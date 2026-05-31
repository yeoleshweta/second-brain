"""Chandler — Calendar & Networking Agent.

Handles scheduling, today's agenda, person notes, and the schedule section
of the unified morning brief. Every destructive action goes through the
pending-confirmation flow before touching Google Calendar or Obsidian.

Sub-intent dispatch (regex-first, no LLM classification):
  schedule      → parse → confirm → create event
  agenda        → list today's/week's Google Calendar events
  find_person   → read 04-People/<name>.md
  add_person    → confirm → create person note
  update_person → confirm → edit frontmatter
  chat          → gpt-4o-mini, reply only
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import dateparser
from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings
from src.services import pending_actions as pa
from src.services import people

if TYPE_CHECKING:
    from src.orchestrator.graph import AgentState

# ── Regex helpers ──────────────────────────────────────────────────────────────

_SCHEDULE_RE = re.compile(
    r"\b(schedule|book|set up|put on( my)? calendar|add a meeting|create( an?)? event)\b",
    re.IGNORECASE,
)
_AGENDA_RE = re.compile(
    r"\b(what'?s? on (today|this week)|today'?s? agenda|agenda|"
    r"what (do i have|am i doing) today|my schedule)\b",
    re.IGNORECASE,
)
_FIND_PERSON_RE = re.compile(
    r"\b(what do i know about|info on|who is|tell me about)\b\s+(.+)",
    re.IGNORECASE,
)
_ADD_PERSON_RE = re.compile(
    r"^(add\s+(\w[\w\s]*?)\s+to (my )?contacts|met\s+(\w[\w\s]*?)\s*(,|at|–))",
    re.IGNORECASE,
)
_ADD_PERSON_WORKS_RE = re.compile(
    r"^(\w[\w\s]*?)\s+works at\b",
    re.IGNORECASE,
)
_UPDATE_PERSON_RE = re.compile(
    r"^(update\s+(\w[\w\s]*?)[\s,]|(\w[\w\s]*?)\s+(is now|is a|just got|joined|moved to|left|works at|started at|was promoted|got promoted))",
    re.IGNORECASE,
)
_YES_RE = re.compile(r"^\s*(yes|y|yep|yeah|confirm|do it|go|sure|ok)\s*[!.]?\s*$", re.IGNORECASE)
_NO_RE = re.compile(r"^\s*(no|n|nope|cancel|stop|never mind|nah)\s*[!.]?\s*$", re.IGNORECASE)
_DIGEST_RE = re.compile(
    r"\b(what'?s? new|any new|latest|new papers|whats new)\b", re.IGNORECASE
)


def is_yes_no_or_cancel(msg: str) -> bool:
    return bool(_YES_RE.match(msg) or _NO_RE.match(msg))


def classify_chandler_intent(msg: str) -> str:
    # Agenda must be checked before schedule — "my schedule" should show agenda, not create one
    if _AGENDA_RE.search(msg):
        return "agenda"
    if _SCHEDULE_RE.search(msg):
        return "schedule"
    m = _FIND_PERSON_RE.search(msg)
    if m:
        return "find_person"
    if _ADD_PERSON_RE.match(msg) or _ADD_PERSON_WORKS_RE.match(msg):
        return "add_person"
    if _UPDATE_PERSON_RE.match(msg):
        return "update_person"
    return "chat"


# ── OpenAI helper ──────────────────────────────────────────────────────────────

def _openai() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


async def _extract_event_fields(msg: str) -> dict | None:
    """Use gpt-4o-mini to parse scheduling text into structured fields."""
    today = datetime.now().strftime("%A %Y-%m-%d %H:%M")
    prompt = (
        f"Today is {today}. Parse this scheduling request into JSON.\n"
        "Return ONLY a JSON object with these keys:\n"
        "  summary (string, event title),\n"
        "  person_name (string or null, if a person is explicitly named),\n"
        "  person_email (string or null),\n"
        "  start_iso (ISO 8601 datetime string, infer from context),\n"
        "  duration_minutes (int, default 30; use 60 if 'coffee' or 'lunch' appears),\n"
        "  description (string or null)\n"
        f"Message: {msg}"
    )
    import json as _json
    client = _openai()
    resp = await client.chat.completions.create(
        model=get_settings().openai_model_cheap,
        max_tokens=200,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return _json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None


async def _extract_person_fields(msg: str) -> dict | None:
    """Extract name + attributes from an 'add person' message."""
    import json as _json
    client = _openai()
    resp = await client.chat.completions.create(
        model=get_settings().openai_model_cheap,
        max_tokens=150,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                "Extract person info from this message. "
                "Return JSON with: name, company (or null), role (or null), "
                "location (or null), tags (list), notes (string with any extra context or null).\n"
                f"Message: {msg}"
            ),
        }],
    )
    try:
        return _json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None


async def _extract_update_fields(msg: str) -> dict | None:
    """Extract name + what to update from an 'update person' message."""
    import json as _json
    client = _openai()
    resp = await client.chat.completions.create(
        model=get_settings().openai_model_cheap,
        max_tokens=150,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": (
                "Extract the person update from this message. "
                "Return JSON with: name (who is being updated), "
                "updates (dict of frontmatter fields to change, e.g. {role: 'Staff'}).\n"
                f"Message: {msg}"
            ),
        }],
    )
    try:
        return _json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return None


# ── Date parsing ───────────────────────────────────────────────────────────────

def _parse_start_dt(start_iso: str | None, msg: str) -> datetime | None:
    """Parse a datetime from the LLM's start_iso, falling back to dateparser on msg."""
    if start_iso:
        try:
            return datetime.fromisoformat(start_iso)
        except ValueError:
            pass
    # Fallback: dateparser on the raw message
    return dateparser.parse(msg, settings={"PREFER_DATES_FROM": "future"})


def _format_event_time(dt: datetime, duration: int) -> str:
    end_dt = dt + timedelta(minutes=duration)
    return f"{dt.strftime('%a %b %-d at %-I:%M%p').rstrip()} – {end_dt.strftime('%-I:%M%p').rstrip().lower()}"


# ── Google Calendar guard ──────────────────────────────────────────────────────

def _google_not_connected_reply() -> dict:
    settings = get_settings()
    if not settings.google_oauth_client_secrets or not Path(settings.google_oauth_client_secrets).exists():
        return {
            "reply": (
                "📅 Chandler: I'm not connected to Google Calendar yet. "
                "See `docs/phase-2-iphone-setup.md` for the one-time setup."
            )
        }
    if not settings.google_token_path or not Path(settings.google_token_path).exists():
        return {
            "reply": (
                "📅 Chandler: Google not authorized yet. "
                "Run: `cd backend && uv run python -m src.integrations.google_calendar auth`"
            )
        }
    return {}


# ── Handlers ───────────────────────────────────────────────────────────────────

async def handle_schedule(msg: str) -> dict:
    guard = _google_not_connected_reply()
    if guard:
        return guard

    parsed = await _extract_event_fields(msg)
    if not parsed or not parsed.get("start_iso") and not parsed.get("summary"):
        return {
            "reply": (
                "📅 Chandler: couldn't parse that. "
                "Try: 'schedule coffee with Sarah Tuesday at 3pm'."
            )
        }

    # Resolve the start datetime
    start_dt = _parse_start_dt(parsed.get("start_iso"), msg)
    if not start_dt:
        return {
            "reply": (
                "📅 Chandler: I couldn't figure out when that is. "
                "Please include a day and time, e.g. 'Tuesday at 3pm'."
            )
        }

    # Past time today → push to tomorrow
    if start_dt < datetime.now():
        start_dt += timedelta(days=1)

    duration = int(parsed.get("duration_minutes") or 30)
    summary = parsed.get("summary") or "Meeting"

    payload = {
        "summary": summary,
        "person_name": parsed.get("person_name"),
        "person_email": parsed.get("person_email"),
        "start_iso": start_dt.isoformat(),
        "duration_minutes": duration,
        "description": parsed.get("description") or "",
    }
    pa.set_pending("create_event", payload)

    time_str = _format_event_time(start_dt, duration)
    person_note = f" with {payload['person_name']}" if payload.get("person_name") else ""
    return {
        "reply": (
            f"📅 Confirm: '{summary}'{person_note} on {time_str} ({duration} min). "
            "Reply 'yes' to add or 'no' to cancel."
        )
    }


async def handle_confirmation(msg: str, pending: pa.PendingAction) -> dict:
    if _NO_RE.match(msg):
        pa.consume_pending()
        return {"reply": "📅 Chandler: cancelled."}

    if _YES_RE.match(msg):
        action = pa.consume_pending()
        if not action:
            return {"reply": "📅 Chandler: nothing pending to confirm."}
        return await _execute_action(action)

    # Ambiguous — re-prompt without consuming
    return {
        "reply": (
            f"📅 Chandler: did you mean to confirm the pending action? "
            "Reply 'yes' to confirm or 'no' to cancel — I'll wait 5 minutes."
        )
    }


async def _execute_action(action: pa.PendingAction) -> dict:
    if action.kind == "create_event":
        return await _do_create_event(action.payload)
    if action.kind == "create_person":
        return await _do_create_person(action.payload)
    if action.kind == "update_person":
        return await _do_update_person(action.payload)
    return {"reply": "📅 Chandler: unknown action type — nothing done."}


async def _do_create_event(payload: dict) -> dict:
    from src.integrations.google_calendar import GoogleCalendarClient
    try:
        client = GoogleCalendarClient()
    except RuntimeError as e:
        return {"reply": f"📅 Chandler: {e}"}

    start_dt = datetime.fromisoformat(payload["start_iso"])
    end_dt = start_dt + timedelta(minutes=payload["duration_minutes"])
    attendees = [payload["person_email"]] if payload.get("person_email") else []

    try:
        await client.create_event(
            summary=payload["summary"],
            start=start_dt,
            end=end_dt,
            description=payload.get("description", ""),
            attendees=attendees,
        )
    except Exception as e:
        logger.error("create_event failed: {}", e)
        return {"reply": f"📅 Chandler: failed to create event — {e}"}

    reply_parts = [f"✅ Added '{payload['summary']}' to your calendar."]
    obsidian_path = None

    # Log to people note
    person_name = payload.get("person_name")
    if person_name:
        matches = people.find(person_name)
        if matches:
            file_path = matches[0]["path"]
            people.log_interaction(
                file_path,
                f"Calendar event: {payload['summary']} on {start_dt.strftime('%Y-%m-%d')}",
                start_dt.date(),
            )
            slug = Path(file_path).stem
            reply_parts.append(f"Also logged to 04-People/{slug}.md.")
            obsidian_path = f"04-People/{slug}.md"
        else:
            reply_parts.append(
                f"(No note found for {person_name} — create one with "
                f"'add {person_name} to my contacts'.)"
            )

    return {"reply": " ".join(reply_parts), "obsidian_path": obsidian_path}


async def _do_create_person(payload: dict) -> dict:
    name = payload.get("name", "")
    if not name:
        return {"reply": "📅 Chandler: no name given — can't create contact."}

    try:
        fm_fields = {k: v for k, v in payload.items() if k != "name" and v}
        notes = fm_fields.pop("notes", None)
        file_path = people.create(name, **fm_fields)
        if notes:
            people.log_interaction(file_path, notes)
    except Exception as e:
        logger.error("create_person failed: {}", e)
        return {"reply": f"📅 Chandler: failed to create contact — {e}"}

    slug = file_path.name
    return {
        "reply": f"✅ Saved {name} to 04-People/{slug}",
        "obsidian_path": f"04-People/{slug}",
    }


async def _do_update_person(payload: dict) -> dict:
    name = payload.get("name", "")
    updates = payload.get("updates", {})
    matches = people.find(name)
    if not matches:
        return {"reply": f"📅 Chandler: I don't have a note for {name}."}

    file_path = matches[0]["path"]
    try:
        people.update_frontmatter(file_path, updates)
    except Exception as e:
        logger.error("update_person failed: {}", e)
        return {"reply": f"📅 Chandler: update failed — {e}"}

    slug = file_path.name
    return {
        "reply": f"✅ Updated {matches[0]['frontmatter'].get('name', name)}.",
        "obsidian_path": f"04-People/{slug}",
    }


async def handle_agenda(msg: str) -> dict:
    guard = _google_not_connected_reply()
    if guard:
        return guard

    # Determine window: "this week" → rest of week; default → rest of today
    is_week = bool(re.search(r"\bthis week\b", msg, re.IGNORECASE))
    hours = 24 * 7 if is_week else 24

    from src.integrations.google_calendar import GoogleCalendarClient
    try:
        client = GoogleCalendarClient()
        events = await client.list_upcoming_events(hours=hours)
    except Exception as e:
        return {"reply": f"📅 Chandler: couldn't reach Google Calendar — {e}"}

    if not events:
        scope = "this week" if is_week else "the rest of today"
        return {
            "reply": (
                f"📅 Chandler: nothing on the calendar for {scope}. "
                "Want to add something?"
            )
        }

    lines = ["📅 Here's what's coming up:\n"]
    for ev in events:
        start = ev.get("start", {})
        start_str = start.get("dateTime") or start.get("date", "")
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_label = start_dt.strftime("%-I:%M%p").lower()
        except Exception:
            time_label = start_str

        summary = ev.get("summary", "(no title)")
        attendee_names = [
            a.get("displayName") or a.get("email", "")
            for a in ev.get("attendees", [])
            if not a.get("self")
        ]

        line = f"- **{time_label}** — {summary}"
        if attendee_names:
            line += f" (with {', '.join(attendee_names)})"

        # Prep note from people file
        for aname in attendee_names:
            matches = people.find(aname)
            if matches:
                fm = matches[0]["frontmatter"]
                if fm.get("last_interaction"):
                    line += f"\n  _Prep: last talked about: {fm['last_interaction']}_"
                break

        lines.append(line)

    return {"reply": "\n".join(lines)}


async def handle_find_person(msg: str) -> dict:
    m = _FIND_PERSON_RE.search(msg)
    query = m.group(2).strip() if m else msg.strip()

    matches = people.find(query)
    if not matches:
        return {
            "reply": (
                f"📅 Chandler: I don't have a note for {query} yet. "
                f"Tell me about them: '{query} works at <company>, met at <event>.'"
            )
        }
    if len(matches) == 1:
        return {"reply": people.get_summary(matches[0])}

    # Multiple matches
    options = "\n".join(
        f"{i+1}. {p['frontmatter'].get('name', p['filename'])} "
        f"({p['frontmatter'].get('company', '?')})"
        for i, p in enumerate(matches)
    )
    return {"reply": f"📅 Which {query}?\n{options}"}


async def handle_add_person(msg: str) -> dict:
    parsed = await _extract_person_fields(msg)
    if not parsed or not parsed.get("name"):
        return {
            "reply": (
                "📅 Chandler: couldn't extract a name. "
                "Try: 'Sarah Wong works at Anthropic, met at Re:Invent'."
            )
        }

    name = parsed["name"]
    company = parsed.get("company") or ""
    confirm_line = f"📇 New contact: {name}"
    if company:
        confirm_line += f" @ {company}"
    confirm_line += ". Confirm? (yes/no)"

    pa.set_pending("create_person", parsed)
    return {"reply": confirm_line}


async def handle_update_person(msg: str) -> dict:
    parsed = await _extract_update_fields(msg)
    if not parsed or not parsed.get("name") or not parsed.get("updates"):
        return {"reply": "📅 Chandler: couldn't parse that update. Try: 'Sarah just got promoted to Staff'."}

    name = parsed["name"]
    updates = parsed["updates"]

    # Confirm with matched person
    matches = people.find(name)
    if not matches:
        return {
            "reply": (
                f"📅 Chandler: I don't have a note for {name} yet. "
                f"Add them first: '{name} works at <company>.'"
            )
        }

    if len(matches) > 1:
        options = "\n".join(
            f"{i+1}. {p['frontmatter'].get('name')} ({p['frontmatter'].get('company', '?')})"
            for i, p in enumerate(matches)
        )
        return {"reply": f"📅 Which {name}?\n{options}"}

    person = matches[0]
    full_name = person["frontmatter"].get("name", name)
    changes = ", ".join(f"{k}='{v}'" for k, v in updates.items())
    confirm_line = f"Update {full_name}: {changes}? (yes/no)"

    pa.set_pending("update_person", {"name": name, "updates": updates, "file_path": str(person["path"])})
    return {"reply": confirm_line}


async def handle_chat(msg: str) -> dict:
    client = _openai()
    resp = await client.chat.completions.create(
        model=get_settings().openai_model_cheap,
        max_tokens=200,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Chandler, the calendar and networking agent in a personal AI second brain. "
                    "The user is chatting about scheduling, people, or networking. "
                    "Reply briefly (2-3 sentences). Do not pretend to schedule or save anything — "
                    "they need to explicitly ask. "
                    "Voice: dry, organized, slightly sarcastic. Don't overdo it."
                ),
            },
            {"role": "user", "content": msg},
        ],
    )
    return {"reply": resp.choices[0].message.content or ""}


# ── Morning brief section ─────────────────────────────────────────────────────

async def morning_section() -> str:
    """Return the Chandler schedule section for the combined morning brief."""
    guard = _google_not_connected_reply()
    if guard:
        return "## 📅 Chandler's Schedule\n\nGoogle Calendar not connected.\n"

    from src.integrations.google_calendar import GoogleCalendarClient
    try:
        client = GoogleCalendarClient()
        events = await client.list_upcoming_events(hours=24)
    except Exception as e:
        logger.warning("Chandler morning_section: calendar error: {}", e)
        return f"## 📅 Chandler's Schedule\n\nCouldn't reach Google Calendar: {e}\n"

    if not events:
        return "## 📅 Chandler's Schedule\n\nNothing scheduled today.\n"

    lines = ["## 📅 Chandler's Schedule\n"]
    for ev in events:
        start = ev.get("start", {})
        start_str = start.get("dateTime") or start.get("date", "")
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_label = start_dt.strftime("%-I:%M%p").lower()
        except Exception:
            time_label = start_str

        summary = ev.get("summary", "(no title)")
        attendees = [
            a.get("displayName") or a.get("email", "")
            for a in ev.get("attendees", [])
            if not a.get("self")
        ]

        line = f"- **{time_label}** — {summary}"
        if attendees:
            line += f" · {', '.join(attendees)}"

        for aname in attendees:
            matches = people.find(aname)
            if matches and matches[0]["frontmatter"].get("last_interaction"):
                line += f"\n  _(Prep: {matches[0]['frontmatter']['last_interaction']})_"
                break

        lines.append(line)

    return "\n".join(lines) + "\n"


# ── Main entry point ──────────────────────────────────────────────────────────

async def run(state: AgentState) -> dict:
    """Chandler's main dispatch. Never writes to inbox; never calls stub_run."""
    msg = state.get("user_message", "")

    # Confirmation flow takes priority
    pending = pa.peek_pending()
    if pending and is_yes_no_or_cancel(msg):
        return await handle_confirmation(msg, pending)

    # Edge case: "nothing pending" confirmation attempt
    if is_yes_no_or_cancel(msg):
        return {"reply": "📅 Chandler: nothing pending to confirm."}

    intent = classify_chandler_intent(msg)
    if intent == "schedule":
        return await handle_schedule(msg)
    if intent == "agenda":
        return await handle_agenda(msg)
    if intent == "find_person":
        return await handle_find_person(msg)
    if intent == "add_person":
        return await handle_add_person(msg)
    if intent == "update_person":
        return await handle_update_person(msg)
    return await handle_chat(msg)
