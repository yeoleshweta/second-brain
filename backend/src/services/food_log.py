"""Food logging — SQLite + Obsidian daily notes."""
from __future__ import annotations

from datetime import date, datetime, time

from sqlmodel import Session, select

from src.integrations import ObsidianClient
from src.storage.models import FoodEntry

FOOD_DIR = "02-Health/Food"


def add(
    session: Session,
    *,
    description: str,
    quantity: str | None = None,
    calories: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    source: str = "manual",
) -> FoodEntry:
    entry = FoodEntry(
        description=description.strip(),
        quantity=quantity,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        source=source,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_for_day(session: Session, day: date | None = None) -> list[FoodEntry]:
    day = day or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    return list(
        session.exec(
            select(FoodEntry)
            .where(FoodEntry.timestamp >= start, FoodEntry.timestamp <= end)
            .order_by(FoodEntry.timestamp.asc())
        ).all()
    )


def list_since(session: Session, since: datetime) -> list[FoodEntry]:
    return list(
        session.exec(
            select(FoodEntry)
            .where(FoodEntry.timestamp >= since)
            .order_by(FoodEntry.timestamp.asc())
        ).all()
    )


def day_totals(entries: list[FoodEntry]) -> dict[str, float]:
    def _sum(attr: str) -> float:
        return round(sum(getattr(e, attr) or 0 for e in entries), 1)

    return {
        "calories": _sum("calories"),
        "protein_g": _sum("protein_g"),
        "carbs_g": _sum("carbs_g"),
        "fat_g": _sum("fat_g"),
        "meals": float(len(entries)),
    }


def _format_entry_line(entry: FoodEntry) -> str:
    ts = entry.timestamp.strftime("%H:%M")
    macro_bits: list[str] = []
    if entry.calories:
        macro_bits.append(f"{int(entry.calories)} kcal")
    if entry.protein_g:
        macro_bits.append(f"{entry.protein_g:.0f}g protein")
    macro = f" ({', '.join(macro_bits)})" if macro_bits else ""
    qty = f" — {entry.quantity}" if entry.quantity else ""
    return f"- **{ts}** {entry.description}{qty}{macro}"


async def mirror_day(session: Session, day: date | None = None) -> str | None:
    """Rewrite today's food note in Obsidian from DB entries."""
    day = day or date.today()
    entries = list_for_day(session, day)
    if not entries:
        return None

    totals = day_totals(entries)
    lines = [_format_entry_line(e) for e in entries]
    body = (
        f"# Food log — {day.isoformat()}\n\n"
        f"**Daily totals:** {int(totals['calories'])} kcal · "
        f"{totals['protein_g']:.0f}g protein · "
        f"{totals['carbs_g']:.0f}g carbs · "
        f"{totals['fat_g']:.0f}g fat\n\n"
        + "\n".join(lines)
        + "\n"
    )
    path = f"{FOOD_DIR}/{day.isoformat()}.md"
    try:
        async with ObsidianClient() as obs:
            await obs.create_note(path, body)
        return path
    except Exception:
        return None
