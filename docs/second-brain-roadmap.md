# Second Brain — Full Potential Roadmap

Your agents are a **local second brain** on your Mac. This doc explains what's live, what's next, and what's realistically possible for Gmail, LinkedIn, Instagram, and phone access when the laptop is away.

---

## What you have today

| Agent | Live capabilities |
|---|---|
| **Ross** | Save URLs/PDFs/any file → reading list + Obsidian vault; digests; books; Apple Books MCP; research |
| **Chandler** | Google Calendar schedule/agenda; people notes (`04-People/`); Sunday stale-contact reminders; **Gmail unread in morning brief** (after re-auth) |
| **Monica** | Food/workout logging, nutrition status |
| **Finance** | Plaid bank link (sandbox); spending queries coming in Phase 5 |

---

## 1. Universal file capture (done)

- Chat accepts **any file type** (images, PDF, zip, epub, …)
- Ross copies files into **`Attachments/YYYY-MM-DD/`** in your Obsidian vault
- Creates a capture note in **`00-Inbox/Captured/`** with embed/link
- PDFs/docs also go to the **Reading list** when applicable
- Images get a short **AI description** in the note

**Requires:** `OBSIDIAN_VAULT_PATH` and Obsidian Local REST API running on the Mac.

---

## 2. Phone access — honest options

The app runs on **your Mac**. Obsidian, SQLite, and uploads all live there. When the Mac is **off or asleep**, nothing can serve the app — that's architectural, not a bug.

### Option A — Phone while traveling (Mac stays on at home) ✅ recommended

1. Install **Tailscale** on Mac + iPhone (see `docs/mobile-access.md`)
2. Run `./scripts/start.sh` or install the LaunchAgent (below)
3. Open `http://<tailscale-ip>:5173` on your phone
4. Prevent sleep: **System Settings → Energy → Prevent automatic sleeping when display is off** (or use Amphetamine)

API calls go through the Vite proxy on port **5173**, not direct :8000.

### Option B — Public URL when Mac is on (Tailscale Funnel)

```bash
tailscale funnel 5173
```

Use the `*.ts.net` URL from your phone anywhere. Strong `APP_API_TOKEN` required.

### Option C — Mac always on (Mac mini / old Mac as server)

Same as A, but a dedicated always-on machine at home. Best long-term for “second brain at home, phone anywhere.”

### Option D — True laptop-off access (future / large project)

Requires:

- Backend hosted in the cloud (Fly.io, Railway, etc.)
- Vault sync (git, S3, or Obsidian Sync) instead of localhost REST
- Secrets management for Google/Plaid tokens

Not built yet — Option A + always-on Mac is the practical path for months ahead.

### LaunchAgent (auto-start on login)

```bash
cp scripts/com.second-brain.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.second-brain.plist
```

Edit paths in the plist if your project lives elsewhere.

---

## 3. Gmail (partial — re-auth required)

Gmail **read-only** is wired into the **morning brief** (`## 📧 Gmail — unread`).

**Enable:**

1. Google Cloud Console → enable **Gmail API** on your project
2. Re-run OAuth (adds `gmail.readonly` scope):

   ```bash
   cd backend && uv run python -m src.integrations.google_calendar auth
   ```

3. Ask Chandler: *"anything important in my email?"* (inbox handler — extend as needed)

Chandler will **never send email** without a confirmation gate (same as calendar writes).

---

## 4. LinkedIn & Instagram — what's possible

| Platform | Personal API? | Realistic approach |
|---|---|---|
| **LinkedIn** | No (personal) | Tell Chandler: *"Met Sarah at Re:Invent, works at Anthropic"* → `04-People/Sarah.md`. Sunday brief reminds you to reconnect. |
| **Instagram** | Business accounts only | Manual capture in chat; no reliable personal API. |

Scraping or unofficial APIs break often and violate ToS — this project intentionally avoids them.

**Better signals for “who should I connect with?”**

- Gmail (meetings, intros, unread from people in `04-People/`)
- Google Calendar attendees → auto person notes
- Google Contacts sync (client exists, wiring in progress)
- Your manual notes — still the highest-quality source

---

## 5. Recommended build order (next sprints)

1. **Re-auth Google** with Gmail scope → verify morning brief inbox section
2. **Wire Google People** → fill emails when scheduling; optional sync to `04-People/`
3. **Chandler inbox chat** — "summarize my unread email" on demand
4. **Plaid transaction sync** → Finance agent spending questions
5. **Proactive nudges** — push reach-out reminders into chat, not just Obsidian
6. **Always-on Mac** + LaunchAgent for reliable phone access

---

## 6. MCP pattern for Mac apps

Already live: **Apple Books** via `apple-books-mcp`.

To add more apps (Mail.app, Reminders, Notes):

1. Find or build a **read-only MCP server**
2. Add to `.cursor/mcp.json`
3. Wrap in `backend/src/integrations/` using `mcp_stdio.py`
4. Route from the right agent

See `docs/mcp-apple-books.md`.

---

## Quick health checks

```bash
# Backend
curl -H "Authorization: Bearer $APP_API_TOKEN" http://localhost:8000/api/health

# Google Calendar
curl -H "Authorization: Bearer $APP_API_TOKEN" http://localhost:8000/api/integrations/google/health

# Apple Books MCP
curl -H "Authorization: Bearer $APP_API_TOKEN" http://localhost:8000/api/integrations/apple-books/health
```

Your second brain gets smarter as **Obsidian notes + calendar + email + bank data** accumulate — the agents query what you've captured, not magic social graphs.
