# Phase 2 — Chandler (Calendar & Networking Agent) — handoff to Cursor Composer

**You (Cursor) are being asked to implement Phase 2 of this project.** Read this entire file before writing any code, then read the files it references. Implement the stages in order, verify at each checkpoint, commit at the end.

This phase delivers the Calendar / Networking agent named **Chandler**. He handles scheduling, today's agenda, person notes, and contributes to the unified morning brief. The original `docs/plan.md` calls this "Calendar/Networking Agent". User has named him Chandler (in the spirit of Ross from Phase 1).

---

## 0. Naming and personality

The Calendar/Networking Agent is **Chandler**. Use this name in:
- Every chat reply the agent emits (e.g., `"📅 Chandler scheduled 'Coffee with Sarah' for Tue Jun 4 at 3pm."`)
- The sidebar label in `frontend/src/components/Sidebar.tsx` — change "Calendar" to "Chandler". Keep an emoji like 📅 or 🤝.
- The schedule section of the morning brief (`## 📅 Chandler's Schedule`)
- Any greeting / introduction text

Internally, the file is still `backend/src/agents/calendar_agent.py`, the intent string is still `"calendar"`, and the module's exported function is still `async def run(state)`. Do NOT rename module files or the intent enum.

Chandler's voice: dry, organized, slightly sarcastic (in the spirit of the namesake). Always confirms destructive actions. Knows people by name and won't pretend to know more than the notes say.

---

## 1. Goal

By the end of Phase 2 the app does these things it didn't before:

1. **Schedule events with confirmation.** User says `"schedule coffee with Sarah Tuesday at 3pm"`. Chandler parses → replies with proposed event details → user says `"yes"` → event lands in Google Calendar AND in Sarah's person note as a logged interaction.
2. **Show today's agenda.** User says `"what's on today?"`. Chandler lists all events from Google Calendar for the rest of the day, with attendee names and prep notes from each person's file.
3. **Person notes.** Each person mentioned in chat or invited to an event automatically gets a file at `04-People/<First-Last>.md` with structured frontmatter (`name`, `email`, `company`, `role`, `first_contacted`, `last_contacted`, `tags`). User can add freeform notes to the body; Chandler only edits frontmatter and an "Interactions" log section.
4. **"What do I know about X?"** User asks about a person; Chandler reads the file and replies with a summary.
5. **Update a person's info.** User says `"Sarah is now at Anthropic as a Research Engineer"`. Chandler updates Sarah's frontmatter (with confirmation).
6. **Merged morning brief.** Instead of separate Ross / Chandler files, a single `00-Inbox/Daily/YYYY-MM-DD-Brief.md` contains both. At 06:00 the unified job runs both agents' contributions, assembles, writes one file. Both agents are refactored to expose a `morning_section() -> str` function rather than writing files directly.
7. **Sunday stale-contact reminder.** On Sundays at 09:00, Chandler scans `04-People/` for contacts with `last_contacted` > 90 days ago, picks up to 5, appends a "🤝 Reach out this week" section to that day's brief.

### Departure from previous defaults (Chandler-specific)

- **Confirmation flow is multi-turn.** This is the first time we need short-term state across messages: the user's next message after a Chandler proposal must be interpreted as a yes/no on the pending action. We'll do this with a tiny in-memory `pending_actions` dict keyed by session, with a 5-minute TTL. Cleared after consumption. Per the original plan, "real" multi-turn memory is Phase 3 — this is a deliberately scoped subset.
- **Chandler also obeys the "no auto-save chat" rule from Phase 1.** Default chat = chat-only. Only explicit scheduling / contact-update commands write to Obsidian or Google Calendar.

---

## 2. Acceptance criteria (Phase 2 is "done" when ALL true)

### Calendar

1. **First-time OAuth done.** User has run the one-time auth flow per the iPhone setup doc and `backend/secrets/google_token.json` exists. (You — Cursor — verify this; if missing, your code should reply `"Chandler: I'm not connected to Google Calendar yet. Run: cd backend && uv run python -m src.integrations.google_calendar auth"`.)
2. **Schedule with confirmation:**
   - User: `"schedule coffee with Sarah Tuesday at 3pm"`
   - Chandler reply within 3s: `"📅 Confirm: 'Coffee with Sarah' on Tue Jun 4 at 3:00pm (60 min). Reply 'yes' to add or 'no' to cancel."`
   - User: `"yes"` → Chandler creates the Google Calendar event, replies `"✅ Added 'Coffee with Sarah' to your calendar. Also logged to 04-People/Sarah.md."` and updates Sarah's people note.
   - User: `"no"` or no reply within 5 minutes → no event created, pending state cleared.
3. **Today's agenda:**
   - User: `"what's on today?"` (or `"today's agenda"`, `"what do I have today"`)
   - Chandler replies with markdown list: each event shows time range, summary, attendees, and (if known) a one-line prep blurb from each attendee's people note.
   - If nothing scheduled: `"📅 Chandler: nothing on the calendar for the rest of today. Want to add something?"`
4. **No active connection = friendly degradation.** If Google Calendar API is unreachable (network, expired token, etc.) Chandler replies with the actual error message and what to do, not a generic 500.

### Person notes

5. **Person-not-known flow:** User: `"what do I know about Sarah?"`. If `04-People/Sarah*.md` doesn't exist, Chandler replies `"I don't have a note for Sarah yet. Tell me about her: 'Sarah is at Anthropic, works on safety, met at Re:Invent.'"`.
6. **Person creation:** User: `"Sarah Wong works at Anthropic, met at Re:Invent"`. Chandler asks `"📇 New contact: Sarah Wong @ Anthropic. Confirm? (yes/no)"`. On yes, creates `04-People/Sarah-Wong.md` with frontmatter and an initial note. Replies with the path.
7. **Person update:** User: `"Sarah just got promoted to Staff"`. If exactly one match, Chandler asks `"Update Sarah Wong's role to 'Staff'? (yes/no)"`. On yes, edits the frontmatter (preserving the body). If multiple Sarahs, asks which one (`"Which Sarah? 1) Sarah Wong (Anthropic) 2) Sarah Chen (OpenAI)"`).
8. **Person read:** User: `"what do I know about Sarah Wong?"` → Chandler replies with a summary built from the frontmatter and the body's first paragraph.

### Morning brief (unified)

9. **One file per day.** `00-Inbox/Daily/YYYY-MM-DD-Brief.md` contains contributions from both agents. Sections, in order:
   - `## 📅 Chandler's Schedule` (today's events with attendee prep)
   - `## 🪄 Ross's Picks` (the 3-item knowledge brief from Phase 1)
   - `## 🤝 Reach out this week` (Sundays only — stale contacts)
10. **Single scheduler job.** Phase 1's `morning_brief` job is replaced with `combined_morning_brief` at 06:00. It calls `chandler.morning_section()` and `ross.morning_section()`, assembles, writes one file. Old `YYYY-MM-DD-Ross.md` filename is no longer produced.
11. **Refactored Ross.** `agents/knowledge.py`'s `build_morning_brief()` is split: a new function `morning_section() -> str` returns the rendered Markdown (no file write), and `build_morning_brief()` becomes a thin wrapper that calls `morning_section()` and writes the file (kept for `POST /api/jobs/morning-brief` to still work for ad-hoc Ross-only generation).
12. **Manual trigger updated.** `POST /api/jobs/combined-brief` (new) runs the unified job on demand for testing. Old `POST /api/jobs/morning-brief` (Ross-only) is kept as a fallback.

### Sunday reach-out

13. **Sunday cron.** APScheduler has a new job at `day_of_week='sun', hour=9, minute=0` that calls `build_reachout_section()` and APPENDS it to that day's brief file (creates the brief if it doesn't exist).
14. **Selection logic.** Reads all `04-People/*.md` frontmatter, filters where `last_contacted` is more than 90 days ago (or never), sorts by oldest, takes top 5. Outputs as a bullet list with: name, days since last contact, a one-line prompt ("Email them about <last_topic>", "Schedule a coffee").

### General

15. **Existing intents still work.** "I read a paper about Mamba" still routes to Ross; "I had eggs for breakfast" still routes to Health (stub); on-demand digest, save, etc. all still work.
16. **Default chat doesn't write to Obsidian.** Same rule as Phase 1: if Chandler doesn't recognize a calendar/contact intent, the message is replied to in chat only.
17. `cd backend && uv run pytest -v` — all green.
18. Code committed and pushed.

---

## 3. Architecture and what's already in place

### Files Cursor will touch

| File | Status | Action |
|---|---|---|
| `backend/secrets/google_client_secret.json` | User provides | One-time OAuth setup — see Stage 1 |
| `backend/secrets/google_token.json` | Created by OAuth flow | User runs `uv run python -m src.integrations.google_calendar auth` once |
| `backend/src/integrations/google_calendar.py` | Exists, basic | Add `update_event`, `delete_event`, `get_event` |
| `backend/src/integrations/google_people.py` | New | People API client for contact lookup / search |
| `backend/src/agents/calendar_agent.py` | Stub | Rewrite as Chandler |
| `backend/src/storage/models.py` | Has ReadingListItem | Add `PersonRecord` model OR keep people in markdown only (decision in Stage 2) |
| `backend/src/services/people.py` | New | Person CRUD against markdown frontmatter (or DB) |
| `backend/src/services/pending_actions.py` | New | In-memory store for pending confirmations |
| `backend/src/jobs/combined_brief.py` | New | Replaces single-agent brief job. Calls each agent's `morning_section()` and assembles. |
| `backend/src/jobs/reachout.py` | New | Sunday job. |
| `backend/src/agents/knowledge.py` | Phase 1 done | Refactor: extract `morning_section()` from `build_morning_brief()` |
| `backend/src/api/main.py` | Phase 1 done | Add `POST /api/jobs/combined-brief`, update scheduler registration |
| `backend/src/scheduler/__init__.py` | Phase 1 done | Replace `morning_brief` job with `combined_morning_brief` cron + add Sunday `reachout` cron |
| `frontend/src/components/Sidebar.tsx` | Phase 1 done | Rename "Calendar" → "Chandler" |
| `frontend/src/components/Agenda.tsx` | New | Today's agenda view (optional polish — sidebar tab) |

### Helpers already in place

- `GoogleCalendarClient` in `google_calendar.py` — has `list_upcoming_events(hours)` and `create_event(summary, start, end, description, attendees)`. Needs `update_event`, `delete_event`, `get_event` added.
- `ObsidianClient` in `obsidian.py` — `get_note`, `create_note`, `append_to_note`. You'll also need to be able to OVERWRITE notes (for frontmatter updates) — that's `create_note(path, content)` which is PUT (overwrites). For reading the body so you can splice in updates, use `get_note(path)`.
- `ReadingListItem` SQLModel + storage layer (from Phase 1) — pattern to copy if you choose DB-backed people.

### Decision: people in DB or markdown?

For Phase 2 keep people as **markdown-with-frontmatter only**, no DB table. Reasoning:
- Each person already has a hand-maintained note in `04-People/`. The user wants to edit those directly in Obsidian.
- Frontmatter (YAML) is queryable enough for our needs.
- Adding a DB table means dual write + sync, which is hard to keep consistent across "user edits in Obsidian" + "agent edits via API".

Use the `python-frontmatter` library (already common; `pip install python-frontmatter` — add to deps) to read/modify frontmatter while preserving the body.

Frontmatter schema:
```yaml
---
name: Sarah Wong
emails: [sarah@anthropic.com]
company: Anthropic
role: Staff Research Engineer
location: SF Bay Area
tags: [ai-safety, work, met-at-reinvent]
first_contacted: 2025-11-15
last_contacted: 2026-05-20
last_interaction: "Coffee meeting at Sightglass"
---
```

Body: freeform notes — Chandler appends an "## Interactions" section if it doesn't exist, then logs each interaction as a dated bullet.

### Pending confirmations

Tiny in-memory store. Single-user app, so a global dict is fine:
```python
# backend/src/services/pending_actions.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

@dataclass
class PendingAction:
    kind: str               # "create_event" | "create_person" | "update_person" | ...
    payload: dict[str, Any]
    expires_at: datetime

_pending: PendingAction | None = None

def set_pending(kind: str, payload: dict, ttl_minutes: int = 5) -> None:
    global _pending
    _pending = PendingAction(kind, payload, datetime.now() + timedelta(minutes=ttl_minutes))

def consume_pending() -> PendingAction | None:
    global _pending
    if not _pending or _pending.expires_at < datetime.now():
        _pending = None
        return None
    p, _pending = _pending, None
    return p

def peek_pending() -> PendingAction | None:
    global _pending
    if _pending and _pending.expires_at < datetime.now():
        _pending = None
    return _pending
```

In Chandler's `run`, FIRST check for a pending action — if the user's message is a yes/no/cancel and there's a pending action, execute it (or discard). THEN do sub-intent classification.

### Natural language parsing for dates/times

Use the `dateparser` library (lightweight, handles `"Tuesday at 3pm"`, `"next Mon"`, `"tomorrow morning"`, etc.):
```python
import dateparser
dt = dateparser.parse("Tuesday at 3pm", settings={"PREFER_DATES_FROM": "future"})
```

Add `dateparser>=1.2.0` to `backend/pyproject.toml`. Run `uv sync` after.

For ambiguous parses (no time, or year), default to:
- No time → 9:00 AM
- Past time today → next day same time
- Default duration → 30 min (60 min if "coffee" or "lunch" appear in summary)

---

## 4. Implementation plan — stages

### Stage 1 — Google OAuth (user-driven, document it well)

The user does this once before any code calls Google. Cursor should NOT attempt to automate the OAuth flow but should ensure it's documented clearly. Update `docs/phase-2-iphone-setup.md` (which I'll create alongside this spec) to include the Google Cloud + iPhone steps.

**Cursor's job in this stage:**

1. Verify `backend/secrets/google_client_secret.json` exists. If not, write a clean error in any Chandler call: `"Chandler: Google not connected. See docs/phase-2-iphone-setup.md for the one-time setup."`
2. If `backend/secrets/google_token.json` doesn't exist either, the error should also mention: `"Run: cd backend && uv run python -m src.integrations.google_calendar auth"`.
3. After OAuth, the existing `GoogleCalendarClient` constructor will work without errors. Add a `health_check()` method that hits `events().list(maxResults=1)` and returns OK / specific error — wire to `GET /api/integrations/google/health`.

**Checkpoint:** `curl http://127.0.0.1:8000/api/integrations/google/health -H "Authorization: Bearer $TOKEN"` returns `{"status":"ok"}` after the user has done OAuth. Before, it returns a clean error.

### Stage 2 — People service (markdown-backed)

Create `backend/src/services/people.py`:

```python
from pathlib import Path
from datetime import date
import frontmatter
import re
from src.config import get_settings

PEOPLE_DIR = "04-People"  # relative to vault

def _vault_path() -> Path:
    s = get_settings()
    if not s.obsidian_vault_path:
        raise RuntimeError("OBSIDIAN_VAULT_PATH not set")
    return Path(s.obsidian_vault_path) / PEOPLE_DIR

def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-")

def list_all() -> list[dict]:
    """Return list of {filename, frontmatter, body_preview} for every person note."""
    ...

def find(name_query: str) -> list[dict]:
    """Fuzzy match against name in frontmatter. Returns 0–N matches."""
    ...

def create(name: str, **frontmatter_fields) -> Path:
    """Write a new file, return path."""
    ...

def update_frontmatter(file_path: Path, updates: dict) -> None:
    """Read, merge frontmatter, write back. Preserves body."""
    ...

def log_interaction(file_path: Path, summary: str, on_date: date | None = None) -> None:
    """Append a bullet to the '## Interactions' section. Creates section if missing.
    Also updates `last_contacted` and `last_interaction` in frontmatter."""
    ...
```

For frontmatter, use the `python-frontmatter` library — handles parse + write while preserving formatting. Add `python-frontmatter>=1.1.0` to `backend/pyproject.toml`.

**Checkpoint:** Manually create `04-People/Sarah-Wong.md` with frontmatter via Obsidian. Run `uv run python -c "from src.services.people import find; print(find('Sarah'))"` — returns the entry.

### Stage 3 — Pending actions store

Drop in `backend/src/services/pending_actions.py` per the snippet above. Add a unit test that sets a pending action with 1-second TTL, sleeps 2s, calls `consume_pending()` — returns None.

### Stage 4 — Google People API client

Create `backend/src/integrations/google_people.py`. Reuse the existing OAuth token (scope `contacts.readonly` is already in `SCOPES`). Methods:

- `search_contacts(query: str) -> list[dict]` — calls People API `people:searchContacts`. Returns simplified `{name, emails, phones, organization}` dicts.
- `get_contact_by_email(email: str) -> dict | None`.

If a person comes up in a calendar event with an email, try to enrich the people note from Google Contacts before creating it from scratch.

**Checkpoint:** `uv run python -c "import asyncio; from src.integrations.google_people import GooglePeopleClient; print(asyncio.run(GooglePeopleClient().search_contacts('Sarah')))"` returns hits (if any in user's Google Contacts).

### Stage 5 — Chandler agent core

Rewrite `backend/src/agents/calendar_agent.py`. Top of `run(state)`:

```python
async def run(state):
    msg = state["user_message"]
    # 1. Confirmation flow takes precedence
    pending = peek_pending()
    if pending and is_yes_no_or_cancel(msg):
        return await handle_confirmation(msg, pending)
    
    # 2. Sub-intent classification
    intent = classify_chandler_intent(msg)
    return await DISPATCH[intent](msg)
```

Sub-intents:
| Sub-intent | Trigger phrases | Writes? |
|---|---|---|
| `schedule` | `schedule`, `book`, `set up`, `put on (my)? calendar`, `add a meeting`, `create event` | Calendar + people note (on confirm) |
| `agenda` | `what's on today`, `today's agenda`, `agenda`, `what's on this week`, `my schedule` | No |
| `find_person` | `what do I know about <name>`, `info on <name>`, `who is <name>`, `tell me about <name>` | No |
| `update_person` | starts with `<name> is/works/joined/moved/left`, or `update <name>` | People note (on confirm) |
| `add_person` | starts with `<Name> works at`, `met <Name>`, `add <Name> to my contacts` | People note (on confirm) |
| `chat` | anything else | No |

`classify_chandler_intent` uses regex + keyword heuristics (no LLM call for classification — keep it fast and predictable). Use `gpt-4o-mini` only for ambiguous edge cases if needed; prefer to fall to `chat`.

**Handlers:**

- `handle_schedule(msg)`:
  - Use `gpt-4o-mini` with `response_format=json_object` to extract `{summary, person_name?, person_email?, start_iso, duration_minutes, description?}`. Prompt: `"Parse this scheduling request. Today is <today>. Extract: summary (event title), person_name (if explicitly named), start_iso (ISO 8601), duration_minutes (default 30; 60 if 'coffee' or 'lunch' in summary), description (optional). Return JSON."`. Pass the message; pass today's date.
  - If parsing failed → reply `"Chandler: couldn't parse that. Try: 'schedule coffee with Sarah Tuesday at 3pm'."`
  - Format a friendly confirmation reply (`"📅 Confirm: ..."`).
  - Set pending action `{kind: "create_event", payload: parsed_json}`.

- `handle_confirmation(msg, pending)`:
  - If user said yes-like ("yes", "y", "confirm", "do it", "go"): consume pending, execute. Execution depends on `pending.kind`:
    - `create_event`: call `GoogleCalendarClient().create_event(...)`. Find or create the person's note (use `services.people.find` then `create`). Log interaction.
    - `create_person`: call `services.people.create`.
    - `update_person`: call `services.people.update_frontmatter`.
  - If user said no-like ("no", "cancel", "stop"): consume + discard, reply `"Chandler: cancelled."`
  - Otherwise (not yes/no but pending exists): re-prompt: `"Did you want me to do that? Reply yes or no — I'll wait 5 minutes."`

- `handle_agenda(msg)`:
  - Determine window: today by default; "this week" → today through Sunday.
  - `events = await GoogleCalendarClient().list_upcoming_events(hours)`.
  - For each event, find attendees in `04-People/`, build a one-line prep from their last_interaction or role.
  - Render as bullet list. Reply.

- `handle_find_person(msg)`:
  - Extract name. `matches = services.people.find(name)`.
  - 0 → suggest creating; 1 → render frontmatter + body preview; N > 1 → ask which.

- `handle_update_person(msg)` and `handle_add_person(msg)`:
  - Use `gpt-4o-mini` to extract `{name, field, value}` (e.g., `{name: "Sarah", field: "role", value: "Staff"}` or `{name: "Sarah Wong", company: "Anthropic", ...}` for add). Confirm. Set pending.

- `handle_chat(msg)`:
  - `gpt-4o-mini` with system prompt: `"You are Chandler, the calendar and networking agent in a personal AI second brain. The user is chatting casually about scheduling, people, or networking. Reply briefly (2-3 sentences). Do not pretend to schedule or save anything — they need to explicitly ask. Voice: dry, organized, slightly sarcastic. Don't overdo it."`

**Checkpoint:** Run through the manual verification matrix in section 5 (chat half) end-to-end.

### Stage 6 — Refactor Ross + unified morning brief

1. In `agents/knowledge.py`, extract a new function `async def morning_section() -> str`:
   - Does the fetch + LLM ranking + markdown render that today writes to a file
   - Returns the Markdown (header + 3 items), no file write
2. Keep `build_morning_brief()` (now a thin wrapper: `content = await morning_section()` + `await client.create_note(...)`) for the `POST /api/jobs/morning-brief` endpoint backward compat.
3. In `agents/calendar_agent.py`, add `async def morning_section() -> str`:
   - Fetches today's events via `list_upcoming_events(24)`
   - For each event, optionally enriches attendees from people notes
   - Renders `## 📅 Chandler's Schedule` + bullet list
   - Returns Markdown. If no events, returns `## 📅 Chandler's Schedule\n\nNothing scheduled today.`
4. Create `backend/src/jobs/combined_brief.py`:
   ```python
   async def build_combined_brief() -> Path:
       from src.agents import calendar_agent, knowledge
       chandler_md = await calendar_agent.morning_section()
       ross_md = await knowledge.morning_section()
       today = datetime.now().strftime("%Y-%m-%d")
       path = f"00-Inbox/Daily/{today}-Brief.md"
       content = f"# Morning Brief — {today}\n\n*Compiled at {datetime.now():%H:%M}*\n\n{chandler_md}\n\n{ross_md}\n"
       async with ObsidianClient() as c:
           await c.create_note(path, content)
       logger.info("Combined brief written to {}", path)
       return path
   ```
5. In `scheduler/__init__.py`, replace the Ross-only `morning_brief` job with `combined_brief` at 06:00. Keep the function signature for `start_scheduler` the same.
6. New endpoint `POST /api/jobs/combined-brief` calls `build_combined_brief()`. Add to `main.py`. Keep old `POST /api/jobs/morning-brief` as Ross-only fallback.

**Checkpoint:** `curl -X POST http://127.0.0.1:8000/api/jobs/combined-brief -H "Authorization: Bearer $TOKEN"` returns 200. Open `~/Documents/SecondBrain/00-Inbox/Daily/<today>-Brief.md` — has both sections.

### Stage 7 — Sunday reach-out job

1. Create `backend/src/jobs/reachout.py`:
   - `async def build_reachout_section() -> str` — scans `04-People/*.md`, parses frontmatter, filters by `last_contacted` (or never contacted) > 90 days, sorts oldest-first, takes top 5. Renders `## 🤝 Reach out this week` + bullet list.
   - `async def append_reachout_to_brief()` — calls `build_reachout_section`, gets today's brief content via `client.get_note`, appends section, writes back. If brief doesn't exist yet, run `build_combined_brief()` first.
2. Register cron `day_of_week='sun', hour=9, minute=0` in `scheduler/__init__.py` calling `append_reachout_to_brief`.
3. Endpoint `POST /api/jobs/reachout` for manual triggering.

**Checkpoint:** Create 2 test person files with `last_contacted: 2025-01-01` (old). Run the reachout job. Section appears in today's brief file.

### Stage 8 — Frontend polish (optional but nice)

1. Rename "Calendar" to "Chandler" in `Sidebar.tsx`.
2. Add a new "📅 Agenda" tab in the sidebar that switches the main panel to an Agenda view component. Agenda view fetches `GET /api/chandler/agenda` (new endpoint that calls `chandler.handle_agenda` directly and returns JSON) and renders today's events as cards.
3. (Optional) Surface today's brief in the chat panel banner if one exists (the latest-brief endpoint from Phase 1 already shows whatever the latest brief is; should "just work").

### Stage 9 — Smoke tests

`tests/test_chandler.py`:
- `classify_chandler_intent` for each variant.
- Pending-action TTL.
- People service: create, find, update_frontmatter, log_interaction round-trips.
- (Integration) `morning_section()` produces non-empty markdown when calendar is reachable.

`cd backend && uv run pytest -v` — all green.

---

## 5. Manual verification matrix

### Chat behavior

| Message | Expected | Writes to Google Cal? | Writes to Obsidian? |
|---|---|---|---|
| `schedule coffee with Sarah Tuesday at 3pm` | `📅 Confirm: 'Coffee with Sarah' on Tue ... 3:00pm (60 min). Reply 'yes' to add or 'no' to cancel.` | NO (yet) | NO (yet) |
| `yes` (within 5min of above) | `✅ Added 'Coffee with Sarah' to your calendar. Also logged to 04-People/Sarah.md.` | YES | YES (people note + interactions log) |
| `schedule meeting tomorrow morning` | `📅 Confirm: 'Meeting' on <tomorrow> 9:00am (30 min)...` | NO (yet) | NO (yet) |
| `no` (within 5min) | `Chandler: cancelled.` | NO | NO |
| (wait 6 min, then) `yes` | `Chandler: nothing pending to confirm.` | NO | NO |
| `what's on today?` | Bullet list of today's events with attendee prep, or 'nothing scheduled' message. | NO | NO |
| `Sarah Wong works at Anthropic, met at Re:Invent` | `📇 New contact: Sarah Wong @ Anthropic. Confirm? (yes/no)` | NO (yet) | NO (yet) |
| `yes` | `✅ Saved Sarah Wong to 04-People/Sarah-Wong.md` | NO | YES (new file) |
| `what do I know about Sarah Wong?` | Reply summarizing her frontmatter + body. | NO | NO |
| `Sarah just got promoted to Staff` | `Update Sarah Wong's role to 'Staff'? (yes/no)` | NO (yet) | NO (yet) |
| `yes` | `✅ Updated Sarah Wong.` | NO | YES (frontmatter only) |
| `what do you think about Chandler's name?` (random chat) | Brief conversational reply, slightly sarcastic. | NO | NO |
| `save in notes https://...` | Routes to **Ross** (knowledge), unchanged from Phase 1. | NO | YES (reading list) |
| `I had eggs for breakfast` | Routes to **Health stub**, unchanged. | NO | YES (inbox via stub) |

**Critical check:** open `~/Documents/SecondBrain/00-Inbox/Daily/<today>.md`. Should contain only the Phase 0 stub captures (e.g., the eggs message), NOT Chandler's chat replies, agenda renders, or confirmation prompts.

### Morning brief

- `curl -X POST http://127.0.0.1:8000/api/jobs/combined-brief -H "Authorization: Bearer $TOKEN"` → 200.
- Open `~/Documents/SecondBrain/00-Inbox/Daily/<today>-Brief.md`. Has `## 📅 Chandler's Schedule` and `## 🪄 Ross's Picks`.
- Tomorrow at 6:00am — file appears automatically.

### Sunday job

- Create 3 test people files with `last_contacted: 2024-01-01`. Manually trigger: `curl -X POST .../api/jobs/reachout -H "Authorization: Bearer $TOKEN"`.
- Brief file now has a `## 🤝 Reach out this week` section listing the 3.

### Frontend

- Sidebar shows "Chandler" instead of "Calendar".
- (Optional) Agenda tab loads today's events as cards.
- All Phase 1 features (reading list, chat with Ross) still work.

### iPhone

- After completing `docs/phase-2-iphone-setup.md`: Google Calendar events created via Chandler appear in iOS Calendar app within ~1 minute (Google push sync).
- Chat from iPhone PWA: scheduling flow works end-to-end (parse → confirm → create).
- Today's brief banner shows the combined brief at the top of the chat view.

---

## 6. Things NOT to do

- **Don't auto-confirm.** Every action that touches Google Calendar or modifies a people note's frontmatter must go through the pending-confirmation flow.
- **Don't move money or send messages.** This agent does not send calendar invites to external attendees in Phase 2 — it only creates events on the user's own calendar with attendees listed in the description. Sending invites is a follow-up phase.
- **Don't add Alembic.** Same as Phase 1: `metadata.create_all()` is fine; no schema migrations.
- **Don't replace the existing people markdown files** if the user has hand-edited them — only update frontmatter, never overwrite the body without explicit user permission.
- **Don't make the LLM extract dates without `dateparser` as a fallback.** Use `dateparser` first (deterministic, no API call); only fall back to `gpt-4o-mini` if dateparser returns None.
- **Don't introduce real multi-turn memory** beyond the pending-actions hack. Full conversational memory is Phase 3.
- **Don't log full OAuth tokens** anywhere. `creds.to_json()` writes to `secrets/google_token.json` only; never echo it in logs.
- **Don't auto-create people from arbitrary mentions.** Only create when the user explicitly says "add <Name>" or confirms after a scheduling that hit an unknown attendee.

---

## 7. When done

1. Walk through every row of section 5 manually.
2. `cd backend && uv run pytest -v` — green.
3. Commit + push:
   ```bash
   cd ~/Documents/Projects/second-brain
   git add .
   git commit -m "Phase 2: Chandler (calendar + networking) — schedule, people notes, unified brief, Sunday reach-out"
   git push
   ```
4. Confirm commit at `https://github.com/yeoleshweta/second-brain/commits/main`.
5. Write a short summary back to me:
   - What you built
   - Any deviations + why
   - Cost: roughly how many OpenAI tokens / day given typical use
   - Known caveats (e.g., "dateparser misparsed 'next next Monday' — recommend using Google's natural-language event creation in Phase 3")

---

## 8. Reference files

- `docs/plan.md` — Phase 2 source-of-truth
- `docs/architecture.md` — orchestrator/agent topology
- `docs/integrations-cookbook.md` — Google + Plaid notes
- `docs/phase-0-handoff.md`, `docs/phase-1-handoff.md` — what's already done
- `docs/phase-2-iphone-setup.md` — Google OAuth + iOS Calendar / Contacts sync (write this if not already present)
- `backend/src/integrations/google_calendar.py` — existing client + OAuth
- `backend/src/services/reading_list.py` — pattern to copy for service-layer functions
- `backend/src/scheduler/__init__.py` — APScheduler setup from Phase 1
- `backend/src/agents/knowledge.py` (Ross) — pattern for sub-intent + sub-handler dispatch
