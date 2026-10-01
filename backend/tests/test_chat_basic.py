"""Basic chatbot loop: routing, auth, handle_message, Inbox capture."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from src.agents._base import is_inbox_capture, is_inbox_thought_dump
from src.config.settings import get_settings
from src.integrations.obsidian import (
    DAILY_NOTE_DIR,
    UNSORTED_DIR,
    ObsidianClient,
    _assert_writable,
    classify_log_type,
)
from src.orchestrator.graph import _classify_node, handle_message


def _fake_openai(content: str = "Hey — got it."):
    class _Msg:
        def __init__(self, text: str) -> None:
            self.content = text

    class _Choice:
        def __init__(self, text: str) -> None:
            self.message = _Msg(text)

    class _FakeResp:
        def __init__(self, text: str) -> None:
            self.choices = [_Choice(text)]

    async def fake_create(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeResp(content)

    fake_client = AsyncMock()
    fake_client.chat.completions.create = fake_create
    return fake_client


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    profile = root / "Career" / "Profile"
    profile.mkdir(parents=True)
    (root / "Context").mkdir()
    (profile / "skills.md").write_text("# Skills\nPython\n", encoding="utf-8")
    (root / "Context" / "career.md").write_text("User-owned routing notes.\n", encoding="utf-8")
    # API key set the way production .env is — capture must still use the
    # vault folder. No mock Local REST API server.
    monkeypatch.setenv("OBSIDIAN_API_KEY", "test-not-a-live-key")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


# ── Classify / routing ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_always_general() -> None:
    out = await _classify_node({"user_message": "what should I cook for fun tonight"})
    assert out["intent"] == "general"


@pytest.mark.asyncio
async def test_classify_ignores_friends_names() -> None:
    for msg in (
        "Ross what's new",
        "Monica I had eggs",
        "Chandler what's on today",
        "Rachel interview prep",
        "Phoebe weekend ideas",
    ):
        out = await _classify_node({"user_message": msg})
        assert out["intent"] == "general"


# ── Capture detection ──────────────────────────────────────────────────────────


def test_inbox_capture_phrases() -> None:
    assert is_inbox_capture("remember this: I like oat milk")
    assert is_inbox_capture("write this down — dentist Friday")
    assert is_inbox_capture("add to inbox: buy oat milk")
    assert not is_inbox_capture("what's a good walk idea")
    assert not is_inbox_thought_dump("remember this article https://example.com/x")
    assert not is_inbox_thought_dump("remember this pdf for later")


# ── Vault write contract ───────────────────────────────────────────────────────


def test_protected_paths_refused() -> None:
    with pytest.raises(PermissionError, match="protected"):
        _assert_writable("Career/Profile/skills.md")
    with pytest.raises(PermissionError, match="protected"):
        _assert_writable("Context/career.md")
    for path in (
        "01-Knowledge/Notes/x.md",
        "02-Health/Logs/2026-09.md",
        "03-Finance/Logs/2026-09.md",
        "04-People/Sarah.md",
        "05-Calendar/event.md",
    ):
        with pytest.raises(PermissionError, match="protected"):
            _assert_writable(path)
    _assert_writable("00-Inbox/Daily/2026-09-30.md")
    _assert_writable("00-Inbox/Unsorted/raw.md")
    _assert_writable("99-System/Logs/2026-09-30.md")


def test_classify_log_type_heuristic() -> None:
    assert classify_log_type("I ate eggs this morning") == "food"
    assert classify_log_type("spent 20 on groceries") == "finance"
    assert classify_log_type("idea: empathy at scale") == "idea"
    assert classify_log_type("todo email Sarah") == "task"
    assert classify_log_type("meeting with Sarah at 3") == "task"
    assert classify_log_type("30 min workout at the gym") == "exercise"
    assert classify_log_type("30 min walk") == "exercise"
    assert classify_log_type("I like oat milk") is None
    assert classify_log_type("I ate lunch then spent $20") is None


@pytest.mark.asyncio
async def test_append_to_inbox_writes_under_log(vault: Path) -> None:
    skills = vault / "Career" / "Profile" / "skills.md"
    context = vault / "Context" / "career.md"
    before_skills = skills.read_text(encoding="utf-8")
    before_context = context.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    daily = vault / DAILY_NOTE_DIR / f"{today}.md"
    daily.parent.mkdir(parents=True)
    prior = (
        f"---\ntype: daily\ndate: {today}\ncreated: {today}T07:00\nmood:\nenergy:\n---\n\n"
        f"# {today}\n\n"
        "## Log\n"
        "- 07:00 💡 **idea** :: keep this line [src:: user]\n\n"
        "## Notes\n"
        "do not touch\n\n"
        "## Review\n"
        "- [ ] Triage captures\n"
    )
    daily.write_text(prior, encoding="utf-8")

    async with ObsidianClient() as client:
        path = await client.append_to_inbox("I ate eggs this morning", source="user")
        with pytest.raises(PermissionError):
            await client.write_note("Career/Profile/skills.md", "hacked")
        with pytest.raises(PermissionError):
            await client.append_to_note("Context/career.md", "hacked")
        for blocked in (
            "01-Knowledge/Notes/x.md",
            "02-Health/Logs/x.md",
            "03-Finance/Logs/x.md",
            "04-People/x.md",
            "05-Calendar/x.md",
        ):
            with pytest.raises(PermissionError):
                await client.write_note(blocked, "hacked")

    assert path == f"{DAILY_NOTE_DIR}/{today}.md"
    body = (vault / path).read_text(encoding="utf-8")
    assert "- 07:00 💡 **idea** :: keep this line [src:: user]" in body
    assert "do not touch" in body
    assert "**food**" in body
    assert "eggs this morning" in body
    assert "[src:: user]" in body
    assert "## Notes" in body
    assert body.index("eggs this morning") < body.index("## Notes")
    assert skills.read_text(encoding="utf-8") == before_skills
    assert context.read_text(encoding="utf-8") == before_context


@pytest.mark.asyncio
async def test_append_failure_logs_to_system(vault: Path) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    async with ObsidianClient() as client:
        real_put = client._backend.put
        real_append = client._backend.append

        async def fake_put(path: str, content: str) -> None:
            if str(path).startswith("99-System/Logs"):
                await real_put(path, content)
                return
            raise OSError("inbox write failed")

        async def fake_append(path: str, content: str) -> None:
            if str(path).startswith("99-System/Logs"):
                await real_append(path, content)
                return
            raise OSError("inbox write failed")

        with (
            patch.object(client._backend, "get", side_effect=OSError("inbox read failed")),
            patch.object(client._backend, "put", fake_put),
            patch.object(client._backend, "append", fake_append),
            pytest.raises(OSError),
        ):
            await client.append_to_inbox("I ate eggs this morning")

    log = vault / "99-System" / "Logs" / f"{today}.md"
    assert log.exists()
    assert "append_to_inbox failed" in log.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_append_to_inbox_unsorted_when_unparseable(vault: Path) -> None:
    async with ObsidianClient() as client:
        path = await client.append_to_inbox("I like oat milk", source="user")

    assert path.startswith(f"{UNSORTED_DIR}/")
    body = (vault / path).read_text(encoding="utf-8")
    assert "I like oat milk" in body
    today = datetime.now().strftime("%Y-%m-%d")
    daily = vault / DAILY_NOTE_DIR / f"{today}.md"
    assert not daily.exists()


@pytest.mark.asyncio
async def test_handle_message_walk_capture_uses_daily(vault: Path) -> None:
    with patch("openai.AsyncOpenAI", return_value=_fake_openai("Noted.")):
        result = await handle_message("remember this: 30 min walk")

    today = datetime.now().strftime("%Y-%m-%d")
    expected = f"{DAILY_NOTE_DIR}/{today}.md"
    assert result["obsidian_path"] == expected
    assert "Local REST API" not in (result.get("reply") or "")
    body = (vault / expected).read_text(encoding="utf-8")
    assert "## Log" in body
    assert "**exercise**" in body
    assert "30 min walk" in body
    assert not (vault / "02-Health").exists()


@pytest.mark.asyncio
async def test_handle_log_workout_uses_inbox_not_health_folder(vault: Path) -> None:
    from src.agents.health import handle_log_workout

    result = await handle_log_workout("I did 30 min yoga this morning", None)  # type: ignore[arg-type]

    today = datetime.now().strftime("%Y-%m-%d")
    expected = f"{DAILY_NOTE_DIR}/{today}.md"
    assert result["obsidian_path"] == expected
    assert "Local REST API" not in result["reply"]
    assert "Saved to" in result["reply"]
    body = (vault / expected).read_text(encoding="utf-8")
    assert "## Log" in body
    assert "**exercise**" in body
    assert "30 min yoga" in body
    assert not (vault / "02-Health").exists()


@pytest.mark.asyncio
async def test_handle_message_capture_uses_daily(vault: Path) -> None:
    with patch("openai.AsyncOpenAI", return_value=_fake_openai("Noted.")):
        result = await handle_message("remember this: idea — empathy at scale")

    today = datetime.now().strftime("%Y-%m-%d")
    expected = f"{DAILY_NOTE_DIR}/{today}.md"
    assert result["intent"] == "general"
    assert result["obsidian_path"] == expected
    body = (vault / expected).read_text(encoding="utf-8")
    assert "## Log" in body
    assert "**idea**" in body
    assert "empathy at scale" in body
    skills = (vault / "Career" / "Profile" / "skills.md").read_text(encoding="utf-8")
    context = (vault / "Context" / "career.md").read_text(encoding="utf-8")
    assert skills == "# Skills\nPython\n"
    assert context == "User-owned routing notes.\n"


@pytest.mark.asyncio
async def test_handle_message_unparseable_goes_unsorted(vault: Path) -> None:
    with patch("openai.AsyncOpenAI", return_value=_fake_openai("Noted.")):
        result = await handle_message("remember this: I like oat milk")

    assert result["obsidian_path"]
    assert str(result["obsidian_path"]).startswith(f"{UNSORTED_DIR}/")
    assert "I like oat milk" in (vault / str(result["obsidian_path"])).read_text(
        encoding="utf-8"
    )
    skills = (vault / "Career" / "Profile" / "skills.md").read_text(encoding="utf-8")
    context = (vault / "Context" / "career.md").read_text(encoding="utf-8")
    assert skills == "# Skills\nPython\n"
    assert context == "User-owned routing notes.\n"


@pytest.mark.asyncio
async def test_handle_message_plain_chat_skips_inbox(vault: Path) -> None:
    with patch("openai.AsyncOpenAI", return_value=_fake_openai("Try a loop around the park.")):
        result = await handle_message("what's a good walk idea")

    assert result["intent"] == "general"
    assert result["obsidian_path"] is None
    daily = vault / "00-Inbox" / "Daily"
    unsorted = vault / "00-Inbox" / "Unsorted"
    assert not daily.exists() or not any(daily.iterdir())
    assert not unsorted.exists() or not any(unsorted.iterdir())


@pytest.mark.asyncio
async def test_handle_message_reads_today_daily_note(vault: Path) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    daily = vault / DAILY_NOTE_DIR / f"{today}.md"
    daily.parent.mkdir(parents=True)
    daily.write_text(
        f"# {today}\n\n## Log\n- 08:00 🍽 **food** :: leftover oats [src:: user]\n",
        encoding="utf-8",
    )
    captured: dict = {}

    class _Msg:
        def __init__(self, text: str) -> None:
            self.content = text

    class _Choice:
        def __init__(self, text: str) -> None:
            self.message = _Msg(text)

    class _FakeResp:
        def __init__(self, text: str) -> None:
            self.choices = [_Choice(text)]

    async def fake_create(**kwargs):  # type: ignore[no-untyped-def]
        captured["messages"] = kwargs["messages"]
        return _FakeResp("You already logged leftover oats.")

    fake_client = AsyncMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await handle_message("what did I log for breakfast?")

    assert result["intent"] == "general"
    system = captured["messages"][0]["content"]
    assert "leftover oats" in system
    assert "00-Inbox/Daily" in system


@pytest.mark.asyncio
async def test_handle_message_friends_names_stay_general(vault: Path) -> None:
    with (
        patch("openai.AsyncOpenAI", return_value=_fake_openai()),
        patch(
            "src.agents.career.handle_chat",
            AsyncMock(side_effect=AssertionError("career agent must not run")),
        ),
        patch(
            "src.agents.knowledge.run",
            AsyncMock(side_effect=AssertionError("knowledge agent must not run")),
        ),
    ):
        result = await handle_message("Rachel what should I work on next")
    assert result["intent"] == "general"
    assert result.get("obsidian_path") is None
    today = datetime.now().strftime("%Y-%m-%d")
    assert not (vault / "01-Knowledge").exists()
    daily = vault / DAILY_NOTE_DIR / f"{today}.md"
    assert not daily.exists()


# ── Auth + SSE chat handler ────────────────────────────────────────────────────


def test_chat_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api import main as api_main

    monkeypatch.setattr(api_main.settings, "environment", "production")
    monkeypatch.setattr(api_main.settings, "app_api_token", "test-token")
    with pytest.raises(HTTPException) as exc:
        api_main.require_token(None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        api_main.require_token("Bearer wrong")
    api_main.require_token("Bearer test-token")


@pytest.mark.asyncio
async def test_chat_sse_handler_mocked() -> None:
    from src.api.main import ChatRequest, chat
    from src.services import chat_history as chat_store
    from src.storage.models import ChatMessage, ChatSession  # noqa: F401

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    async def fake_handle(
        message: str,
        attachments: list | None = None,
        chat_history: list | None = None,
        *,
        session_id: str | None = None,
    ) -> dict:
        return {
            "user_message": message,
            "reply": "mocked reply",
            "intent": "general",
            "obsidian_path": None,
        }

    with (
        Session(engine) as db,
        patch("src.api.main.handle_message", fake_handle),
    ):
        response = await chat(ChatRequest(message="hello there"), db)
        chunks: list[str] = []
        async for item in response.body_iterator:
            if isinstance(item, bytes):
                chunks.append(item.decode())
            elif isinstance(item, dict):
                chunks.append(f"event: {item.get('event')}\ndata: {item.get('data')}\n")
            else:
                chunks.append(str(item))

    body = "".join(chunks)
    assert "event: session_id" in body
    assert "event: status" in body
    assert "event: message" in body
    assert "mocked reply" in body
    assert "event: intent" in body
    assert "general" in body
    assert "event: done" in body

    with Session(engine) as db:
        sessions = chat_store.list_sessions(db)
        assert len(sessions) == 1
        msgs = chat_store.list_messages(db, sessions[0].id)
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[1].content == "mocked reply"
