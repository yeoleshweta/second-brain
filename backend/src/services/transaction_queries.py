"""Query and aggregate Transaction data for the Finance agent.

All amounts use Plaid's sign convention: positive = money out (expense),
negative = money in (credit/refund).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlmodel import Session, select

from src.storage.models import Transaction

# Categories we treat as income / internal transfers — exclude from spending totals.
_EXCLUDE_CATEGORIES = {
    "transfer",
    "transfer_in",
    "transfer_out",
    "payroll",
    "loan_payments",
    "bank_fees",
    "interest_earned",
    "income",
    "duplicate",
}


def _is_expense(tx: Transaction) -> bool:
    cat = (tx.category or "").lower().replace(" ", "_")
    if any(exc in cat for exc in _EXCLUDE_CATEGORIES):
        return False
    return tx.amount > 0 and not tx.pending


def date_range_for_period(period: str) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for common period strings."""
    now = datetime.now()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == "week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start, now
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == "last_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_prev = first_this - timedelta(days=1)
        start = last_prev.replace(day=1)
        return start, first_this
    if period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    # Default: last 30 days
    return now - timedelta(days=30), now


def spending_by_category(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    top_n: int = 10,
) -> list[dict]:
    """Return [{category, total, count}] sorted by spend, top_n categories."""
    txs = session.exec(
        select(Transaction).where(Transaction.date >= start, Transaction.date <= end)
    ).all()

    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for tx in txs:
        if not _is_expense(tx):
            continue
        cat = tx.category or "Uncategorized"
        totals[cat] += tx.amount
        counts[cat] += 1

    result = [
        {"category": cat, "total": round(totals[cat], 2), "count": counts[cat]}
        for cat in totals
    ]
    result.sort(key=lambda x: x["total"], reverse=True)
    return result[:top_n]


def total_spent(session: Session, *, start: datetime, end: datetime) -> float:
    txs = session.exec(
        select(Transaction).where(Transaction.date >= start, Transaction.date <= end)
    ).all()
    return round(sum(tx.amount for tx in txs if _is_expense(tx)), 2)


def recent_transactions(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    limit: int = 50,
    merchant_filter: str | None = None,
    category_filter: str | None = None,
) -> list[dict]:
    """Return recent transactions as serialisable dicts, newest first."""
    txs = session.exec(
        select(Transaction)
        .where(Transaction.date >= start, Transaction.date <= end)
        .order_by(Transaction.date.desc())
        .limit(limit * 3)  # over-fetch so we can apply filters client-side
    ).all()

    result: list[dict] = []
    for tx in txs:
        if merchant_filter and merchant_filter.lower() not in (tx.merchant or "").lower():
            continue
        if category_filter and category_filter.lower() not in (tx.category or "").lower():
            continue
        result.append(
            {
                "id": tx.id,
                "plaid_transaction_id": tx.plaid_transaction_id,
                "date": tx.date.date().isoformat() if tx.date else None,
                "merchant": tx.merchant,
                "category": tx.category,
                "amount": round(tx.amount, 2),
                "pending": tx.pending,
            }
        )
        if len(result) >= limit:
            break
    return result


def detect_subscriptions(
    session: Session,
    *,
    lookback_days: int = 90,
    min_occurrences: int = 2,
) -> list[dict]:
    """Find merchants that charge roughly monthly — likely subscriptions."""
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    txs = session.exec(
        select(Transaction)
        .where(Transaction.date >= start, Transaction.date <= end, Transaction.pending == False)  # noqa: E712
        .order_by(Transaction.date.desc())
    ).all()

    merchant_txs: dict[str, list[Transaction]] = defaultdict(list)
    for tx in txs:
        if tx.amount <= 0:
            continue
        key = (tx.merchant or "Unknown").strip().lower()
        merchant_txs[key].append(tx)

    subs: list[dict] = []
    for merchant_key, charges in merchant_txs.items():
        if len(charges) < min_occurrences:
            continue
        amounts = [c.amount for c in charges]
        avg_amount = sum(amounts) / len(amounts)
        # Check amounts are consistent (within 10%)
        if max(amounts) - min(amounts) > avg_amount * 0.1 + 1:
            continue
        subs.append(
            {
                "merchant": charges[0].merchant or merchant_key.title(),
                "avg_amount": round(avg_amount, 2),
                "occurrences": len(charges),
                "last_charged": charges[0].date.date().isoformat() if charges[0].date else None,
            }
        )
    subs.sort(key=lambda x: x["avg_amount"], reverse=True)
    return subs


def spending_summary_text(
    session: Session,
    *,
    period: str = "month",
) -> str:
    """Return a human-readable spending summary for the given period."""
    start, end = date_range_for_period(period)
    total = total_spent(session, start=start, end=end)
    categories = spending_by_category(session, start=start, end=end, top_n=5)
    subs = detect_subscriptions(session)

    period_label = {
        "today": "today",
        "week": "this week",
        "month": "this month",
        "last_month": "last month",
        "year": "this year",
    }.get(period, "the past 30 days")

    lines = [f"**Total spent {period_label}: ${total:,.2f}**\n"]
    if categories:
        lines.append("**Top categories:**")
        for cat in categories:
            lines.append(f"- {cat['category']}: ${cat['total']:,.2f} ({cat['count']} txns)")
    if subs:
        lines.append("\n**Likely subscriptions:**")
        for sub in subs[:5]:
            lines.append(f"- {sub['merchant']}: ~${sub['avg_amount']:,.2f}/mo")

    return "\n".join(lines)
