"""Usage and estimated cost logging for visibility endpoint."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from src.storage.models import UsageEvent

# Approximate per-1M-token costs (USD) for quick budget visibility.
MODEL_COST_PER_M = {
    "gpt-4o": {"in": 5.0, "out": 15.0},
    "gpt-4o-mini": {"in": 0.15, "out": 0.6},
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = MODEL_COST_PER_M.get(model, MODEL_COST_PER_M["gpt-4o-mini"])
    return (
        (prompt_tokens / 1_000_000.0) * rates["in"]
        + (completion_tokens / 1_000_000.0) * rates["out"]
    )


def log(
    session: Session,
    *,
    agent: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    route: str = "chat",
) -> UsageEvent:
    total_tokens = max(0, prompt_tokens) + max(0, completion_tokens)
    event = UsageEvent(
        agent=agent,
        model=model,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(model, prompt_tokens, completion_tokens),
        route=route,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def today_summary(session: Session, day: date | None = None) -> dict:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    rows = list(
        session.exec(
            select(UsageEvent).where(
                UsageEvent.timestamp >= start,
                UsageEvent.timestamp < end,
            )
        ).all()
    )
    return {
        "date": day.isoformat(),
        "events": len(rows),
        "total_tokens": sum(r.total_tokens for r in rows),
        "prompt_tokens": sum(r.prompt_tokens for r in rows),
        "completion_tokens": sum(r.completion_tokens for r in rows),
        "estimated_cost_usd": round(sum(r.estimated_cost_usd for r in rows), 6),
        "by_agent": {
            agent: round(sum(r.estimated_cost_usd for r in rows if r.agent == agent), 6)
            for agent in sorted({r.agent for r in rows})
        },
    }
