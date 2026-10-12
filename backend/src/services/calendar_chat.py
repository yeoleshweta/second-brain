"""Schedule Google Calendar events from the one chat bot, with a confirm gate.

Does not write Notes/People/Projects/Concepts. Schedule, agenda, and yes/no
confirmation turns skip Inbox — calendar is Google, not the wiki.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
from loguru import logger

from src.config import get_settings
from src.services import pending_actions as pa

_REMIND_RE = re.compile(
    r"\b("
    r"remind me|"
    r"set (a |an )?reminder|"
    r"reminder (for|on|to)|"
    r"notify me|"
    r"set (an? )?alarm|"
    r"don'?t let me forget"
    r")\b",
    re.IGNORECASE,
)
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_CLOCK = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
_CLOCK_RE = re.compile(rf"\b(?:{_CLOCK}|noon|midnight)\b", re.IGNORECASE)
_DATE_SNIP_RE = re.compile(
    rf"\b(?:"
    rf"(?:on |at |for )?(?:the )?\d{{1,2}}(?:st|nd|rd|th)?"
    rf"(?:\s+{_MONTH})?"
    rf"|"
    rf"(?:on |at |for )?{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?"
    rf"|"
    rf"(?:tomorrow|today|tonight)(?:\s+(?:morning|afternoon|evening|night))?"
    rf"|"
    rf"{_WEEKDAY}(?:\s+(?:morning|afternoon|evening|night))?"
    rf")"
    rf"(?:\s+at\s+{_CLOCK})?",
    re.IGNORECASE,
)
_SCHEDULE_RE = re.compile(
    r"\b("
    r"schedule|book (?:a |an |my |the |us )|set up|set-up|"
    r"put (this |it |that )?(on|in)( my)? calendar|"
    r"add (a |this |an? )?(meeting|event|call)|"
    r"create( an?)? event|"
    r"add (it |this |that )?to (my )?calendar"
    r")\b",
    re.IGNORECASE,
)
_AGENDA_RE = re.compile(
    r"\b("
    r"what'?s? on (today|this week)|today'?s? agenda|agenda|"
    r"what (do i have|am i doing) today|my schedule|"
    r"what'?s? on my calendar|"
    r"(upcoming|my) meetings|what meetings|"
    r"this week'?s? (calendar|meetings|schedule)|"
    r"sync my calendar"
    r")\b",
    re.IGNORECASE,
)
_MAIL_RE = re.compile(
    r"\b("
    r"unread (email|mail|gmail)|"
    r"my (email|inbox|gmail)|"
    r"what'?s? in my (email|inbox|gmail)|"
    r"check my (email|inbox|mail)|"
    r"sync my email"
    r")\b",
    re.IGNORECASE,
)
_ORGANIZE_RE = re.compile(
    r"\b("
    r"organiz\w* my (day|week|meetings|calendar)|"
    r"sync my meetings|"
    r"meetings and (email|mail)|"
    r"email and meetings"
    r")\b",
    re.IGNORECASE,
)
_YES_RE = re.compile(
    r"^\s*(yes|y|yep|yeah|confirm|do it|go|sure|ok|add it|add to calendar)\s*[!.]?\s*$",
    re.IGNORECASE,
)
_NO_RE = re.compile(
    r"^\s*(no|n|nope|cancel|stop|never mind|nah)\s*[!.]?\s*$",
    re.IGNORECASE,
)
_WITH_PERSON_RE = re.compile(r"\bwith\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)", re.IGNORECASE)


def is_yes_no(msg: str) -> bool:
    return bool(_YES_RE.match(msg) or _NO_RE.match(msg))


def classify_calendar_turn(msg: str) -> str | None:
    if _ORGANIZE_RE.search(msg):
        return "organize"
    if _MAIL_RE.search(msg):
        return "mail"
    if _AGENDA_RE.search(msg):
        return "agenda"
    if _REMIND_RE.search(msg):
        return "remind"
    if _SCHEDULE_RE.search(msg):
        return "schedule"
    return None


def skips_vault(msg: str) -> bool:
    pending = pa.peek_pending()
    if pending and pending.kind == "create_event" and is_yes_no(msg):
        return True
    return classify_calendar_turn(msg) in {
        "schedule",
        "remind",
        "agenda",
        "mail",
        "organize",
    }


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone or "America/New_York")


def _google_ready() -> bool:
    try:
        from src.integrations.google_auth import load_google_credentials

        return load_google_credentials() is not None
    except Exception:
        return False


def _connect_reply() -> str:
    return (
        "Google Calendar isn't connected yet. Open **Settings → Connect Google**, "
        "then ask me again (for example: schedule coffee Tuesday at 3pm). "
        "I will show a confirm card before anything is added. "
        "Calendar writes run on the Mac API, not the Vercel phone deploy."
    )


def _format_when(dt: datetime, duration: int) -> str:
    local = dt.astimezone(_tz()) if dt.tzinfo else dt.replace(tzinfo=_tz())
    end = local + timedelta(minutes=duration)
    start_s = local.strftime("%a %b %d at %I:%M %p").replace(" 0", " ")
    end_s = end.strftime("%I:%M %p").lstrip("0")
    return f"{start_s} – {end_s}"


def _pending_card(payload: dict[str, Any]) -> dict[str, Any]:
    start = datetime.fromisoformat(payload["start_iso"])
    duration = int(payload["duration_minutes"])
    card = {
        "summary": payload["summary"],
        "when": _format_when(start, duration),
        "duration_minutes": duration,
    }
    if payload.get("reminder"):
        card["kind"] = "reminder"
    return card


def _parse_when(msg: str, *, default_hour: int | None) -> datetime | None:
    found = _DATE_SNIP_RE.search(msg)
    if not found:
        return None
    snippet = re.sub(
        r"\b(morning|afternoon|evening|night)\b",
        " ",
        found.group(0),
        flags=re.IGNORECASE,
    )
    snippet = re.sub(r"\s+", " ", snippet).strip()
    tz_name = get_settings().app_timezone or "America/New_York"
    start = dateparser.parse(
        snippet,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": tz_name,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": tz_name,
        },
    )
    if start is None:
        return None
    local = start.astimezone(_tz())
    if not _CLOCK_RE.search(msg):
        if re.search(r"\bmorning\b", msg, re.IGNORECASE):
            hour = 9
        elif re.search(r"\bafternoon\b", msg, re.IGNORECASE):
            hour = 14
        elif re.search(r"\b(evening|night)\b", msg, re.IGNORECASE):
            hour = 18
        elif default_hour is not None:
            hour = default_hour
        else:
            hour = local.hour
        local = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if local <= datetime.now(_tz()):
        return None
    return local


def reminder_summary(msg: str) -> str:
    parts = re.split(
        r"\b(?:remind me(?: to)?|notify me(?: to)?|don'?t let me forget(?: to)?|"
        r"set (?:a |an )?reminder(?: to)?|set (?:an? )?alarm(?: to)?)\b",
        msg,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    text = parts[-1]
    text = _DATE_SNIP_RE.sub(" ", text)
    text = _CLOCK_RE.sub(" ", text)
    text = re.sub(r"^(to|please)\s+", "", re.sub(r"\s+", " ", text).strip(" .,"), flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,")
    if not text:
        return "Reminder"
    if len(text) > 80:
        text = text[:77] + "..."
    return text[0].upper() + text[1:]


def fallback_parse(msg: str) -> dict[str, Any]:
    tz_name = get_settings().app_timezone or "America/New_York"
    start = dateparser.parse(
        msg,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": tz_name,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": tz_name,
        },
    )
    duration = 60 if re.search(r"\b(coffee|lunch|dinner)\b", msg, re.I) else 30
    person = None
    m = _WITH_PERSON_RE.search(msg)
    if m:
        person = m.group(1).strip()
    summary = _SCHEDULE_RE.sub("", msg)
    summary = re.sub(r"\s+", " ", summary).strip(" .")
    if person and person.lower() not in summary.lower():
        summary = f"{summary} with {person}".strip()
    if not summary:
        summary = "Meeting"
    if len(summary) > 80:
        summary = summary[:77] + "..."
    return {
        "summary": summary,
        "person_name": person,
        "person_email": None,
        "start_iso": start.isoformat() if start else None,
        "duration_minutes": duration,
        "description": "",
    }


async def extract_event_fields(msg: str) -> dict[str, Any]:
    parsed = fallback_parse(msg)
    settings = get_settings()
    if not settings.anthropic_key_present:
        return parsed
    try:
        from src.integrations.claude import complete, parse_json_object

        today = datetime.now(_tz()).strftime("%A %Y-%m-%d %H:%M %Z")
        raw = await complete(
            system=(
                "Return ONLY JSON with keys: summary, person_name, person_email, "
                "start_iso (ISO 8601), duration_minutes, description. "
                "Use null for unknown. Infer future datetimes from the user timezone."
            ),
            user=f"Today is {today}. Parse this scheduling request:\n{msg}",
            max_tokens=300,
        )
        data = parse_json_object(raw)
        for key in (
            "summary",
            "person_name",
            "person_email",
            "start_iso",
            "duration_minutes",
            "description",
        ):
            value = data.get(key)
            if value not in (None, "", []):
                parsed[key] = value
    except Exception as exc:
        logger.debug("calendar parse fell back: {}", type(exc).__name__)
    return parsed


def _resolve_start(parsed: dict[str, Any], msg: str) -> datetime | None:
    start_iso = parsed.get("start_iso")
    if isinstance(start_iso, str) and start_iso:
        try:
            dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    else:
        dt = None
    if dt is None:
        fb = fallback_parse(msg)
        if fb.get("start_iso"):
            dt = datetime.fromisoformat(str(fb["start_iso"]))
    if dt is None:
        return None
    dt = dt.replace(tzinfo=_tz()) if dt.tzinfo is None else dt.astimezone(_tz())
    now = datetime.now(_tz())
    if dt < now:
        dt = dt + timedelta(days=1)
    return dt


async def maybe_handle(msg: str) -> dict[str, Any] | None:
    from src.agents._base import is_inbox_capture

    if is_inbox_capture(msg) and not _REMIND_RE.search(msg):
        return None
    pending = pa.peek_pending()
    if pending and pending.kind == "create_event" and is_yes_no(msg):
        return await _handle_confirmation(msg, pending)

    kind = classify_calendar_turn(msg)
    if kind == "organize":
        return await _handle_organize()
    if kind == "mail":
        return await _handle_mail()
    if kind == "agenda":
        return await _handle_agenda(msg)
    if kind == "remind":
        return await _handle_schedule(msg, reminder=True)
    if kind == "schedule":
        return await _handle_schedule(msg)
    return None


async def _handle_confirmation(msg: str, pending: pa.PendingAction) -> dict[str, Any]:
    if _NO_RE.match(msg):
        pa.consume_pending()
        return {
            "reply": "Cancelled — nothing was added to Google Calendar or the vault.",
            "obsidian_path": None,
            "intent": "general",
            "pending_calendar": None,
        }
    action = pa.consume_pending()
    if not action:
        return {
            "reply": "Nothing is waiting to add. Ask me to schedule something first.",
            "obsidian_path": None,
            "intent": "general",
        }
    return await _do_create_event(action.payload)


async def _handle_schedule(msg: str, *, reminder: bool = False) -> dict[str, Any]:
    if not _google_ready():
        return {
            "reply": _connect_reply(),
            "obsidian_path": None,
            "intent": "general",
        }

    if reminder:
        start_dt = _parse_when(msg, default_hour=9)
        summary = reminder_summary(msg)
        duration = 15
        description = summary
        person_name = None
        person_email = None
    else:
        parsed = await extract_event_fields(msg)
        start_dt = _resolve_start(parsed, msg)
        summary = str(parsed.get("summary") or "Meeting")
        duration = int(parsed.get("duration_minutes") or 30)
        description = str(parsed.get("description") or "")
        person_name = parsed.get("person_name")
        person_email = parsed.get("person_email")
    if not start_dt:
        missing = (
            "I need a day for this reminder. "
            "Try: remind me on October 20 at 9am to pray and eat nonveg."
            if reminder
            else (
                "I need a day and time to put this on the calendar. "
                "Try: schedule coffee with Sarah Tuesday at 3pm."
            )
        )
        return {
            "reply": missing,
            "obsidian_path": None,
            "intent": "general",
        }

    payload = {
        "summary": summary,
        "person_name": person_name,
        "person_email": person_email,
        "start_iso": start_dt.isoformat(),
        "duration_minutes": duration,
        "description": description,
        "reminder": reminder,
    }
    pa.set_pending("create_event", payload, ttl_minutes=30 if reminder else 5)
    card = _pending_card(payload)
    if reminder:
        used_default = not _CLOCK_RE.search(msg)
        default_note = " I used 9:00 AM because no time was given." if used_default else ""
        reply = (
            f"Reminder: **{summary}** on {card['when']}.{default_note} "
            "Your iPhone alerts you from Google Calendar, so turn on notifications "
            "for the Calendar app. Tap Add reminder. Nothing is added until you do."
        )
    else:
        person_note = f" with {person_name}" if person_name else ""
        reply = (
            f"Add **{summary}**{person_note} to Google Calendar on {card['when']} "
            f"({duration} min)? This goes on your calendar only — not the vault — "
            "until you later approve a note in Review."
        )
    return {
        "reply": reply,
        "obsidian_path": None,
        "intent": "general",
        "pending_calendar": card,
    }


async def _handle_agenda(msg: str) -> dict[str, Any]:
    if not _google_ready():
        return {
            "reply": _connect_reply(),
            "obsidian_path": None,
            "intent": "general",
        }
    hours = 24 * 7 if re.search(r"\bweek\b", msg, re.I) else 24
    return await list_agenda_reply(hours=hours)


def _format_event_when(start: dict[str, Any]) -> str:
    raw = str(start.get("dateTime") or start.get("date") or "")
    if not raw:
        return ""
    if "T" not in raw:
        return f"{raw} (all day)"
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    local = dt.astimezone(_tz())
    return local.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")


def _google_failure(exc: Exception, *, what: str, enable_url: str) -> str:
    text = str(exc)
    if "has not been used" in text or "accessNotConfigured" in text:
        return (
            f"{what} is not enabled for this Google Cloud project. "
            f"Open {enable_url} and click Enable, then ask again."
        )
    logger.warning("{} failed: {}", what, type(exc).__name__)
    return f"Couldn't reach {what}. Check Settings → Connect Google."


def _no_google() -> dict[str, Any]:
    return {
        "reply": _connect_reply(),
        "obsidian_path": None,
        "intent": "general",
    }


async def list_agenda_reply(*, hours: int = 24) -> dict[str, Any]:
    from src.integrations.google_calendar import GoogleCalendarClient

    window = "the next 7 days" if hours > 24 else "the next day"
    try:
        client = GoogleCalendarClient()
        raw = await client.list_upcoming_events(hours=hours)
    except Exception as exc:
        return {
            "reply": _google_failure(
                exc,
                what="Google Calendar",
                enable_url="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
            ),
            "obsidian_path": None,
            "intent": "general",
        }
    if not raw:
        return {
            "reply": f"Nothing on the calendar for {window}. Want to add something?",
            "obsidian_path": None,
            "intent": "general",
        }
    lines = [
        f"Here's what's coming up for {window}. "
        "This is read from Google Calendar and is not filed in the vault:\n"
    ]
    for ev in raw[:12]:
        summary = ev.get("summary") or "(no title)"
        when = _format_event_when(ev.get("start") or {})
        lines.append(f"- **{summary}** — {when}")
    if len(raw) > 12:
        lines.append(f"\n{len(raw) - 12} more not shown.")
    return {
        "reply": "\n".join(lines),
        "obsidian_path": None,
        "intent": "general",
    }


async def _handle_mail() -> dict[str, Any]:
    if not _google_ready():
        return _no_google()
    messages, err = await _unread_messages()
    if err:
        return {"reply": err, "obsidian_path": None, "intent": "general"}
    return {
        "reply": _format_mail(messages),
        "obsidian_path": None,
        "intent": "general",
    }


async def _handle_organize() -> dict[str, Any]:
    if not _google_ready():
        return _no_google()
    agenda = await list_agenda_reply(hours=24 * 7)
    messages, err = await _unread_messages()
    mail = err or _format_mail(messages or [])
    reply = (
        f"{agenda['reply'].rstrip()}\n\n{mail}\n\n"
        "Nothing was filed. Say “remember this” to save a takeaway, "
        "or “schedule …” and tap Add to calendar before an event is created. "
        "I can read mail. I will not send it."
    )
    return {"reply": reply, "obsidian_path": None, "intent": "general"}


async def _unread_messages() -> tuple[list[dict] | None, str | None]:
    from src.integrations.google_gmail import GmailClient

    try:
        client = GmailClient()
        return await client.list_unread_important(max_results=8), None
    except Exception as exc:
        return None, _google_failure(
            exc,
            what="Gmail",
            enable_url="https://console.cloud.google.com/apis/library/gmail.googleapis.com",
        )


def _format_mail(messages: list[dict]) -> str:
    if not messages:
        return "No unread inbox mail. Mail stays in Gmail — I do not send or delete it."
    lines = [
        "Unread inbox (read-only — nothing is sent, deleted, or filed):\n"
    ]
    for msg in messages[:8]:
        subj = msg.get("subject") or "(no subject)"
        who = msg.get("from") or msg.get("from_email") or "Unknown"
        snippet = (msg.get("snippet") or "").replace("\n", " ")[:140]
        lines.append(f"- **{subj}** — {who}")
        if snippet:
            lines.append(f"  _{snippet}_")
    return "\n".join(lines)


async def _do_create_event(payload: dict[str, Any]) -> dict[str, Any]:
    from src.integrations.google_calendar import GoogleCalendarClient

    if not _google_ready():
        return {
            "reply": _connect_reply(),
            "obsidian_path": None,
            "intent": "general",
        }
    start_dt = datetime.fromisoformat(payload["start_iso"])
    end_dt = start_dt + timedelta(minutes=int(payload["duration_minutes"]))
    attendees = [payload["person_email"]] if payload.get("person_email") else []
    try:
        client = GoogleCalendarClient()
        created = await client.create_event(
            summary=payload["summary"],
            start=start_dt,
            end=end_dt,
            description=str(payload.get("description") or ""),
            attendees=attendees,
            popup_minutes=0 if payload.get("reminder") else None,
        )
    except Exception as exc:
        logger.warning("create_event failed: {}", type(exc).__name__)
        return {
            "reply": (
                "Failed to create the Google Calendar event. "
                "Nothing was written to the vault."
            ),
            "obsidian_path": None,
            "intent": "general",
        }
    html = created.get("htmlLink") if isinstance(created, dict) else None
    extra = f" [Open]({html})" if html else ""
    when = _format_when(start_dt, int(payload["duration_minutes"]))
    if payload.get("reminder"):
        reply = (
            f"Reminder set: **{payload['summary']}** ({when}).{extra} "
            "Google Calendar will notify your iPhone then. "
            "In the iPhone Settings app, turn on notifications for Calendar."
        )
    else:
        reply = (
            f"Added **{payload['summary']}** to Google Calendar ({when}).{extra} "
            "It is not in the vault. Paste a takeaway later if you want a wiki note."
        )
    return {
        "reply": reply,
        "obsidian_path": None,
        "intent": "general",
        "pending_calendar": None,
    }
