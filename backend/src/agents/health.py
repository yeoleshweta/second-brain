"""Monica — Health, Nutrition & Fitness Agent.

Logs meals (USDA + SQLite + Obsidian), workouts, and weekly nutrition summaries.
Default chat stays in chat — no auto-save to the daily inbox.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger
from openai import AsyncOpenAI
from sqlmodel import Session

from src.config import get_settings
from src.integrations import ObsidianClient
from src.integrations.usda import search_food
from src.services import food_log as fl
from src.storage import get_session, init_db

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

WORKOUT_DIR = "02-Health/Workouts"

MONICA_CHAT_SYSTEM = (
    "You are Monica Geller from Friends — reimagined as the user's nutritionist "
    "and personal trainer in their second-brain app.\n\n"
    "Voice: warm, organized, competitive-but-supportive. Short, practical replies.\n"
    "You CAN log meals when the user says things like \"I had eggs for breakfast\" "
    "(the app handles the save — you'll see a confirmation in context).\n"
    "You CAN log workouts when they say \"I did 30 min yoga\".\n"
    "For general nutrition questions, give clear evidence-based advice.\n"
    "Do not invent logged meals or claim you saved something unless the app confirmed it.\n"
    "2–4 sentences unless they ask for a plan or detailed breakdown."
)

FOOD_LOG_RE = re.compile(
    r"\b("
    r"I had|I ate|I just had|I just ate|"
    r"for breakfast|for lunch|for dinner|for a snack|"
    r"log (?:my )?meal|logged (?:my )?meal|"
    r"ate .+ for"
    r")\b",
    re.IGNORECASE,
)
WORKOUT_LOG_RE = re.compile(
    r"\b("
    r"I did|I ran|I walked|I lifted|I worked out|"
    r"log (?:my )?workout|logged (?:my )?workout|"
    r"\d+\s*(?:min|minute|minutes|mi|mile|miles|km)\s+(?:of\s+)?(?:yoga|run|walk|swim|bike|cycling|hiit|weights|lifting|workout)"
    r")\b",
    re.IGNORECASE,
)
NUTRITION_STATUS_RE = re.compile(
    r"\b("
    r"how am I doing|nutrition this week|weekly health|"
    r"what did I eat|food log today|calories today|"
    r"my meals today|nutrition summary"
    r")\b",
    re.IGNORECASE,
)

_MEAL_PREFIX_RE = re.compile(
    r"^(?:I (?:had|ate|just had|just ate)\s+|log (?:my )?meal[:\s]+|logged (?:my )?meal[:\s]+)",
    re.IGNORECASE,
)
_MEAL_SUFFIX_RE = re.compile(
    r"\s+for (?:breakfast|lunch|dinner|a snack|snack)\.?\s*$",
    re.IGNORECASE,
)


def classify_health_intent(msg: str) -> str:
    lowered = msg.strip().lower()
    if NUTRITION_STATUS_RE.search(lowered):
        return "nutrition_status"
    if WORKOUT_LOG_RE.search(msg) and not FOOD_LOG_RE.search(msg):
        return "log_workout"
    if FOOD_LOG_RE.search(msg):
        return "log_food"
    return "chat"


def _clean_meal_description(msg: str) -> str:
    text = _MEAL_PREFIX_RE.sub("", msg.strip())
    text = _MEAL_SUFFIX_RE.sub("", text)
    return text.strip(" .,-") or msg.strip()


def _macro_line(entry: fl.FoodEntry) -> str:
    parts: list[str] = []
    if entry.calories:
        parts.append(f"**{int(entry.calories)} kcal**")
    if entry.protein_g:
        parts.append(f"{entry.protein_g:.0f}g protein")
    if entry.carbs_g:
        parts.append(f"{entry.carbs_g:.0f}g carbs")
    if entry.fat_g:
        parts.append(f"{entry.fat_g:.0f}g fat")
    return " · ".join(parts) if parts else "logged (no macro data)"


async def handle_log_food(msg: str, session: Session) -> dict:
    description = _clean_meal_description(msg)
    settings = get_settings()
    nutrients: dict[str, float | str | None] = {}
    source = "manual"

    if settings.usda_api_key:
        hit = await search_food(description, api_key=settings.usda_api_key)
        if hit and hit.get("description"):
            nutrients = hit
            source = "usda"
            if hit["description"] and hit["description"].lower() not in description.lower():
                description = f"{description} ({hit['description']})"

    entry = fl.add(
        session,
        description=description,
        calories=float(nutrients["calories"]) if nutrients.get("calories") else None,
        protein_g=float(nutrients["protein_g"]) if nutrients.get("protein_g") else None,
        carbs_g=float(nutrients["carbs_g"]) if nutrients.get("carbs_g") else None,
        fat_g=float(nutrients["fat_g"]) if nutrients.get("fat_g") else None,
        source=source,
    )
    mirror_path = await fl.mirror_day(session)
    totals = fl.day_totals(fl.list_for_day(session))
    macro = _macro_line(entry)

    usda_note = ""
    if not settings.usda_api_key:
        usda_note = " _(Add `USDA_API_KEY` in `.env` for automatic calorie lookup.)_"

    reply = (
        f"🥗 Logged: **{entry.description}** — {macro}.{usda_note}\n\n"
        f"Today so far: **{int(totals['calories'])} kcal** across "
        f"{int(totals['meals'])} meal(s). I know!"
    )
    return {"reply": reply, "obsidian_path": mirror_path, "intent": "health"}


async def handle_log_workout(msg: str, session: Session) -> dict:
    del session  # workouts are Obsidian-only for now
    today = date.today().isoformat()
    path = f"{WORKOUT_DIR}/{today}.md"
    ts = datetime.now().strftime("%H:%M")
    line = f"- **{ts}** {msg.strip()}\n"

    try:
        async with ObsidianClient() as obs:
            try:
                existing = await obs.get_note(path)
                if "## Workouts" in existing:
                    updated = existing.rstrip() + "\n" + line
                else:
                    updated = existing.rstrip() + f"\n\n## Workouts\n{line}"
            except Exception:
                updated = f"# Workout log — {today}\n\n## Workouts\n{line}"
            await obs.create_note(path, updated)
    except Exception as exc:
        logger.warning("Workout mirror failed: {}", exc)
        return {
            "reply": (
                "🥗 I noted your workout in chat, but couldn't reach Obsidian. "
                "Is the Local REST API running?"
            ),
            "intent": "health",
        }

    return {
        "reply": (
            f"💪 Logged your workout — nice work! Saved to `{path}`. "
            "Want me to suggest a recovery snack?"
        ),
        "obsidian_path": path,
        "intent": "health",
    }


async def handle_nutrition_status(session: Session) -> dict:
    since = datetime.now() - timedelta(days=7)
    entries = fl.list_since(session, since)
    if not entries:
        return {
            "reply": (
                "🥗 No meals logged this week yet. Tell me what you ate — "
                "e.g. **I had oatmeal with berries for breakfast**."
            ),
            "intent": "health",
        }

    by_day: dict[date, list] = {}
    for e in entries:
        d = e.timestamp.date()
        by_day.setdefault(d, []).append(e)

    active_days = len(by_day)
    total_cals = sum(e.calories or 0 for e in entries)
    avg_cals = total_cals / active_days if active_days else 0
    today_entries = fl.list_for_day(session)
    today_totals = fl.day_totals(today_entries)

    lines = [
        f"- **{active_days}** days with meals logged (last 7 days)",
        f"- **{int(avg_cals)}** avg kcal on logged days",
        f"- **Today:** {int(today_totals['calories'])} kcal · "
        f"{int(today_totals['meals'])} meal(s)",
    ]
    return {
        "reply": "🥗 **Your nutrition this week**\n\n" + "\n".join(lines),
        "intent": "health",
    }


async def handle_chat(msg: str, history: list[dict] | None = None) -> dict:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    messages: list[dict[str, str]] = [{"role": "system", "content": MONICA_CHAT_SYSTEM}]
    for turn in (history or [])[-8:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in {"user", "assistant"} and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": msg})

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model_cheap,
            messages=messages,
            max_tokens=512,
        )
        reply = resp.choices[0].message.content or "I'm Monica — what are we working on today?"
    except Exception as exc:
        logger.warning("Monica LLM error: {}", exc)
        reply = (
            "I'm Monica! 🥗 Log a meal with **I had … for breakfast**, "
            "a workout with **I did 30 min yoga**, or ask me anything about nutrition."
        )
    return {"reply": reply, "obsidian_path": None, "intent": "health"}


async def run(state: AgentState) -> dict:
    msg = state.get("user_message", "")
    history = state.get("chat_history") or []
    sub = classify_health_intent(msg)

    init_db()
    with next(get_session()) as session:
        if sub == "log_food":
            return await handle_log_food(msg, session)
        if sub == "log_workout":
            return await handle_log_workout(msg, session)
        if sub == "nutrition_status":
            return await handle_nutrition_status(session)
    return await handle_chat(msg, history)
