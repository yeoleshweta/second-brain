# Mobile Native App — Full Setup Guide

Your second brain runs as a **native iOS and Android app** via [Capacitor](https://capacitorjs.com),
which wraps your existing React UI into a real `.ipa` / `.apk`. The backend runs on
[Railway](https://railway.app) (free tier) so your phone works even when your Mac is off.

---

## Architecture (what changes)

```
Before:  iPhone → (Tailscale VPN) → Mac (must be on) → FastAPI → Obsidian on Mac
After:   iPhone (native app) → Railway (always on) → FastAPI → /vault volume
                                                               ↕ Obsidian Sync
                                                            Mac Obsidian vault
```

Obsidian Sync ($5/mo) keeps the vault in sync between the Railway volume and every device
you have Obsidian installed on (Mac, iPhone, iPad).

---

## Step 1 — Deploy backend to Railway

### 1a. Create a Railway account
Go to https://railway.app and sign up (GitHub login is fastest).

### 1b. New project from GitHub
1. Click **New Project → Deploy from GitHub repo**
2. Select your `second-brain` repository
3. Railway detects the `Dockerfile` and `railway.toml` automatically

### 1c. Add persistent volumes
In Railway → your service → **Volumes** tab:
- Add volume → mount path `/data` → name `secondbrain-data`
- Add volume → mount path `/vault` → name `secondbrain-vault`

### 1d. Set environment variables
Copy everything from `backend/.env.cloud.example` into Railway → **Variables** tab.

Key ones to fill in immediately:
```
OPENAI_API_KEY=sk-...
APP_API_TOKEN=<generate: python -c "import secrets; print(secrets.token_urlsafe(32))">
OBSIDIAN_API_KEY=          # leave EMPTY — triggers filesystem mode
OBSIDIAN_VAULT_PATH=/vault
DATABASE_URL=sqlite:////data/secondbrain.db
DATA_DIR=/data
```

### 1e. Get your Railway URL
After deploy: your app is at `https://second-brain-production.up.railway.app` (Railway assigns this).
Check it works: `curl https://your-app.up.railway.app/api/health`

---

## Step 2 — Set up Obsidian Sync (vault everywhere)

Obsidian Sync keeps your vault in sync between Railway and your Mac + iPhone.

### Option A — Obsidian Sync (easiest, $5/mo)
1. Open Obsidian on Mac → Settings → Core plugins → enable **Sync**
2. Subscribe at https://obsidian.md/sync
3. Create a remote vault and connect it to your local vault
4. Install **Obsidian** on iPhone → Settings → Sync → connect to the same remote vault
5. On Railway: the backend writes .md files to `/vault`; Obsidian Sync on Mac picks them up

> Note: Railway's `/vault` volume and your Mac's Obsidian vault are separate file systems.
> Currently: Railway writes notes, they appear in your Mac vault via Obsidian Sync only when you
> use the iOS Obsidian app to browse (it syncs the remote). For real bidirectional sync between
> Railway volume and Mac you'd need a git-based sync (see Option B).

### Option B — Git sync (free, more control)
1. Make your Obsidian vault a git repo: `cd ~/Documents/SecondBrain && git init`
2. Push to a private GitHub repo
3. Install the **Obsidian Git** community plugin on Mac
4. On Railway: set `GITHUB_TOKEN` and add a startup script that clones and periodically pulls/pushes
5. Railway writes notes → git push → Mac Obsidian Git plugin pulls

---

## Step 3 — Build the native iOS app

### Prerequisites
- Mac with **Xcode** installed (Mac App Store, free, ~15GB)
- iPhone connected with a cable (or use a Simulator)
- Free Apple Developer account (no $99 account needed to sideload to your own phone)

### 3a. Set your Railway backend URL
```bash
cd frontend
cp .env.example .env.local
```

Edit `.env.local`:
```
VITE_API_URL=https://your-app.up.railway.app
VITE_API_TOKEN=your-real-token
```

### 3b. Build and open in Xcode
```bash
cd frontend
npm run mobile:ios
# This runs: tsc && vite build && cap sync ios && cap open ios
```

Xcode opens automatically with the `ios/App/App.xcworkspace` project.

### 3c. Sign and run on your iPhone
1. In Xcode: select your iPhone as the target device (top bar)
2. **Signing**: Xcode → Target → Signing & Capabilities → select your Apple ID team
3. Click the **▶ Run** button
4. First time: on your iPhone go to Settings → General → VPN & Device Management → trust your developer certificate
5. App installs and launches directly on your phone 🎉

### 3d. Every time you update the app
```bash
cd frontend
npm run mobile:ios
# Xcode re-opens; press Run again
```

---

## Step 4 — Build Android app (optional)

### Prerequisites
- **Android Studio** installed (free from https://developer.android.com/studio)

```bash
cd frontend
npm run mobile:android
# This runs: tsc && vite build && cap sync android && cap open android
```

Android Studio opens → Run → select your device or emulator.

---

## Step 5 — iOS Obsidian app

Install **Obsidian** from the App Store on your iPhone.
If you set up Obsidian Sync (Step 2 Option A), your notes appear automatically.

You'll have two ways to access your second brain on your iPhone:
1. **Central Perk native app** (chat with agents, Finance, Agenda, Reading list)
2. **Obsidian iOS app** (browse/edit raw markdown notes, graph view)

---

## Summary: what you need to buy/set up

| Item | Cost | Required for |
|---|---|---|
| Railway account | Free (500h/mo hobby) | Always-on cloud backend |
| Railway Pro (if needed) | $5/mo | More than 500 compute hours |
| Obsidian Sync | $5/mo | Vault sync between cloud + Mac + iPhone |
| Apple Developer account | Free (sideload only) | Running on your own iPhone |
| Apple Developer account paid | $99/yr | Publishing to App Store |
| Xcode | Free (Mac App Store) | Building iOS app |

**Minimum to get started: $0** (Railway free tier + Xcode + free Apple ID sideload).
Obsidian Sync at $5/mo is strongly recommended for vault access everywhere.

---

## Development workflow (day-to-day)

```bash
# Local dev (Mac): run both servers, open browser
cd backend && uv run python -m src.api.main &
cd frontend && npm run dev

# Update mobile app after UI changes:
cd frontend && npm run mobile:ios   # rebuilds + opens Xcode → press Run

# Push backend changes to Railway:
git push origin main                # Railway auto-deploys from main branch
```
