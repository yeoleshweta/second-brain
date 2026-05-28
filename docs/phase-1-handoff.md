# Phase 1 — Ross (Knowledge Agent) — handoff to Cursor Composer

**You (Cursor) are being asked to implement Phase 1 of this project.** This is a substantial phase — read the entire file before writing any code, then read the files it references, then implement the stages in order. Verify at each checkpoint and commit at the end.

This supersedes the original Phase 1 spec (which used the name "Pensieve" and was scoped narrower). The agent is now named **Ross**, the reading list lives in SQLite with an Obsidian mirror, the app is reachable from mobile via Tailscale, and the daily brief is a curated 3-item digest instead of a long ranked list.

---

## 0. Naming and personality

The Knowledge Agent is **Ross**. Use this name in:
- Every chat reply the agent emits (e.g., `"🪄 Ross saved 'Mamba…' to your reading list."`)
- The sidebar label in `frontend/src/components/Sidebar.tsx` — change "Knowledge" to "Ross". Keep an emoji like 🪄 or 📚.
- The morning-brief note headers (`# Ross's Morning Brief — YYYY-MM-DD`)
- Any greeting / introduction text

Internally, the file is still `backend/src/agents/knowledge.py`, the intent string is still `"knowledge"`, and the module's exported function is still `async def run(state)`. Do NOT rename module files or the intent enum (it ripples through router.py, graph.py, and the frontend's agent list). Only the user-facing label changes.

Ross's voice: friendly, concise, mildly nerdy. Doesn't pretend to have feelings. Uses second person ("your reading list"). When uncertain, asks rather than guesses.

---

## 1. Goal

By the end of this phase the app does five things it didn't before:

1. **Explicit save** — user says `"save in notes <URL>"` (or any recognized save phrase). Ross fetches, summarizes, dedupes, and writes to a real reading list (SQLite + Obsidian mirror).
2. **Reading list management** — user can ask to see the list, mark items as read (with optional % progress), and delete items. A new view in the frontend shows the same list with the same actions.
3. **On-demand digest** — `"what's new in AI?"` returns a markdown bullet list of recent items in chat. Nothing saved.
4. **Ross's Morning Brief** — at 06:00 local time, Ross writes a curated 3-item brief to `00-Inbox/Daily/YYYY-MM-DD-Ross.md` and posts a notification at the top of the chat history. The three items are: (a) one trending AI news/article/paper, (b) one unique fact or interesting research, (c) one recent tool or technology.
5. **Mobile access via Tailscale + PWA** — user installs Tailscale on Mac + phone, opens `http://<mac-name>:5173` in iPhone Safari, installs the app to the home screen via PWA. A real icon, full-screen, splash screen, offline-capable shell.

### Important departure from Phase 0 default

In Phase 0, every chat message hits an agent's `stub_run`, which captures the message to `00-Inbox/Daily/<today>.md`. **Ross breaks this default.** When intent is `knowledge`:
- If the message contains a recognized save command → save to reading list.
- Otherwise → reply in chat only. Do not write to Obsidian. Do NOT fall back to `stub_run`.

The other three agents (Health, Finance, Calendar) keep their Phase 0 stub behavior — that changes in their respective phases.

---

## 2. Acceptance criteria (Phase 1 is "done" when ALL true)

### Save and reading list

1. **Save with URL:** User types `"save in notes https://arxiv.org/abs/2312.00752"`. Within ~5s, Ross replies `"🪄 Ross saved 'Mamba: Linear-Time Sequence Modeling…' to your reading list."` and the item appears in both:
   - SQLite table `reading_list_items` (status=`unread`, progress=0)
   - `~/Documents/SecondBrain/01-Knowledge/To-Read/mamba-linear-time-sequence-modeling.md` (mirror file with YAML frontmatter)
2. **Save freeform:** User types `"save this: revisit BAML for structured output"` (no URL). Ross saves it as a freeform note (no fetch, no summary), generates a title via `gpt-4o-mini`, persists in DB + mirror file.
3. **Dedup:** Saving the same URL a second time replies `"You already have this in your list (saved YYYY-MM-DD). Marking it unread again? (reply 'yes' or skip)"` — DO NOT insert a duplicate row. (For Phase 1, just reply with the "already saved" message and don't actually re-add. Confirmation flow can be Phase 3.)
4. **List the list:** User types `"show my reading list"` or `"what's in my reading list"`. Ross replies with a markdown bullet list: `**Title** (source · status · 45%)` for each unread/in-progress item. Done items omitted. If empty: `"Your reading list is empty. Save something with 'save in notes <url>'."`
5. **Mark as read:** User types `"mark Mamba as read"` (matches title fuzzily). Ross sets status=`read`, sets `finished_at=now`, moves the mirror file from `01-Knowledge/To-Read/` to `01-Knowledge/Archive/`, replies `"📚 Marked 'Mamba: Linear-Time…' as read. 3 of 12 done (25%)."`
6. **Update progress:** User types `"I'm 50% done with Mamba"` (or just `"50% Mamba"`). Ross sets progress=50, status=`in_progress`, replies with current state.
7. **Delete:** User types `"delete Mamba"` or `"remove Mamba from list"`. Ross hard-deletes the DB row AND deletes the mirror file. Replies `"🗑️ Deleted 'Mamba…' from your list."` (User explicitly asked: "make sure to delete something once finished reading" — interpret as: delete is a separate explicit action, and "mark as read" archives rather than deletes. If user wants automatic delete on read, they'll say so later.)

### Reading list UI (frontend)

8. **List view exists.** A new route `/reading` (or a sidebar tab) shows all items with status `unread` and `in_progress`. Each row shows: title (clickable to open URL in new tab), source, status badge, progress bar.
9. **Per-item actions:** each row has buttons for "Mark read", "Edit progress", "Delete". Clicking them calls the corresponding backend endpoint and updates the UI optimistically.
10. **Header stats:** the top of the view shows `📚 N items · M read (P%)` — total saved-ever count, finished count, and overall progress percentage.
11. **Responsive:** the layout works at iPhone widths (e.g., 390px) — sidebar collapses into a top hamburger, list rows stack cleanly, buttons are touch-sized (min 44x44 px).

### On-demand digest

12. **`what's new in AI?`** — markdown bullet list, 5–10 items, chat-only, nothing written.

### Morning Brief

13. **Scheduled run:** APScheduler `AsyncIOScheduler` started in FastAPI's `lifespan`, cron at `hour=6, minute=0`. Job calls `build_morning_brief()`.
14. **Curation:** The brief contains EXACTLY 3 items in this order — (1) Trending in AI, (2) Interesting fact / research, (3) Recent tool / tech. LLM picks the best candidate from each bucket using all of RSS + arXiv + Tavily as input.
15. **Output:** Writes to `~/Documents/SecondBrain/00-Inbox/Daily/YYYY-MM-DD-Ross.md`. Structure:
    ```markdown
    # Ross's Morning Brief — YYYY-MM-DD
    
    *Curated by Ross at HH:MM.*
    
    ## 🔥 Trending in AI
    
    **[Title](url)** — *source · date*
    
    2–3 sentence summary written by the LLM, not just the raw blurb.
    
    ## 🧠 Interesting fact / research
    
    **[Title](url)** — *source · date*
    
    Same.
    
    ## 🛠️ New tool / tech
    
    **[Title](url)** — *source · date*
    
    Same.
    ```
16. **Manual trigger for testing:** `POST /api/jobs/morning-brief` (auth-protected) runs the same function on demand. Returns 200 + the file path. The brief is also added to the chat as a system-style message visible at the top of the next conversation load (frontend reads the latest brief file via a new endpoint and shows it as a banner / pinned message — see step in stage 7).

### Mobile access

17. **Tailscale instructions delivered.** A new file `docs/mobile-access.md` walks the user through installing Tailscale on Mac, signing up, installing on phone, finding the Mac's MagicDNS name (e.g., `shwetas-macbook-pro.tail-XXXX.ts.net`), and accessing `http://<name>:5173` from the phone.
18. **Backend listens on 0.0.0.0** (or override via env). Currently `app_host = "127.0.0.1"` in `settings.py` — change default to `"0.0.0.0"`. Token-gated already, so the security model is the same. Add a comment explaining this is required for Tailscale.
19. **Frontend talks to backend over Tailscale automatically.** Currently `VITE_API_URL=http://localhost:8000` (hardcoded). Update `frontend/src/lib/api.ts` so `API_BASE` falls back to `${window.location.protocol}//${window.location.hostname}:8000` when `VITE_API_URL` is not set. Then REMOVE `VITE_API_URL` from `.env` so the frontend uses the dynamic value. Confirm desktop access still works (localhost:5173 → localhost:8000) and phone access works (<mac>:5173 → <mac>:8000).
20. **CORS allows Tailscale hostnames.** Currently `allow_origins=[settings.frontend_origin]` (one origin). Change to accept the same hostname on port 5173 regardless of which interface (use a regex via `allow_origin_regex`).

### Backend health

21. All Phase 0 stubs (Health, Finance, Calendar) still route correctly and capture to inbox. Nothing in Phase 1 breaks Phase 0.
22. `cd backend && uv run pytest -v` — all tests green.
23. All Phase 1 code committed and pushed.

---

## 3. Architecture and what's already in place

### Files Cursor will touch

| File | Status | Action |
|---|---|---|
| `backend/src/storage/models.py` | Exists, has stub | Add `ReadingListItem` SQLModel + Alembic migration |
| `backend/src/storage/__init__.py` | Empty | Export models, init engine, session factory |
| `backend/src/agents/knowledge.py` | Stub | Rewrite as Ross |
| `backend/src/scheduler/__init__.py` | Empty | APScheduler setup + lifespan helpers |
| `backend/src/api/main.py` | Working | Add reading-list endpoints, brief endpoint, lifespan, 0.0.0.0 host, CORS regex |
| `backend/src/config/settings.py` | Working | Default `app_host` to `0.0.0.0`, add comment |
| `backend/src/integrations/knowledge_sources.py` | Has helpers | Use as-is (`fetch_rss`, `search_arxiv`, `search_tavily`) |
| `backend/src/integrations/obsidian.py` | Working | Use as-is, plus add `delete_note(path)` method if not present |
| `frontend/src/components/Sidebar.tsx` | Working | Add reading list nav item, rename Knowledge → Ross |
| `frontend/src/components/ReadingList.tsx` | New file | New view |
| `frontend/src/lib/api.ts` | Working | Dynamic `API_BASE`, add reading-list methods |
| `frontend/src/App.tsx` | Working | Add route or tab switcher |
| `frontend/src/index.css` (or tailwind config) | Working | Responsive breakpoints |
| `frontend/.env` | Working | Remove `VITE_API_URL` (rely on dynamic) |
| `frontend/package.json` | Working | Add `vite-plugin-pwa` |
| `frontend/vite.config.ts` | Working | Add `VitePWA` plugin config |
| `frontend/public/manifest.webmanifest` | New | PWA manifest |
| `frontend/public/icons/` | New | Icon set: 192, 512, maskable, apple-touch-icon |
| `frontend/index.html` | Working | Add iOS PWA meta tags |
| `docs/mobile-access.md` | Exists | Already written by Phase 1 prep step. Append a "Install as PWA" subsection. |

### Existing helpers worth reusing

- `KnowledgeItem` dataclass and `fetch_rss / search_arxiv / search_tavily` in `knowledge_sources.py`.
- `ObsidianClient` in `obsidian.py` — methods: `get_note(path)`, `create_note(path, content)` (PUT, overwrites), `append_to_note(path, content)` (POST, appends), `append_to_inbox(message, source)`.
- `AsyncOpenAI` pattern from `orchestrator/router.py` (use `gpt-4o` for main, `gpt-4o-mini` for cheap).

### Jina Reader for URL extraction (no new dep)

```python
import httpx
async def fetch_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
        r.raise_for_status()
        return r.text[:20000]
```

If Jina fails, save the item with just the URL + a stub title (`urlparse(url).path` or domain). Don't block the save on a fetch error.

### Reading list schema (SQLite via SQLModel)

```python
from datetime import datetime
from enum import StrEnum
from sqlmodel import SQLModel, Field

class ItemStatus(StrEnum):
    UNREAD = "unread"
    IN_PROGRESS = "in_progress"
    READ = "read"

class ItemKind(StrEnum):
    URL = "url"           # web article, blog, anything with a URL
    PAPER = "paper"       # arxiv or other
    NOTE = "note"         # freeform text save (no URL)

class ReadingListItem(SQLModel, table=True):
    __tablename__ = "reading_list_items"
    id: int | None = Field(default=None, primary_key=True)
    url: str | None = Field(default=None, index=True, unique=True)  # null for freeform notes
    title: str
    summary: str | None = None
    source: str | None = None   # domain or "arxiv" or "note"
    kind: ItemKind = ItemKind.URL
    tags: str = ""              # comma-separated; simple is fine for v1
    status: ItemStatus = ItemStatus.UNREAD
    progress: int = 0           # 0–100
    saved_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    mirror_path: str | None = None   # path to the markdown file in vault, relative
```

Use the existing `DATABASE_URL=sqlite:///./data/secondbrain.db` from `.env`. Create the table on startup with `SQLModel.metadata.create_all(engine)` — skip Alembic for this phase (Phase 5 will introduce it for finance).

### Mirror file format

Path: `01-Knowledge/To-Read/<slug>.md` (slug = lowercased, hyphenated, max 60 chars of the title).

Content:
```markdown
---
id: 42
url: https://arxiv.org/abs/2312.00752
source: arxiv
kind: paper
status: unread
progress: 0
saved_at: 2026-05-27T18:00
tags: [llm, mamba, state-space]
---

# Mamba: Linear-Time Sequence Modeling…

*arxiv · saved 2026-05-27*

2–3 sentence summary here.
```

When status transitions to `read`, MOVE the file to `01-Knowledge/Archive/<slug>.md` (write new, delete old). When the item is deleted, delete the file entirely. Keep DB and files in sync on every state change.

---

## 4. Implementation plan — stages

Execute stages in order. After each stage, verify the listed checkpoint before moving on.

### Stage 1 — Storage layer

1. Write `backend/src/storage/models.py` with the `ReadingListItem` model above.
2. In `backend/src/storage/__init__.py`, expose:
   - `engine` (SQLModel engine from `settings.database_url`)
   - `init_db()` — calls `SQLModel.metadata.create_all(engine)`. Idempotent.
   - `get_session()` — yields a `Session`. Use as FastAPI dependency.
3. In `backend/src/api/main.py`, call `init_db()` once in the lifespan startup.

**Checkpoint:** `uv run python -c "from src.storage import init_db, engine; init_db(); print('OK')"` prints `OK` and creates `backend/data/secondbrain.db`.

### Stage 2 — Reading list service

Create `backend/src/services/reading_list.py` (new directory `services/`). Module-level functions, each taking a `Session`:

- `add(session, *, url=None, title, summary=None, source=None, kind, tags="") -> ReadingListItem | None` — inserts; returns `None` if URL already exists (caller decides what to say).
- `list_active(session) -> list[ReadingListItem]` — returns unread + in_progress, ordered by `saved_at` desc.
- `list_all(session) -> list[ReadingListItem]` — for stats.
- `find_by_title(session, query) -> ReadingListItem | None` — fuzzy match on title (use `lower` + `LIKE %query%`; if multiple matches return the most recent).
- `mark_read(session, item) -> ReadingListItem` — set status, finished_at.
- `update_progress(session, item, pct) -> ReadingListItem` — clamp 0–100, set in_progress if 0<pct<100.
- `delete(session, item) -> None`.
- `stats(session) -> dict` — `{total, read, in_progress, unread, percent_done}`.

**Checkpoint:** add a quick pytest in `tests/test_reading_list.py` that adds two items, asserts dedup on duplicate URL, marks one read, calls `stats()` and asserts `percent_done == 50`.

### Stage 3 — Ross agent

Rewrite `backend/src/agents/knowledge.py`. Top-level `run(state)` does:

1. Extract `msg = state["user_message"]`.
2. Sub-intent via heuristics (no LLM):
   - `is_save_command(msg)` — regex below — wins over everything.
   - else if `is_list_command(msg)` — `"show my (reading )?list"`, `"what's in my (reading )?list"`, `"reading list"` (case-insensitive).
   - else if `is_mark_command(msg)` — `"mark .* as read"`, `"finished reading .+"`, `"i (just )?finished .+"`. Capture the target title.
   - else if `is_progress_command(msg)` — `"\d+%\s.+"` or `"i'm \d+% done with .+"`. Capture pct + title.
   - else if `is_delete_command(msg)` — `"delete .+ from (my )?list"`, `"remove .+ from (my )?list"`. Capture target title.
   - else if `is_digest_command(msg)` — `"what's new"`, `"any new"`, `"latest"`, `"new papers"`, etc.
   - else if `is_summarize_command(msg)` — contains URL + words like `"summarize"`, `"tldr"`, `"what does this say"`.
   - else → `chat` (LLM reply, no save).
3. Dispatch to handler. Each handler returns the standard agent dict: `{"reply": "...", "obsidian_path": "..."}` (path is optional).

Save phrase regex:
```python
import re
SAVE_RE = re.compile(
    r"\b(save in notes|save this|save it|save to (notes|list|reading list)|"
    r"bookmark this|bookmark it|add to (reading list|notes|list)|"
    r"remember this|file this)\b",
    re.IGNORECASE,
)
```

Bare `"save"` does NOT trigger. So `"save me from this meeting"` falls to `chat`.

**Handlers:**

- `handle_save(msg, session, obsidian)`:
  - Strip the save phrase from `msg` (so it doesn't pollute the title/summary).
  - URL detection: `urls = re.findall(r'https?://\S+', msg)`.
  - If URL present: fetch via Jina, call `gpt-4o` with `response_format={"type": "json_object"}` to get `{title, summary, tags}`. Compose source from URL domain. `kind = "paper"` if arxiv.org in URL else `"url"`.
  - If no URL: body is the stripped message. Use `gpt-4o-mini` to make a short title (≤60 chars). No summary, no fetch. `kind = "note"`.
  - Call `reading_list.add(...)`. If returns `None` (dedup), reply `"Already in your list (saved <date>). Want to re-add? Reply 'yes' to confirm."` (no actual re-add for v1).
  - On success: write mirror file via `obsidian.create_note(mirror_path, frontmatter_md)`. Update DB row's `mirror_path`. Reply `"🪄 Ross saved '<title>' to your reading list."` and return `obsidian_path=mirror_path`.
- `handle_list(session)`:
  - `items = reading_list.list_active(session)`. If empty: reply with the empty-list message above.
  - Format as markdown bullet list. Include stats line at top: `📚 N total · M read (P%)`. Return.
- `handle_mark_read(target_title, session, obsidian)`:
  - `item = reading_list.find_by_title(session, target_title)`. If None: reply `"Couldn't find anything matching '<query>' in your list. Try 'show my reading list' to see what's there."`.
  - `reading_list.mark_read(session, item)`.
  - Move mirror file: read from `01-Knowledge/To-Read/<slug>.md`, write to `01-Knowledge/Archive/<slug>.md`, delete original. Update `item.mirror_path`.
  - Reply with stats: `"📚 Marked '<title>' as read. <m> of <n> done (<p>%)."`
- `handle_progress(target_title, pct, session)`:
  - Find item, `reading_list.update_progress(session, item, pct)`. Reply `"Got it — <title> at <pct>%."`. Also update the frontmatter in the mirror file (rewrite it).
- `handle_delete(target_title, session, obsidian)`:
  - Find item. Delete mirror file if exists. `reading_list.delete(session, item)`. Reply `"🗑️ Deleted '<title>' from your list."`
- `handle_digest_now()` — same as the original Phase 1 spec: parallel fetch RSS + arXiv, dedupe by URL, sort by date, take 10, format as bullet list with a Ross intro line. No save.
- `handle_summarize_url(url)` — fetch via Jina, gpt-4o for 3-paragraph summary. No save.
- `handle_chat(msg)` — `gpt-4o-mini` with this system prompt: `"You are Ross, the knowledge curator in a personal AI second-brain app. The user is chatting about ideas, articles, research, or learning. Reply briefly (2-4 sentences). Do not pretend to save anything — if they want something saved, they need to say 'save in notes', 'save this', etc. Don't summarize from your training data — be candid when you'd need to look something up."`

**Checkpoint:** in the chat UI, send `"save in notes https://arxiv.org/abs/2312.00752"`. Verify reply, verify SQLite row, verify mirror file exists. Then `"show my reading list"` — see the bullet. Then `"mark Mamba as read"` — see the status change and the file move to Archive.

### Stage 4 — API endpoints

Add to `backend/src/api/main.py` (all behind `Depends(require_token)`):

- `GET /api/reading-list` → returns `{items: [...], stats: {...}}`. Query params: `?status=unread,in_progress` (comma-separated, default = unread+in_progress).
- `GET /api/reading-list/stats` → `{total, read, in_progress, unread, percent_done}`.
- `PATCH /api/reading-list/{id}` → body `{status?: str, progress?: int}` → updates and syncs mirror.
- `DELETE /api/reading-list/{id}` → hard delete + remove mirror.
- `POST /api/jobs/morning-brief` → runs `build_morning_brief()` synchronously, returns the file path.
- `GET /api/morning-brief/latest` → returns the most recent brief's markdown content + date, for the frontend banner.

Use `Annotated[Session, Depends(get_session)]` for DB access.

**Checkpoint:** curl each endpoint with the token. Confirm 200 + reasonable payload.

### Stage 5 — Scheduler and morning brief

1. In `backend/src/scheduler/__init__.py`:
   ```python
   from apscheduler.schedulers.asyncio import AsyncIOScheduler
   from apscheduler.triggers.cron import CronTrigger
   
   _scheduler: AsyncIOScheduler | None = None
   
   def start_scheduler(jobs: list[tuple[str, callable, CronTrigger]]):
       global _scheduler
       _scheduler = AsyncIOScheduler()
       for job_id, fn, trigger in jobs:
           _scheduler.add_job(fn, trigger, id=job_id, replace_existing=True)
       _scheduler.start()
   
   def stop_scheduler():
       if _scheduler: _scheduler.shutdown(wait=False)
   ```

2. In `main.py`, replace direct `FastAPI(...)` with the `lifespan` pattern. In startup, call `init_db()` and `start_scheduler([("morning_brief", build_morning_brief, CronTrigger(hour=6, minute=0))])`. In shutdown, call `stop_scheduler()`.

3. `build_morning_brief()` (put in `agents/knowledge.py` or a new `backend/src/jobs/morning_brief.py`):
   - Fetch candidates: `fetch_rss(...)`, `search_arxiv("LLM OR language model OR diffusion OR agent", 10)`, `search_tavily("AI tools 2026 OR new LLM benchmark", 5)`. Run concurrently with `asyncio.gather`.
   - Deduplicate by URL across all sources.
   - Send the candidate list (titles + sources + dates + first 200 chars) to `gpt-4o` with this prompt:
     ```
     You are Ross, curating a 3-item morning brief for the user.
     From the candidates below, pick EXACTLY 3 items, one per category:
     - "trending": one trending AI news article, announcement, or research paper
     - "interesting": one unique fact, surprising research finding, or "did you know" item
     - "tool": one new or notable tool, library, or technology
     
     For each pick, write a 2-3 sentence summary (NOT just the source blurb — write fresh prose).
     Return JSON: {trending: {url, title, source, date, blurb}, interesting: {...}, tool: {...}}
     
     CANDIDATES:
     <numbered list>
     ```
     with `response_format={"type": "json_object"}`.
   - Render Markdown per the structure in acceptance criteria #15 above.
   - Write via `obsidian.create_note("00-Inbox/Daily/YYYY-MM-DD-Ross.md", content)`.
   - Log success/failure to `logs/app.log` with timestamps.

**Checkpoint:** `curl -X POST http://127.0.0.1:8000/api/jobs/morning-brief -H "Authorization: Bearer $TOKEN"` returns 200, file appears in Obsidian, file has all 3 sections with non-empty content.

### Stage 6 — Frontend: reading list view

1. Update `frontend/src/lib/api.ts`:
   - `API_BASE = import.meta.env.VITE_API_URL || \`${window.location.protocol}//${window.location.hostname}:8000\`` (dynamic per host).
   - Add `getReadingList()`, `updateItem(id, patch)`, `deleteItem(id)`, `getMorningBriefLatest()`.

2. Remove `VITE_API_URL` line from `frontend/.env` (so the dynamic fallback kicks in).

3. New file `frontend/src/components/ReadingList.tsx`:
   - Fetches `/api/reading-list` on mount + every 30s (poll, simplest).
   - Renders header: `📚 <total> items · <read> read (<p>%)` with a visible progress bar.
   - List rows: title (link, opens in new tab), source pill, status badge, per-item progress bar, action buttons: "Read", "Edit %", "Delete". Each calls the API and refetches.
   - Empty state: instructions on how to save.

4. Update `Sidebar.tsx`:
   - Rename "Knowledge" → "Ross" (keep emoji).
   - Add a nav item "📚 Reading list" that switches the main panel from chat to the ReadingList component.

5. Update `App.tsx` to handle the panel switch (simple `view` state: `'chat' | 'reading'`).

6. Banner for latest morning brief: in `App.tsx` (chat view), on mount call `getMorningBriefLatest()`. If a brief exists for today, render it as a dismissible card at the top of the chat panel.

**Checkpoint:** save 2 items via chat. Switch to Reading List view. See both. Mark one as read — disappears from active list. See stats update.

### Stage 7 — Mobile responsive + Tailscale

1. **Responsive CSS.** The app uses Tailwind. Audit each component:
   - Sidebar: `md:flex hidden md:w-60` and a hamburger button on mobile that toggles a slide-over.
   - Main: `flex-1` with `px-2 md:px-6`.
   - Chat input: full width, sticky to bottom, large tap target.
   - Reading list rows: stack on `<md`, side-by-side on `≥md`.
   - All buttons: `min-h-[44px] min-w-[44px]` to meet touch targets.
   - Test at 390px width (iPhone), 768px (iPad), 1280px (laptop).

2. **Backend on 0.0.0.0.** In `backend/src/config/settings.py`, change `app_host: str = "127.0.0.1"` to `app_host: str = "0.0.0.0"`. Add comment: `# 0.0.0.0 so Tailscale-routed traffic can reach the server. Token-gated.`. The user's existing `.env` overrides with `APP_HOST=127.0.0.1` — Cursor should also remove that line (or change to 0.0.0.0) since user is opting into mobile access.

3. **CORS regex.** Replace:
   ```python
   allow_origins=[settings.frontend_origin],
   ```
   with:
   ```python
   allow_origin_regex=r"http://(localhost|127\.0\.0\.1|[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*):5173",
   ```
   (Permissive — local hostnames + Tailscale MagicDNS names. Fine for a single-user local app.)

4. **Write `docs/mobile-access.md`** with concrete steps:
   - Install Tailscale: `brew install --cask tailscale && open /Applications/Tailscale.app`.
   - Sign up (free tier), enable MagicDNS in admin console.
   - Note the Mac's MagicDNS name (something like `shwetas-macbook-pro`).
   - Install Tailscale app on iPhone (App Store), sign in with same account.
   - On the Mac, ensure backend + frontend are both running.
   - On the phone, open Safari → `http://shwetas-macbook-pro:5173`.
   - Troubleshooting section: how to test the backend reachable from the phone (`http://shwetas-macbook-pro:8000/api/health` should return JSON), what to do if firewall blocks, how to use Tailscale's own funnel for over-the-internet access.

**Checkpoint:** open `http://localhost:5173` on the Mac — works. Tailscale up. Open `http://<mac-magic-dns>:5173` on the phone — works. Send a chat message from the phone. Reading list view loads on the phone.

### Stage 8 — Smoke tests

Add to `tests/test_reading_list.py` and `tests/test_knowledge.py`:
- `is_save_command("save in notes: ...")` → True; `"save me from this meeting"` → False.
- `classify_sub_intent` for each handler type returns the right key.
- Reading list: add, dedup, mark_read, delete, stats — all work.
- (Optional, marked `@pytest.mark.integration`) `build_morning_brief()` writes a file with 3 sections.

`cd backend && uv run pytest -v` — all green.

### Stage 9 — PWA (installable app on iPhone)

This stage turns the frontend into a true Progressive Web App so the user can install it to their iPhone home screen with a real icon, splash screen, and full-screen mode.

**1. Install the plugin:**
```bash
cd ~/Documents/Projects/second-brain/frontend
npm install -D vite-plugin-pwa
```

**2. Configure Vite (`frontend/vite.config.ts`):**

Add the PWA plugin import and config. Critical: the service worker must NEVER cache `/api/*` requests (especially the SSE stream — caching it would break chat).

```ts
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'Second Brain',
        short_name: 'Brain',
        description: 'Your personal AI second brain. Save, recall, learn.',
        theme_color: '#0b0d12',
        background_color: '#0b0d12',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: /\/api\/.*/i,
            handler: 'NetworkOnly',
            method: 'GET',
            options: { cacheName: 'api-never-cached' },
          },
        ],
      },
      devOptions: {
        enabled: true,  // dev-time PWA support so we can test on iPhone before build
      },
    }),
  ],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5173,
    host: true,  // bind 0.0.0.0 so Tailscale can reach Vite
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
```

Note `server.host: true` — this makes Vite bind to all interfaces, not just localhost, so the iPhone over Tailscale can hit it.

**3. Generate icons:**

Cursor doesn't need to design custom artwork — use placeholders that look acceptable and the user can replace later with proper icons. Generate three PNGs:

- `frontend/public/icons/icon-192.png` — 192×192, dark background `#0b0d12`, a centered 🧠 emoji rendered at ~60% size (use Python + Pillow if needed). White or `#7aa2f7` accent.
- `frontend/public/icons/icon-512.png` — same design at 512×512.
- `frontend/public/icons/icon-maskable-512.png` — same content but with extra padding (icon fills only the inner ~80% so iOS / Android can mask it into a circle / squircle without clipping).
- `frontend/public/icons/apple-touch-icon.png` — 180×180, same design.

You can generate these with a one-shot Python script using Pillow (already a dep — used by `receipt_ocr.py`). Add the script to `frontend/scripts/gen-icons.py` so the user can regenerate later if they want a different design.

**4. Update `frontend/index.html`** with iOS-specific tags (vite-plugin-pwa injects most of this for Android, but iOS needs explicit tags):

```html
<head>
  <!-- existing tags -->
  <meta name="theme-color" content="#0b0d12">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Brain">
  <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
</head>
```

**5. Test the PWA install (manual):**

a. Build: `npm run build && npm run preview` — confirm `dist/manifest.webmanifest` and `dist/sw.js` exist.

b. Run the dev server (`npm run dev`) — vite-plugin-pwa's `devOptions.enabled: true` makes PWA features work in dev too.

c. From the iPhone (with Tailscale up), open the frontend URL in Safari. Tap the Share button → "Add to Home Screen". The dialog should show the "Brain" name and the icon you generated.

d. After installing, tap the home-screen icon. App should launch full-screen, no Safari chrome, with a black status bar.

e. Open Safari's Web Inspector (Mac → Safari → Develop → [iPhone] → [the PWA tab]) and confirm:
   - `navigator.serviceWorker.controller` is non-null
   - `caches.keys()` shows the workbox precache + `api-never-cached` (empty)
   - In the Network tab, an `/api/chat` request shows status 200 with "from network" (not "from sw")

**6. Update `docs/mobile-access.md`** with a new section after "Add to iPhone home screen":

```markdown
### Installing as a PWA (better experience)

After Phase 1's Stage 9, the app is a true PWA — when you "Add to Home Screen" you'll get:

- A custom **Second Brain** icon (not just a screenshot of the page)
- A splash screen when launching
- Full-screen mode (no Safari address bar)
- Faster reloads (the UI shell is cached, only chat data hits the network)

To install: open the URL in Safari → tap Share → "Add to Home Screen". That's it.

To update later: the service worker auto-updates on each visit. If you ever want to force a fresh install, delete the home-screen icon and re-add.
```

**Checkpoint:** Build succeeds. Install on iPhone via Safari. Launch from home screen — full-screen with custom icon. Send a chat message — works (proves SSE isn't being cached by SW).

---

## 5. Manual verification matrix

After implementation, run through every row. All must behave as described.

### Chat behavior

| Message | Expected reply | Writes to Obsidian? | DB write? |
|---|---|---|---|
| `save in notes https://arxiv.org/abs/2312.00752` | `🪄 Ross saved 'Mamba…' to your reading list.` | YES — `01-Knowledge/To-Read/<slug>.md` | YES — insert |
| `save in notes https://arxiv.org/abs/2312.00752` (again) | `Already in your list (saved …)…` | NO | NO (dedup) |
| `save this: try BAML next week` (no URL) | `🪄 Ross saved 'Try BAML next week' to your reading list.` | YES — freeform note file | YES |
| `save me from this meeting` | Conversational reply (chat handler) | NO | NO |
| `show my reading list` | Markdown bullet list w/ stats header | NO | NO |
| `mark Mamba as read` | `📚 Marked 'Mamba…' as read. N of M done (P%).` | YES — file moves to Archive/ | YES — update |
| `I'm 50% done with Mamba` | `Got it — Mamba… at 50%.` | YES — frontmatter rewrites | YES — update |
| `delete Mamba from my list` | `🗑️ Deleted 'Mamba…' from your list.` | YES — file deleted | YES — delete |
| `what's new in AI?` | Bullet list of recent items, prefaced by `🪄 Ross found N fresh items:` | NO | NO |
| `summarize https://arxiv.org/abs/2312.00752` | 3-paragraph summary in chat | NO | NO |
| `what do you think about transformers?` | Brief conversational reply | NO | NO |
| `hey` | Brief greeting | NO | NO |
| `I had eggs for breakfast` | Routes to health agent | YES (health stub, unchanged) | NO |

**Critical check** after running all the above: open `~/Documents/SecondBrain/00-Inbox/Daily/<today>.md`. Should contain ONLY the health-agent entry from the last row. Ross's chat-only replies must NOT leak into the daily inbox. If they do, the `chat` handler is wrong — fix it.

### Reading list view

- Save 3 items. Switch to Reading List view in sidebar.
- See all 3, with progress bars at 0%, status badges "unread".
- Click "Edit %" on one, set to 60%. See badge change to "in progress", bar fill 60%.
- Click "Mark read" on another. Item disappears from list. Stats header updates: `1 of 3 read (33%)`.
- Click "Delete" on the in-progress one. Confirm dialog. Item disappears.

### Morning Brief

- `curl -X POST http://127.0.0.1:8000/api/jobs/morning-brief -H "Authorization: Bearer $(grep '^APP_API_TOKEN=' backend/.env | cut -d= -f2)"` → 200.
- Open `~/Documents/SecondBrain/00-Inbox/Daily/<today>-Ross.md`. Has all 3 sections, each with a real summary (not the raw RSS blurb).
- Reload the chat view in the browser — there's a banner at the top showing today's brief.

### Mobile

- Mac on Tailscale, phone on Tailscale, same account.
- Phone browser → `http://<mac-magic-dns>:5173`. App loads.
- Send a save command from phone — appears in Obsidian on Mac.
- Reading List view on phone — list visible, buttons tappable, layout doesn't wrap weirdly.

### PWA install

- On iPhone Safari, hit the URL. Tap Share → "Add to Home Screen". Dialog shows "Brain" name + custom icon.
- Tap the home-screen icon. App launches full-screen, no Safari chrome.
- Send a chat message. Reply streams in — confirms SSE works through the service worker without being cached.
- Force-quit the app. Reopen. Splash screen briefly visible, then app loads from cached shell.
- Toggle airplane mode. Open the app. UI shell still loads from cache (chat won't work obviously, but the app doesn't show a "no internet" white screen).

---

## 6. Things NOT to do in this phase

- **Don't auto-save chat messages.** Default chat = chat-only.
- **Don't fall back to `stub_run` in the knowledge agent.** The `chat` handler replies in chat, full stop.
- Don't rename `agents/knowledge.py`, the `"knowledge"` intent string, or the module's `run()` function. Only user-facing labels change to "Ross".
- Don't introduce Alembic migrations yet (Phase 5). Just use `SQLModel.metadata.create_all`.
- Don't add multi-turn memory (Phase 3).
- Don't change the OpenAI model defaults.
- Don't introduce React Router unless absolutely needed — a simple `view` state in App.tsx is enough.
- Don't expose anything over the internet without Tailscale (no port forwarding, no ngrok). Tailscale's mesh is the only authorized route.

---

## 7. When you're done

1. Walk through every row of section 5 manually. All pass.
2. `cd backend && uv run pytest -v` — green.
3. Commit and push:
   ```bash
   cd ~/Documents/Projects/second-brain
   git add .
   git commit -m "Phase 1: Ross (knowledge agent) — reading list, morning brief, mobile via Tailscale"
   git push
   ```
4. Confirm commit at `https://github.com/yeoleshweta/second-brain/commits/main`.
5. Write a short summary to me:
   - What you built
   - Any deviations from this spec and why
   - Outstanding issues (e.g., "Tailscale MagicDNS name resolution flaky from Safari — recommend Firefox")
   - Cost notes: roughly how many OpenAI tokens / dollars per typical day of usage

---

## 8. Reference files

Read these before coding:

- `docs/plan.md` — full roadmap, context for Phase 2+
- `docs/architecture.md` — orchestrator/agent topology
- `docs/integrations-cookbook.md` — integration notes
- `docs/phase-0-handoff.md` — what was built in Phase 0 (incl. Anthropic → OpenAI swap)
- `backend/src/integrations/knowledge_sources.py` — RSS / arXiv / Tavily helpers
- `backend/src/integrations/obsidian.py` — ObsidianClient API
- `backend/src/orchestrator/router.py` — pattern for OpenAI calls
- `backend/src/agents/_base.py` — stub_run pattern (DO NOT call it from Ross's `chat` handler)
