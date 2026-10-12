from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.services import calendar_chat as cc
from src.services import pending_actions as pa


@pytest.mark.parametrize(
    "msg",
    [
        "schedule coffee with Sarah Tuesday at 3pm",
        "book a meeting with John tomorrow",
        "put this on my calendar Friday 2pm",
        "add this to my calendar",
        "create an event for lunch Monday",
    ],
)
def test_schedule_intent(msg: str) -> None:
    assert cc.classify_calendar_turn(msg) == "schedule"
    assert cc.skips_vault(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "what's on today?",
        "today's agenda",
        "my schedule",
        "what's on my calendar",
    ],
)
def test_agenda_intent(msg: str) -> None:
    assert cc.classify_calendar_turn(msg) == "agenda"
    assert cc.skips_vault(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "my meetings",
        "upcoming meetings",
        "sync my calendar",
        "this week's meetings",
    ],
)
def test_meeting_phrases_are_agenda(msg: str) -> None:
    assert cc.classify_calendar_turn(msg) == "agenda"
    assert cc.skips_vault(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "unread email",
        "what's in my inbox",
        "check my gmail",
        "sync my email",
    ],
)
def test_mail_intent(msg: str) -> None:
    assert cc.classify_calendar_turn(msg) == "mail"
    assert cc.skips_vault(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "organize my day",
        "sync my meetings",
        "meetings and email",
    ],
)
def test_organize_intent(msg: str) -> None:
    assert cc.classify_calendar_turn(msg) == "organize"
    assert cc.skips_vault(msg) is True


def test_remind_me_on_a_date_is_a_reminder() -> None:
    msg = "remind me on the 20th to pray and eat nonveg"
    assert cc.classify_calendar_turn(msg) == "remind"
    assert cc.skips_vault(msg) is True
    when = cc._parse_when(msg, default_hour=9)
    assert when is not None
    assert when.day == 20
    assert when.hour == 9
    assert when.minute == 0
    assert cc.reminder_summary(msg) == "Pray and eat nonveg"
    mixed = (
        "remember today i ate veg only as navratri has started "
        "so on the 20th remind me to pray and eat nonveg"
    )
    assert cc.reminder_summary(mixed) == "Pray and eat nonveg"


def test_reminder_keeps_an_explicit_time() -> None:
    msg = "remind me on October 20 at 8am to pray"
    when = cc._parse_when(msg, default_hour=9)
    assert when is not None
    assert when.day == 20
    assert when.hour == 8


def test_a_reading_list_is_not_a_calendar_request() -> None:
    msg = (
        "remember these books and resources to read\n"
        "Working minds - book on cognitive analysis\n"
        "Tools - figma notebooklm"
    )
    assert cc.classify_calendar_turn(msg) is None


def test_plain_chat_does_not_skip_vault() -> None:
    pa.clear_pending()
    assert cc.classify_calendar_turn("remember this idea about Tany") is None
    assert cc.skips_vault("remember this idea about Tany") is False
    assert cc.skips_vault("yes") is False


@pytest.mark.asyncio
async def test_schedule_proposes_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)

    async def fake_extract(_msg: str) -> dict:
        start = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=1)
        start = start.replace(hour=15, minute=0, second=0, microsecond=0)
        return {
            "summary": "Coffee with Sarah",
            "person_name": "Sarah",
            "person_email": None,
            "start_iso": start.isoformat(),
            "duration_minutes": 60,
            "description": "",
        }

    monkeypatch.setattr(cc, "extract_event_fields", fake_extract)
    result = await cc.maybe_handle("schedule coffee with Sarah Tuesday at 3pm")
    assert result is not None
    assert result["pending_calendar"]["summary"] == "Coffee with Sarah"
    assert "vault" in result["reply"].lower()
    assert pa.peek_pending() is not None
    assert pa.peek_pending().kind == "create_event"


@pytest.mark.asyncio
async def test_cancel_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)
    start = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=1)
    pa.set_pending(
        "create_event",
        {
            "summary": "Dentist",
            "start_iso": start.isoformat(),
            "duration_minutes": 30,
            "description": "",
        },
    )
    result = await cc.maybe_handle("no")
    assert result is not None
    assert "Cancelled" in result["reply"]
    assert pa.peek_pending() is None


@pytest.mark.asyncio
async def test_confirm_creates_event(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)
    start = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=1)
    pa.set_pending(
        "create_event",
        {
            "summary": "Dentist",
            "start_iso": start.isoformat(),
            "duration_minutes": 30,
            "description": "",
        },
    )

    class FakeClient:
        async def create_event(self, **kwargs: object) -> dict:
            assert kwargs["summary"] == "Dentist"
            return {"htmlLink": "https://calendar.google.com/event"}

    monkeypatch.setattr(
        "src.integrations.google_calendar.GoogleCalendarClient",
        FakeClient,
    )
    result = await cc.maybe_handle("yes")
    assert result is not None
    assert "Added" in result["reply"]
    assert "Google Calendar" in result["reply"]
    assert pa.peek_pending() is None


@pytest.mark.asyncio
async def test_reminder_proposes_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)
    result = await cc.maybe_handle("remind me on the 20th to pray and eat nonveg")
    assert result is not None
    card = result["pending_calendar"]
    assert card["kind"] == "reminder"
    assert card["summary"] == "Pray and eat nonveg"
    assert "9:00 AM" in result["reply"]
    assert "Add reminder" in result["reply"]
    assert pa.peek_pending() is not None
    assert pa.peek_pending().payload["reminder"] is True
    pa.clear_pending()


@pytest.mark.asyncio
async def test_confirm_reminder_sets_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)
    start = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=9)
    start = start.replace(hour=9, minute=0, second=0, microsecond=0)
    pa.set_pending(
        "create_event",
        {
            "summary": "Pray and eat nonveg",
            "start_iso": start.isoformat(),
            "duration_minutes": 15,
            "description": "Pray and eat nonveg",
            "reminder": True,
        },
    )
    seen: dict = {}

    class FakeClient:
        async def create_event(self, **kwargs: object) -> dict:
            seen.update(kwargs)
            return {"htmlLink": "https://calendar.google.com/event"}

    monkeypatch.setattr(
        "src.integrations.google_calendar.GoogleCalendarClient",
        FakeClient,
    )
    result = await cc.maybe_handle("yes")
    assert seen["popup_minutes"] == 0
    assert seen["summary"] == "Pray and eat nonveg"
    assert result is not None
    assert "Reminder set" in result["reply"]
    assert pa.peek_pending() is None


@pytest.mark.asyncio
async def test_organize_reads_calendar_and_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: True)

    async def fake_agenda(*, hours: int = 24) -> dict:
        assert hours == 24 * 7
        return {"reply": "Meetings:\n- **Standup** — Tue Oct 13, 9:00 AM", "intent": "general"}

    async def fake_unread() -> tuple[list[dict], None]:
        return [{"subject": "Invoice", "from": "A", "snippet": "due"}], None

    monkeypatch.setattr(cc, "list_agenda_reply", fake_agenda)
    monkeypatch.setattr(cc, "_unread_messages", fake_unread)
    result = await cc.maybe_handle("organize my day")
    assert result is not None
    assert "Standup" in result["reply"]
    assert "Invoice" in result["reply"]
    assert "will not send" in result["reply"]
    assert result["obsidian_path"] is None
    assert pa.peek_pending() is None


@pytest.mark.asyncio
async def test_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    pa.clear_pending()
    monkeypatch.setattr(cc, "_google_ready", lambda: False)
    result = await cc.maybe_handle("schedule coffee Tuesday at 3pm")
    assert result is not None
    assert "Connect Google" in result["reply"]
    assert pa.peek_pending() is None
