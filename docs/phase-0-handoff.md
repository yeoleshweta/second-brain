# Phase 0 — Handoff to Cursor Composer

**You (Cursor) are being asked to finish Phase 0 of this project.** Read this whole file before doing anything. Most of Phase 0 is done. There are a few unverified steps and one unresolved bug. Verify, fix, test, commit.

---

## Goal of Phase 0 (acceptance criteria)

Phase 0 is "done" when ALL of these are true:

1. Run `cd backend && uv run python -m src.api.main` — backend starts on `http://127.0.0.1:8000`, no errors in `backend/logs/app.log`.
2. Run `cd frontend && npm run dev` — frontend serves on `http://localhost:5173`.
3. Open `http://localhost:5173` in a browser. Type "Hello, can you hear me?" and press Enter. Within ~3 seconds:
   - A typing indicator (`...`) appears
   - A reply appears: `(general agent — stub) Captured to \`00-Inbox/Daily/<today>.md\``
   - Below the reply: `Saved to 00-Inbox/Daily/<today>.md`
4. Open the file `~/Documents/SecondBrain/00-Inbox/Daily/<today>.md` — it contains the message with a timestamp.
5. Intent routing works. Test each of these and confirm the reply mentions the correct agent name:
   - `"I read a paper about Mamba architectures"` → `knowledge`
   - `"I had two eggs for breakfast"` → `health`
   - `"I spent $40 on dinner last night"` → `finance`
   - `"Coffee with Sarah next Tuesday"` → `calendar`
6. Both servers stop cleanly with Ctrl+C, no orphan processes.
7. All code changes committed and pushed to `git@github.com:yeoleshweta/second-brain.git`.

---

## State of the world (what's already done)

### Environment
- Homebrew 5.1.8, Python 3.12.7, Node v20.19.3, Git 2.50.1, uv 0.11.x — installed.
- Cursor installed, default model is Claude Sonnet (per Composer).
- Obsidian installed at `/Applications/Obsidian.app`.
- GitHub user `yeoleshweta` set up with ed25519 SSH key (no passphrase) added. `ssh -T git@github.com` returns success.

### Project layout
- Canonical project folder: `~/Documents/Projects/second-brain/`
- Connected to GitHub: `git@github.com:yeoleshweta/second-brain.git` (private)
- `main` branch pushed with commit `Initial scaffold` (sha `f514bb8`)

### Obsidian vault
- Vault at `~/Documents/SecondBrain/`
- Folders created: `00-Inbox/Daily/`, `01-Knowledge/`, `02-Health/`, `03-Finance/`, `04-People/`, `05-Calendar/`, `99-System/`
- Plugin installed + enabled: **Local REST API with MCP v4.1.1** (community plugin by Adam Coddington)
- API listening at `https://127.0.0.1:27124/` (self-signed cert; backend uses `curl -k` equivalent)
- API key is already in `backend/.env` as `OBSIDIAN_API_KEY`

### Backend
- Deps installed via `uv sync` → `.venv` exists, 97 packages.
- `backend/.env` exists with valid `OPENAI_API_KEY` (user's real key, do NOT print it back), `APP_API_TOKEN`, `OBSIDIAN_API_KEY`, `OBSIDIAN_VAULT_PATH=/Users/shwetasharma/Documents/SecondBrain`.
- `backend/logs/` and `backend/data/` directories created.

### Frontend
- Deps installed via `npm install` → `node_modules` exists, 219 packages.
- `frontend/.env` exists with `VITE_API_TOKEN` matching backend's `APP_API_TOKEN`.

### Architectural deviation from the original scaffold
**We swapped the LLM provider from Anthropic to OpenAI.** The original scaffold used `anthropic` SDK with `claude-sonnet-4-5` and `claude-haiku-4-5`. We refactored to:
- `openai` SDK (and `langchain-openai`)
- `gpt-4o` (main) and `gpt-4o-mini` (cheap / intent classifier)

All files affected:
- `backend/pyproject.toml` — dep names
- `backend/.env.example` — env var names + default model names
- `backend/src/config/settings.py` — field names `openai_*`
- `backend/src/orchestrator/router.py` — rewritten with `AsyncOpenAI.chat.completions`
- `backend/src/integrations/receipt_ocr.py` — rewritten with OpenAI vision API + `response_format=json_object`

### Circular import fix
The scaffold had a circular import: `orchestrator/graph.py` → `agents/__init__.py` → each agent module → `agents/_base.py` → `orchestrator/graph.py`. We resolved it by moving `from src.orchestrator.graph import AgentState` under `TYPE_CHECKING` (and converting the annotation to a string) in:
- `backend/src/agents/_base.py`
- `backend/src/agents/knowledge.py`
- `backend/src/agents/health.py`
- `backend/src/agents/finance.py`
- `backend/src/agents/calendar_agent.py`

Backend imports cleanly now: `uv run python -c "from src.api.main import app; print('OK')"` prints `OK`.

---

## Open issue you need to verify or fix

**SSE chat through Vite's proxy returns 503.** The backend works perfectly when hit directly via curl (verified — `POST http://127.0.0.1:8000/api/chat` returns a clean SSE stream with the agent reply, intent, Obsidian path, etc.). But the same request through Vite at `http://localhost:5173/api/chat` returned HTTP 503 from the proxy.

**Fix attempted (uncommitted, just made):**
1. `frontend/src/lib/api.ts` — every `fetch('/api/...')` changed to `fetch(\`${API_BASE}/api/...\`)`, where `API_BASE = import.meta.env.VITE_API_URL || ''`. Empty falls back to the old proxy behavior.
2. `frontend/.env` — added `VITE_API_URL=http://localhost:8000` so the frontend bypasses the Vite proxy entirely and calls the backend directly.

This works because the backend already has CORS configured to allow `http://localhost:5173` (see `backend/src/api/main.py` — `app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], ...)`)

**What you (Cursor) need to do:**
1. Stop the frontend dev server (`pkill -f vite` or Ctrl+C in its terminal).
2. Restart it: `cd ~/Documents/Projects/second-brain/frontend && npm run dev`. Vite loads `VITE_*` env vars at startup; without a restart the new var doesn't take effect.
3. **Hard-refresh** the browser tab (Cmd+Shift+R) — without this, the browser holds onto the cached JS that still calls `/api/chat` relatively.
4. Verify by opening DevTools → Network tab → send a chat message. The request URL should now be `http://localhost:8000/api/chat` (not `http://localhost:5173/api/chat`), and the response should stream as SSE.

If this works, move on. If 503 persists or new CORS errors appear, the next thing to try is updating `vite.config.ts` to extend proxy timeouts:
```ts
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    timeout: 0,
    proxyTimeout: 0,
  },
},
```
And revert the api.ts/`.env` change above.

---

## End-to-end test plan

After the bug above is resolved, run all 5 of these messages in the chat UI and verify each one routes correctly + appears in Obsidian:

| Message | Expected agent | Expected reply prefix |
|---|---|---|
| `Hello, can you hear me?` | general | `(general agent — stub) Captured to ...` |
| `I read a paper about Mamba architectures` | knowledge | `(knowledge agent — stub) Captured to ...` |
| `I had two eggs for breakfast` | health | `(health agent — stub) Captured to ...` |
| `I spent $40 on dinner last night` | finance | `(finance agent — stub) Captured to ...` |
| `Coffee with Sarah next Tuesday` | calendar | `(calendar agent — stub) Captured to ...` |

After all 5 messages are sent, open `~/Documents/SecondBrain/00-Inbox/Daily/<today>.md` (or run `cat ~/Documents/SecondBrain/00-Inbox/Daily/$(date +%Y-%m-%d).md`) and confirm all 5 messages are appended with timestamps.

The intent classifier uses OpenAI's `gpt-4o-mini`. If routing is wrong (e.g. everything goes to `general`), check `backend/logs/app.log` for `Intent classification failed:` warnings — typically means the OpenAI key is invalid or out of credit.

---

## When you're done

```bash
cd ~/Documents/Projects/second-brain
git add .
git commit -m "Phase 0 complete: OpenAI provider, circular-import fix, direct-fetch frontend"
git push
```

Then confirm the new commit appears at `https://github.com/yeoleshweta/second-brain/commits/main`.

---

## Reference commands

```bash
# Start everything fresh (assumes you're at project root)
cd backend && mkdir -p logs data && nohup uv run python -m src.api.main > logs/app.log 2>&1 & ; sleep 4
cd ../frontend && npm run dev

# Direct backend test (bypasses frontend, verifies backend works)
cd backend
TOKEN=$(grep '^APP_API_TOKEN=' .env | cut -d= -f2)
curl -sN -X POST http://127.0.0.1:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"I read a paper on RAG"}'
# Expect: a stream of SSE events ending in 'event: done'

# Verify Obsidian got messages
ls ~/Documents/SecondBrain/00-Inbox/Daily/
cat ~/Documents/SecondBrain/00-Inbox/Daily/$(date +%Y-%m-%d).md

# Kill backend
lsof -ti :8000 | xargs kill -9 2>/dev/null
```
