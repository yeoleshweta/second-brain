"""Weekly finance review job — syncs Plaid and writes a summary to Obsidian.

Runs every Sunday at 18:00. Writes to 03-Finance/Weekly/YYYY-WW.md.
"""
from __future__ import annotations

from datetime import datetime

from loguru import logger

from src.integrations.obsidian import ObsidianClient
from src.services.transaction_queries import (
    date_range_for_period,
    detect_subscriptions,
    recent_transactions,
    spending_by_category,
    total_spent,
)
from src.storage import get_session


async def write_weekly_finance_review() -> str | None:
    """Sync transactions, build a weekly finance note, write to Obsidian vault."""
    now = datetime.now()
    week_str = now.strftime("%Y-W%W")
    note_path = f"03-Finance/Weekly/{week_str}.md"

    # Sync first so the note reflects current data
    try:
        from src.services.plaid_sync import sync_all_items

        with next(get_session()) as session:
            sync_results = await sync_all_items(session)
    except Exception as exc:
        logger.warning("Finance review: Plaid sync failed — {}", exc)
        sync_results = []

    # Build spending summary
    try:
        with next(get_session()) as session:
            start, end = date_range_for_period("week")
            total = total_spent(session, start=start, end=end)
            categories = spending_by_category(session, start=start, end=end, top_n=10)
            recent = recent_transactions(session, start=start, end=end, limit=20)
            subs = detect_subscriptions(session)

        # Also pull month-to-date
        with next(get_session()) as session:
            month_start, month_end = date_range_for_period("month")
            month_total = total_spent(session, start=month_start, end=month_end)
    except Exception as exc:
        logger.error("Finance review: query failed — {}", exc)
        return None

    # Compose markdown note
    lines: list[str] = [
        "---",
        f"generated: {now.isoformat()}",
        f"week: {week_str}",
        "tags: [finance, weekly-review]",
        "---",
        "",
        f"# 💰 Finance Review — {week_str}",
        "",
        f"**This week's spending: ${total:,.2f}**  |  "
        f"**Month-to-date: ${month_total:,.2f}**",
        "",
    ]

    # Spending by category
    if categories:
        lines += ["## Spending by Category", ""]
        lines += [
            "| Category | Total | Txns |",
            "|---|---|---|",
        ]
        for cat in categories:
            lines.append(f"| {cat['category']} | ${cat['total']:,.2f} | {cat['count']} |")
        lines.append("")

    # Recent transactions
    if recent:
        lines += ["## Recent Transactions", ""]
        for tx in recent[:15]:
            sign = "-" if tx["amount"] < 0 else ""
            lines.append(
                f"- {tx['date']}  **{tx['merchant'] or 'Unknown'}**  "
                f"${sign}{abs(tx['amount']):.2f}  _{tx['category'] or ''}_"
            )
        lines.append("")

    # Subscriptions
    if subs:
        sub_total = sum(s["avg_amount"] for s in subs)
        lines += [f"## Subscriptions (~${sub_total:,.2f}/mo)", ""]
        for sub in subs:
            lines.append(
                f"- {sub['merchant']}: ~${sub['avg_amount']:.2f}/mo "
                f"({sub['occurrences']}× in 90d)"
            )
        lines.append("")

    # Sync results
    if sync_results:
        lines += ["## Sync Results", ""]
        for r in sync_results:
            if r["status"] == "error":
                lines.append(f"- ⚠️ {r['institution']}: {r.get('error', 'error')}")
            else:
                lines.append(
                    f"- ✅ {r['institution']}: +{r['added']} new, "
                    f"{r['modified']} updated, {r['removed']} removed"
                )
        lines.append("")

    content = "\n".join(lines)

    try:
        async with ObsidianClient() as obsidian:
            await obsidian.create_note(note_path, content)
        logger.info("Weekly finance review written to {}", note_path)
        return note_path
    except Exception as exc:
        logger.error("Finance review: Obsidian write failed — {}", exc)
        return None
