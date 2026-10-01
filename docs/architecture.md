# Second Brain — Architecture

> Read this before making non-trivial changes. Keep it updated as you build.

One bot, one vault, one daily note. Capture fast, structure later. Custom React UI, FastAPI + LangGraph backend, Obsidian markdown as the source of truth. SQLite is cache and chat history only.

This is **not** a multi-agent Friends / Central Perk product. Leftover specialist modules (`backend/src/agents/{knowledge,health,finance,calendar_agent,career}.py`) may still exist on disk. They are unused by the live chat graph.

---

# Vault contract (v1)

Canonical tree (live vault + `docs/vault-contract/`):

```
00-Inbox/Daily/          ← YYYY-MM-DD.md — bot's only structured write
00-Inbox/Unsorted/       ← unparseable / no type; raw text kept
01-Knowledge/{Notes,Sources,MOCs}/
02-Health/{Logs,Reviews}/
03-Finance/{Logs,Reviews}/
04-People/
05-Calendar/
99-System/{Templates,Schemas,Logs,Dashboard.md}
```

Legacy un-numbered `Inbox/` (and `Career/`, `Context/`) stay in the vault. **v1 chat capture writes only `00-Inbox/Daily/`** (or `Unsorted/`). Do not use `Inbox/YYYY-MM-DD.md`.

**Non-negotiables**

1. One capture target: `00-Inbox/Daily/YYYY-MM-DD.md` under `## Log` only. Never write 01–05 on the fly. Unparseable → `00-Inbox/Unsorted/`. Failures → `99-System/Logs/`.
2. Markdown is source of truth. SQLite is cache / chat history only.
3. Structure emerges from human review, not bot filing.
4. Every bot write: timestamp + `src::` ; append-only; corrections are new lines.
5. Five log types only: `food`, `finance`, `idea`, `task`, `exercise`.
6. One agent. No specialist product identity.

**Ownership:** you write `Career/Profile/` and `Context/`, and you file 01–05 during review. The bot appends under `## Log` (never edits existing lines), logs failures to `99-System/Logs/`, and refuses writes to 01–05 / Profile / Context.

Templates live in `99-System/Templates/` and are mirrored under `docs/vault-contract/`.

---

# How chat works

```
UI :5173  →  POST /api/chat (SSE)  →  one Second Brain node
                                      │
                                      ├─ READ today's 00-Inbox/Daily note (if it exists)
                                      └─ optional: append under ## Log (or Unsorted/)
SQLite ← chat turns only
```

**1. Capture.** “remember this…” / “write this down…” is appended via `ObsidianClient.append_to_inbox`. Five log types. Unparseable raw text goes to `00-Inbox/Unsorted/`. Chat never auto-files into 01–05. Failures append to `99-System/Logs/`.

**2. Store.** The vault is what you open and read. SQLite keeps chat history and a few high-volume tables (reading list, food, Plaid).

**3. Classify / file.** Not automatic. The graph always routes to `general`. Filing 01–05 is a later human-review step.

**4. Chat.** One system prompt in `backend/src/agents/second_brain.py`. `POST /api/chat` streams SSE. The bot may read today’s daily note so replies stay relevant. It does not create atomic notes in `01-Knowledge`.

**5. API.** FastAPI on `:8000`. Bearer token (`APP_API_TOKEN`). SSE: `session_id` → `status` → `message` → optional `obsidian` → `intent` (`general`) → `done`. Uploads go through `/api/upload`, then `file_id`.

**6. UI.** React + Vite + Tailwind on `:5173`. One composer. Vite proxies `/api` to the backend. Same token in `VITE_API_TOKEN`. PWA name is **Second Brain**.

Not this slice: Expo offline queue, `POST /capture`, hourly classify/file jobs, Dataview install, or auto-filing into 01–05.

## Request path

1. UI POSTs `/api/chat` (message, last ~10 turns, `session_id`, attachments).
2. FastAPI hydrates last 20 SQLite turns.
3. LangGraph: `classify` always sets `intent=general`, then `second_brain.run`.
4. After the reply, a thought-dump (if the message matches capture phrases) is written to Inbox.
5. SSE: `status` → `message` → optional `obsidian` → `intent` → `done`.

Filesystem vault writes when `OBSIDIAN_VAULT_PATH` is set. Local REST API is optional fallback. Finance tools never move money. Irreversible external writes still need a confirmation gate if those leftover modules are called outside chat.

## Dual store

| What | Where |
|---|---|
| Captures | `00-Inbox/Daily/` under `## Log`, or `00-Inbox/Unsorted/` |
| Domain notes | `01–05` — human review only |
| Profile / routing notes | `Career/Profile/`, `Context/` — you own these |
| Chat history | SQLite |
| High-volume tables | SQLite (`reading_list_items`, `food_entries`, `transactions`, `plaid_item`) |

---

# How it reaches the iPhone

There is no App Store listing. Daily use is a **home-screen PWA** talking to the Mac over Tailscale. Capacitor (`.ipa` sideload) is scaffolded and optional.

**The Mac has to be on.** If it sleeps or leaves Tailscale, the home-screen icon is a dead app.

1. Tailscale on Mac and iPhone, same account, VPN on. MagicDNS hostname (e.g. `shwetas-macbook-pro`).
2. Both servers on the Mac, bound to `0.0.0.0`:
   - backend `:8000`
   - frontend `:5173`
3. Safari (not Chrome) at `http://<mac-name>:5173`
4. Share → **Add to Home Screen** → Second Brain (standalone, custom icon, shell cached).

Vite proxies `/api`, so the phone only needs port 5173. Auth is `Authorization: Bearer <APP_API_TOKEN>`. MagicDNS fail → `http://100.x.x.x:5173`.

The service worker caches the app shell. It does **not** cache API responses and there is no offline queue.

Capacitor (`appId: com.secondbrain.centralperk` — leftover id) has no Vite proxy — `VITE_API_URL` must be a reachable backend.

Google Calendar sync (if connected) is still available from Settings / Agenda. iPhone Calendar is Apple↔Google sync, outside this app.

## Component map

```
iPhone (Safari PWA)
        │  Tailscale
        ▼
Mac — frontend :5173
        │
        ▼
Mac — backend :8000  (FastAPI + LangGraph)
        │
        ├─ one Second Brain node (always general)
        └─ Obsidian client (vault folder on disk; REST optional)
                │
                ▼
        Vault (markdown) + SQLite (chat / cache)
```

| Component | Status |
|---|---|
| FastAPI + SSE chat | Working — one bot |
| React + Vite + Tailwind UI | Working — one composer |
| LangGraph | Working — no specialist routing |
| Leftover specialist modules | Unused by chat |
| Obsidian client | Working; vault-folder writes preferred |
| PWA + Tailscale | Working, Mac-dependent |
| Capacitor wrapper | Scaffolded, not daily |
| Offline capture queue / `POST /capture` | Not built |
| Hourly classifier + filing | Not built |
| Chat ingest (text, images, PDFs, voice) | Working — Whisper + vision before the one bot |
| Talk mode (mic) | Half-duplex. Needs secure context (localhost or HTTPS). iPhone Tailscale **HTTP** PWA cannot use live mic. |
| Spoken replies (TTS) | Working |
| OpenAI key | `OPENAI_API_KEY` in `backend/.env`. Live check: `GET /api/setup/openai`. |

## What is still missing for daily capture

- No offline queue. Mac unreachable = capture fails.
- Conversation and capture are the same request (model before anything is stored).
- Mac-dependent by design.

A later slice can add a phone queue + `POST /capture` without a model call. Not this change.

## Frontend / backend contract

- All routes under `/api/`
- Bearer token = `APP_API_TOKEN`
- Chat SSE events: `session_id`, `status`, `message`, `digest_items`, `suggest_items`, `book_items`, `obsidian`, `intent`, `done`, `error`
- Live chat `intent` is always `general`

## Error handling

- Obsidian down: the bot still chats; capture is skipped and the reply says so if a dump was requested.
- LLM failure: log, short fallback reply, don't crash the graph.
- Protected-path writes raise `PermissionError`.
