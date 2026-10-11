# Run Second Brain on Vercel only (no Railway)

The FastAPI process (SQLite, disk vault, Plaid, Gmail) cannot run on Vercel. The workaround is a **same-origin serverless API** in this repo (`frontend/api/`) plus **Vercel Blob** for markdown captures and chat history.

Phone chat and “remember this…” work with the Mac off. Plaid, Gmail, uploads, TTS, and the reading list still need the Mac app.

Cloud captures live in Blob (`vault/00-Inbox/…`), not automatically in `~/Documents/SecondBrain`.

## 1. Enable Blob

In the Vercel project: **Storage → Create Database → Blob**. That sets `BLOB_READ_WRITE_TOKEN` for Production.

## 2. Environment variables (Production)

Do **not** set `VITE_API_URL` (the PWA must call `/api` on the same host).

```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
OPENAI_API_KEY=sk-...
APP_API_TOKEN=<same as local APP_API_TOKEN>
VITE_API_TOKEN=<same value as APP_API_TOKEN>
TZ=America/New_York
```

Do **not** set `VITE_API_URL`. Add Anthropic API credits or chat/Review drafts will fail with a billing message.

Optional: `OPENAI_MODEL_CHEAP=gpt-4o-mini` (default). Hobby functions time out around 10s — mini is the safe model.

Redeploy after changing `VITE_*` (they are baked in at build time).

## 3. Deploy

From `frontend/`:

```bash
cd frontend
npx vercel login
npx vercel --prod
```

Root directory in the Vercel project must be `frontend`. Link Blob to this project if the token is missing.

Health: `https://<app>.vercel.app/api/health` should include `"runtime":"vercel"` and `"blob":true`.

## 4. Phone

Safari → that **https** URL → Share → **Add to Home Screen**. Mic needs HTTPS.

## 5. Local Mac

Unchanged: `localhost:5173` talks to FastAPI `:8000` and the Obsidian folder on disk.
