# Architecture

> Read this before making non-trivial changes. Keep it updated as you build.

## High level

```
┌──────────────────────────────────────────┐
│  React UI (Vite + Tailwind, port 5173)   │
│  - Chat surface with SSE streaming       │
│  - File upload                           │
│  - Plaid Link UI                         │
└────────────────┬─────────────────────────┘
                 │ /api/* (Bearer token)
                 ▼
┌──────────────────────────────────────────┐
│  FastAPI (port 8000)                     │
│  - /api/chat      (SSE)                  │
│  - /api/upload                           │
│  - /api/plaid/*                          │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  Orchestrator (LangGraph)                │
│  - classify_intent (Haiku, cheap)        │
│  - route → specialist agent              │
└──┬───┬───┬───┬───────────────────────────┘
   │   │   │   │
   ▼   ▼   ▼   ▼
[Know] [Health] [Finance] [Calendar]
   │      │       │         │
   ▼      ▼       ▼         ▼
┌──────────────────────────────────────────┐
│  Integrations                            │
│  Obsidian · Google · Plaid · Apple       │
│  Health · USDA · Tavily · RSS · arXiv    │
│  · Receipt OCR (Claude vision)           │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│  Obsidian vault (markdown, source of     │
│  truth) + SQLite (structured logs)       │
└──────────────────────────────────────────┘
```

## Key design choices

### 1. Orchestrator is a graph, not a chain
LangGraph means you can add nodes (new agents) without rewriting routing. Each agent is independent — easy to test, replace, or disable.

### 2. Agents are prompts + tools, not separate models
All agents run on the same Claude model. They differ in:
- their `SYSTEM_PROMPT`
- their tool set
- the folder they read/write in Obsidian

This keeps cost down and avoids the "which model for which agent" rabbit hole.

### 3. Obsidian is the source of truth, SQLite is supplemental
Markdown wins for anything you'll want to read by hand. SQLite is for:
- transactions (high volume, structured queries)
- food logs (need aggregation)
- audit trail

Both are local. Both back up via git/iCloud.

### 4. SSE between frontend and backend
The chat endpoint returns Server-Sent Events. Right now we emit the full reply at once, but the wire format is ready for true token streaming when you wire it up later. The frontend's `streamChat` generator handles either case.

### 5. Read-only by default, write with confirmation
Any agent action that's irreversible — create calendar event, send email, move money (no agent moves money) — requires explicit confirmation in chat.

### 6. Single-user, local-only
Auth is a single shared Bearer token between frontend and backend because everything runs on `localhost`. If you ever expose this to the internet, replace with real auth first.

## State model

`AgentState` in `backend/src/orchestrator/graph.py`:

```python
class AgentState(TypedDict, total=False):
    user_message: str
    attachments: list[dict]
    intent: Intent
    reply: str
    obsidian_path: str | None
    metadata: dict
```

Agents read this, do work, and return a partial update. The graph merges updates and emits the final state.

## Where each agent writes

| Agent | Obsidian path | SQLite tables |
|---|---|---|
| Knowledge | `01-Knowledge/`, `00-Inbox/Daily/` | — |
| Health | `02-Health/Food/`, `02-Health/Workouts/`, `02-Health/Groceries/` | `food_entries`, `health_metric_daily` |
| Finance | `03-Finance/Weekly/`, `03-Finance/Monthly/` | `transactions`, `plaid_item` |
| Calendar | `04-People/`, `05-Calendar/` | — |

## Frontend / backend contract

- All routes under `/api/`
- Bearer token in `Authorization` header (matches `APP_API_TOKEN`)
- Chat returns SSE with these event types:
  - `status` — "thinking" indicator
  - `message` — text chunk (may arrive multiple times once token streaming is added)
  - `intent` — which agent handled it (`knowledge`/`health`/...)
  - `obsidian` — path of any note written
  - `done` — end of stream
  - `error` — something failed
- File upload returns `{file_id, path, size, media_type}`; the `file_id` is then referenced in `/api/chat` attachments

## Background jobs (to add)

`backend/src/scheduler/` is wired up but empty. Use APScheduler to run:
- Daily 06:00 — knowledge agent builds AI brief
- Hourly — Plaid sync per linked Item
- Sunday 18:00 — finance agent writes weekly review
- Continuous — Apple Health file watcher

Run the scheduler in the same FastAPI process via `lifespan`, or as a separate `python -m src.scheduler.main`.

## Error handling

- **Integration failure** (e.g. Obsidian unreachable): degrade gracefully — log, tell the user, don't crash.
- **LLM failure**: retry once with backoff. If still failing, fall back to the cheap model.
- **Intent classifier failure**: default to "general" — captures to inbox.

## What's NOT in scope

- Multi-user. The whole thing assumes you, single-user.
- High availability. If your Mac is off, the app is off.
- Realtime sync. Apple Health lags by however often the export app runs.
- Mobile native. The web UI is mobile-responsive but there's no iOS app yet.
