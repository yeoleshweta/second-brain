# Setup Guide

Step-by-step to get this running on your Mac. ~45 minutes for the basics.

## Prerequisites

- macOS (Linux works too)
- Node.js 20+ (`brew install node`)
- Python 3.11+ (`brew install python@3.12`)
- Obsidian (download from obsidian.md)

## 1. Install `uv` (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`uv` is much faster than pip and manages venvs automatically.

## 2. Set up the backend

```bash
cd second-brain/backend
uv sync                              # creates .venv, installs everything
cp .env.example .env                 # then edit with real keys
mkdir -p data logs secrets
```

## 3. Set up Obsidian

1. Open Obsidian. Create vault called `SecondBrain` (or use existing).
2. **Settings → Community plugins → Browse**. Install:
   - **Local REST API** (required)
   - **Templater**
   - **Dataview**
   - **Periodic Notes**
   - **Tasks**
3. Enable each plugin in your plugin list.
4. Open **Local REST API** settings — copy the **API Key**.
5. Create the folder structure:

```
00-Inbox/Daily/
01-Knowledge/
02-Health/
03-Finance/
04-People/
05-Calendar/
99-System/Templates/
```

## 4. Get your Claude API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Add billing, set a $10/month spending cap to start
3. **API Keys → Create Key**, copy it

## 5. Configure backend `.env`

At minimum:

```
ANTHROPIC_API_KEY=sk-ant-...
OBSIDIAN_API_KEY=<from step 3.4>
OBSIDIAN_VAULT_PATH=/Users/you/Documents/SecondBrain
APP_API_TOKEN=<generate a random string — see below>
```

Generate a token:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Fill in the others (Plaid, Google, USDA, etc.) as you build each agent — they're optional for the basic chat to work.

## 6. Set up the frontend

```bash
cd ../frontend
npm install
cp .env.example .env
# Edit .env, set VITE_API_TOKEN to match APP_API_TOKEN from backend
```

## 7. First run

Two terminals:

```bash
# Terminal 1 — backend
cd backend
uv run python -m src.api.main
# Should see: "Starting Second Brain API on http://127.0.0.1:8000"

# Terminal 2 — frontend
cd frontend
npm run dev
# Should see: "Local: http://localhost:5173"
```

Or use the helper script:
```bash
./scripts/dev.sh
```

Open [http://localhost:5173](http://localhost:5173).

## 8. Test it

In the web UI:
- Type "I just read a great paper on RAG" → should route to **Knowledge Agent**
- Type "I ate 200g of chicken" → routes to **Health Agent**
- Type "Coffee with Sarah next Tuesday" → routes to **Calendar Agent**
- Upload an image (paperclip icon) → attachment biases to **Health Agent** (for receipts)

Check Obsidian — entries should appear in `00-Inbox/Daily/`.

## 9. Hook up Google Calendar (optional, ~10 min)

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a project
2. **APIs & Services → Library** — enable "Google Calendar API"
3. **OAuth consent screen** → External → fill required fields → add yourself as test user
4. **Credentials → Create Credentials → OAuth client ID** → Desktop app
5. Download JSON → save to `backend/secrets/google_client_secret.json`
6. Run the auth flow:
   ```bash
   cd backend
   uv run python -m src.integrations.google_calendar auth
   ```
   Browser opens, you authorize, token saves to `secrets/google_token.json`.

## 10. Hook up Plaid (optional, ~10 min)

1. Sign up at [dashboard.plaid.com](https://dashboard.plaid.com) — free
2. **Team Settings → Keys** — copy `client_id` and `Sandbox secret`
3. Add to `.env`:
   ```
   PLAID_CLIENT_ID=...
   PLAID_SECRET=...
   PLAID_ENV=sandbox
   ```
4. In the web UI sidebar, click "Link bank account"
5. Use Plaid's sandbox credentials: username `user_good`, password `pass_good`
6. You're now linked. Real bank linking: change `PLAID_ENV=development` (free for ≤100 items).

## 11. Hook up Apple Health (optional)

1. On your iPhone, install **Health Auto Export — JSON+CSV** from the App Store (~$5)
2. Configure: export to iCloud Drive, format JSON, daily schedule
3. Wait for first export (or trigger manually in the app)
4. On Mac, the file appears at `~/Library/Mobile Documents/com~apple~CloudDocs/HealthExports/`
5. Set `HEALTH_EXPORT_DIR` in `.env` to that path

The file watcher (`backend/src/integrations/apple_health.py`) detects new files automatically — but you'll need to wire it into the scheduler.

## 12. Set up Cursor

See [`docs/cursor-setup.md`](./cursor-setup.md).

## Troubleshooting

**Frontend says "Chat request failed: 401":**
`VITE_API_TOKEN` in frontend `.env` must exactly match `APP_API_TOKEN` in backend `.env`. Restart frontend after editing.

**"OBSIDIAN_API_KEY not set":**
Make sure `.env` is in `backend/` directory, not the root. Make sure you copied from `.env.example`, not `.env.local`.

**Obsidian connection refused:**
- Is Local REST API plugin enabled?
- Default port is 27124. If you changed it, update `OBSIDIAN_PORT`.
- Self-signed cert on localhost — the Python client has `verify=False`, that's expected.

**Plaid Link UI never opens:**
Check browser console. Most common: `PLAID_CLIENT_ID` or `PLAID_SECRET` wrong, or `PLAID_ENV` mismatched (sandbox keys won't work in production env).

**Frontend dev server can't reach backend:**
Vite proxies `/api/*` to `localhost:8000`. If backend is on a different port, edit `frontend/vite.config.ts`.

## What's next

Once the echo bot works end-to-end:
1. Read [`docs/integrations-cookbook.md`](./integrations-cookbook.md) for the full menu of APIs you can plug in.
2. Pick Phase 1: replace `backend/src/agents/knowledge.py` stub with real RSS + arXiv + daily digest logic.
3. Each agent module has a docstring listing what to build next.
