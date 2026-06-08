"""Finance Agent — spending analysis, transaction sync, weekly reviews.

SECURITY: READ-ONLY. Never moves money, initiates transfers, or handles payments.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger
from openai import AsyncOpenAI

from src.agents._base import try_obsidian_capture
from src.config import get_settings

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

# ---------------------------------------------------------------------------
# Intent detection regexes
# ---------------------------------------------------------------------------

_SYNC_RE = re.compile(
    r"\b(sync|refresh|update|fetch|pull)\b.{0,20}\b(bank|transaction|account|plaid)\b",
    re.IGNORECASE,
)
_SPENDING_RE = re.compile(
    r"\b(how much|spent|spending|spend|total|amount|cost|paid|expense|expenses|budget)\b",
    re.IGNORECASE,
)
_SUBSCRIPTION_RE = re.compile(
    r"\b(subscription|subscriptions|recurring|monthly charge|netflix|spotify|apple)\b",
    re.IGNORECASE,
)
_RECENT_TX_RE = re.compile(
    r"\b(recent|latest|last|show|list|view)\b.{0,25}\b(transaction|purchase|charge|payment)\b",
    re.IGNORECASE,
)
_SUMMARY_RE = re.compile(
    r"\b(summary|overview|breakdown|report|review|how am i doing)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are Chandler, a sharp and slightly self-deprecating financial advisor \
in the user's personal AI second-brain app. You help with budgeting, spending awareness, \
savings strategies, and financial habits. You're knowledgeable but approachable — finance \
doesn't have to be boring.

You are READ-ONLY — you never move money, initiate transfers, or handle payments. \
If asked to do so, decline clearly and explain why.

When the user asks about spending, budgets, or transactions, you have real data to work with. \
Refer to it directly. Be specific with numbers. Keep replies concise and actionable."""


def _classify(message: str) -> str:
    if _SYNC_RE.search(message):
        return "sync"
    if _SUBSCRIPTION_RE.search(message):
        return "subscriptions"
    if _RECENT_TX_RE.search(message):
        return "recent_transactions"
    if _SPENDING_RE.search(message) or _SUMMARY_RE.search(message):
        return "spending_summary"
    return "general"


def _extract_period(message: str) -> str:
    low = message.lower()
    if "last month" in low:
        return "last_month"
    if "this week" in low or "this week" in low:
        return "week"
    if "today" in low:
        return "today"
    if "this year" in low or "year" in low:
        return "year"
    return "month"


async def _handle_sync() -> str:
    try:
        from src.services.plaid_sync import sync_all_items
        from src.storage import get_session

        with next(get_session()) as session:
            results = await sync_all_items(session)
    except Exception as exc:
        logger.warning("Finance sync error: {}", exc)
        return (
            "I hit an error trying to sync your bank data. "
            "Make sure Plaid is connected in Settings and your `PLAID_*` credentials are set."
        )

    if not results:
        return (
            "No banks connected yet. "
            "Go to **Settings → Bank Connection** and link your first account!"
        )

    lines = ["Bank sync complete! Here's what changed:\n"]
    for r in results:
        if r["status"] == "error":
            lines.append(f"- ⚠️ {r['institution']}: sync failed — {r.get('error', 'unknown error')}")
        else:
            lines.append(
                f"- ✅ **{r['institution']}**: "
                f"+{r['added']} new, {r['modified']} updated, {r['removed']} removed"
            )
    return "\n".join(lines)


def _handle_spending_summary(message: str) -> str:
    period = _extract_period(message)
    try:
        from src.services.transaction_queries import spending_summary_text
        from src.storage import get_session

        with next(get_session()) as session:
            return spending_summary_text(session, period=period)
    except Exception as exc:
        logger.warning("Spending summary error: {}", exc)
        return (
            "I couldn't pull your spending data right now. "
            "Sync your bank first or check that Plaid is connected."
        )


def _handle_recent_transactions(message: str) -> str:
    period = _extract_period(message)
    try:
        from src.services.transaction_queries import date_range_for_period, recent_transactions
        from src.storage import get_session

        with next(get_session()) as session:
            start, end = date_range_for_period(period)
            txs = recent_transactions(session, start=start, end=end, limit=10)
    except Exception as exc:
        logger.warning("Recent transactions error: {}", exc)
        return "Couldn't load transactions — sync your bank first."

    if not txs:
        period_label = period.replace("_", " ")
        return f"No transactions found for {period_label}. Try syncing first."

    lines = [f"**Recent transactions ({period.replace('_', ' ')}):**\n"]
    for tx in txs:
        sign = "-" if tx["amount"] < 0 else ""
        lines.append(
            f"- {tx['date']}  {tx['merchant'] or 'Unknown':<30}  "
            f"${sign}{abs(tx['amount']):.2f}  _{tx['category'] or ''}_"
        )
    return "\n".join(lines)


def _handle_subscriptions() -> str:
    try:
        from src.services.transaction_queries import detect_subscriptions
        from src.storage import get_session

        with next(get_session()) as session:
            subs = detect_subscriptions(session)
    except Exception as exc:
        logger.warning("Subscription detection error: {}", exc)
        return "Couldn't detect subscriptions — sync your bank first."

    if not subs:
        return (
            "No recurring charges detected yet. Sync at least 2 months of data for best results."
        )

    total = sum(s["avg_amount"] for s in subs)
    lines = [f"**Detected subscriptions (~${total:,.2f}/mo total):**\n"]
    for sub in subs:
        lines.append(
            f"- **{sub['merchant']}**: ~${sub['avg_amount']:.2f}/mo "
            f"({sub['occurrences']}× in 90 days)"
        )
    return "\n".join(lines)


async def _handle_general(message: str) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=512,
        )
        return resp.choices[0].message.content or "Happy to talk finances — what's on your mind?"
    except Exception as exc:
        logger.warning("Finance LLM error: {}", exc)
        return (
            "I'm Chandler — your finance advisor! 💰 I can sync your bank, show spending, "
            "detect subscriptions, and chat budgeting. What do you need?"
        )


async def run(state: AgentState) -> dict:
    message = state["user_message"]
    intent_sub = _classify(message)

    if intent_sub == "sync":
        reply = await _handle_sync()
    elif intent_sub == "spending_summary":
        reply = _handle_spending_summary(message)
    elif intent_sub == "recent_transactions":
        reply = _handle_recent_transactions(message)
    elif intent_sub == "subscriptions":
        reply = _handle_subscriptions()
    else:
        reply = await _handle_general(message)

    obsidian_path = await try_obsidian_capture(message, "finance")
    return {"reply": reply, "obsidian_path": obsidian_path, "intent": "finance"}
