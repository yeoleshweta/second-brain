# Phase 2 — iPhone & Google setup

Use this guide AFTER Cursor implements Phase 2, OR alongside it (the Google OAuth steps below are user-driven and Cursor can't do them automatically). This covers two distinct pieces:

1. **One-time Google OAuth setup on your Mac** so Chandler can read/write your Google Calendar and read Google Contacts.
2. **iPhone setup** so events Chandler creates appear in your native iOS Calendar app, and your iOS Contacts mirror your Google Contacts.

The PWA install / Tailscale setup from Phase 1 (see `docs/mobile-access.md`) still applies — you don't need to redo any of that.

**Time:** ~20 minutes for Google OAuth. ~5 minutes for the iOS Calendar/Contacts sync.

---

## Part 1 — Google Cloud Console: create OAuth credentials (10 min)

You're creating a "Desktop app" OAuth client for your local Mac to talk to your Google account. Google requires this even though you're the only user — it's the same flow third-party apps use.

### 1. Create a Google Cloud project

1. Go to https://console.cloud.google.com — sign in with the Google account you actually use for Calendar / Contacts (the one you want Chandler to manage).
2. Top bar: click the project dropdown → **New Project**.
3. Project name: `Second Brain` (or whatever). Organization: leave default. Click **Create**.
4. Wait ~10 seconds for the project to be created, then make sure it's selected (top bar dropdown should now show "Second Brain").

### 2. Enable the APIs Chandler needs

1. In the left sidebar (hamburger menu): **APIs & Services → Library**.
2. Search for **Google Calendar API** → click → **Enable**. Wait for confirmation.
3. Back to Library. Search **People API** → click → **Enable**. Wait for confirmation.

### 3. Configure OAuth consent screen

(Google requires this even for personal-use apps.)

1. **APIs & Services → OAuth consent screen**.
2. User Type: **External** (this is your personal Google account, but Google still wants this) → **Create**.
3. App information:
   - App name: `Second Brain`
   - User support email: your email
   - App logo: skip
   - Application home page: skip
   - Developer contact email: your email
   - Click **Save and Continue**.
4. Scopes screen: click **Add or Remove Scopes**. Filter "Calendar" → check `.../auth/calendar` (full calendar access). Filter "People" → check `.../auth/contacts.readonly`. Click **Update** → **Save and Continue**.
5. Test users: click **Add Users** → type your own Gmail address → **Save and Continue**. (As an External app in testing mode, only listed test users can authenticate. Adding yourself is enough for personal use.)
6. Summary: click **Back to Dashboard**.
7. On the OAuth consent screen dashboard, you may see a banner saying the app is "Testing". Leave it — you don't need to publish. **Testing-mode OAuth tokens expire after 7 days**, so you'll need to re-run the local auth flow once a week. You can avoid this by clicking **Publish App** later if you want, but for personal use the weekly re-auth is fine.

### 4. Create the OAuth client credentials

1. **APIs & Services → Credentials**.
2. Click **+ Create Credentials → OAuth client ID**.
3. Application type: **Desktop app**.
4. Name: `Second Brain Mac Client` (anything is fine).
5. Click **Create**. A dialog appears with the Client ID and Secret — click **Download JSON**.
6. The file downloads with a long name like `client_secret_…apps.googleusercontent.com.json`.

### 5. Place the credentials in your project

```bash
mkdir -p ~/Documents/Projects/second-brain/backend/secrets
mv ~/Downloads/client_secret_*.json \
   ~/Documents/Projects/second-brain/backend/secrets/google_client_secret.json
```

Confirm the file is there:
```bash
ls -la ~/Documents/Projects/second-brain/backend/secrets/
# expect: google_client_secret.json
```

Verify the path in `backend/.env` matches:
```
GOOGLE_OAUTH_CLIENT_SECRETS=./secrets/google_client_secret.json
GOOGLE_TOKEN_PATH=./secrets/google_token.json
```
(These should already be set from the scaffold.)

**Important:** `backend/secrets/` should already be in `.gitignore`. Double-check:
```bash
grep -E "^secrets|^backend/secrets" ~/Documents/Projects/second-brain/.gitignore
```
If nothing returns, add a line `backend/secrets/` to `.gitignore` immediately. **Never commit these files.**

---

## Part 2 — Run the OAuth flow locally (3 min)

This is a one-time interactive flow that produces `backend/secrets/google_token.json`, which Chandler will use for every call afterward.

```bash
cd ~/Documents/Projects/second-brain/backend
uv run python -m src.integrations.google_calendar auth
```

What happens:
1. A browser tab opens at `accounts.google.com`.
2. Sign in (or pick the account if multiple).
3. You'll see "Google hasn't verified this app" — click **Continue** (this is normal for testing-mode apps you created yourself).
4. Review the requested scopes (Calendar full access, Contacts read). Click **Continue** → **Continue** again.
5. Browser shows "The authentication flow has completed. You may close this window."
6. Back in your terminal: `Google OAuth token saved to ./secrets/google_token.json`.

Verify the token landed:
```bash
ls -la ~/Documents/Projects/second-brain/backend/secrets/google_token.json
```

Quick sanity check:
```bash
cd ~/Documents/Projects/second-brain/backend
uv run python -c "
import asyncio
from src.integrations.google_calendar import GoogleCalendarClient
c = GoogleCalendarClient()
events = asyncio.run(c.list_upcoming_events(168))
print(f'Found {len(events)} events in the next week.')
for e in events[:3]:
    print(' -', e.get('summary'), '@', e.get('start', {}).get('dateTime', e.get('start', {}).get('date')))
"
```

If you see events from your actual Google Calendar listed, you're done. If you see an error, the most common causes are:
- `Missing ./secrets/google_client_secret.json` — Part 1 step 5 didn't land the file in the right place.
- `invalid_client` — the downloaded JSON was for a different OAuth client type. Re-do Part 1 step 4 ensuring "Desktop app" is selected.
- `access_denied` — your email isn't in the test users list. Part 1 step 3 sub-step 5.

---

## Part 3 — iPhone: confirm Google Calendar sync to iOS Calendar (3 min)

Most likely your iPhone already syncs your Google Calendar to the iOS Calendar app — but worth verifying since Chandler's whole value depends on it.

1. **Settings** (iOS Settings, not the Calendar app) → scroll down → **Apps** → **Calendar** (older iOS) or **Settings → Calendar** → **Accounts**.
2. Tap **Add Account** → **Google**.
3. Sign in with the **same Google account** you used for OAuth in Part 1.
4. After sign-in, you'll see toggles for what to sync. Make sure **Calendars** is ON. (Contacts is optional — recommended ON so Chandler's reads of Google Contacts match what's on your phone.)
5. Tap **Save**.

Open the iOS **Calendar** app. Tap **Calendars** at the bottom. You should see your Google calendars listed under your Google account, with checkmarks. Make sure your main calendar (often labeled with your email address) is checked.

To test: in the Calendar app, create a quick test event. Then in Chrome (Mac) go to https://calendar.google.com — the event should appear within ~30 seconds. (Both directions sync.) Delete the test event.

Now any event Chandler creates via Google Calendar API will appear in your iOS Calendar app within ~1 minute (push sync). And events you create on your phone are visible to Chandler too.

---

## Part 4 — iPhone: optional Google Contacts sync (2 min)

If you said yes to "Contacts" in Part 3 step 4, you're already done.

If not, and you'd like Chandler's person notes to use the same contact data as your iPhone (names, emails, photos):

1. Settings → Apps → Contacts → Accounts (or Settings → Contacts → Accounts).
2. Tap your Google account.
3. Toggle **Contacts** ON.
4. Save.

iOS will sync Google Contacts into the native Contacts app. Doesn't change anything Chandler does directly — but if you ever want to call/text a person from a Chandler note, having the contact in iOS Contacts means the link works.

---

## Part 5 — End-to-end smoke test from iPhone (3 min)

Final sanity check that everything's wired up.

Prereqs: backend + frontend running on Mac (`cd backend && uv run python -m src.api.main` + `cd frontend && npm run dev`), Tailscale up on both Mac + iPhone, PWA installed on iPhone home screen.

1. Open the Second Brain PWA on your iPhone.
2. Type: `schedule a quick test event tomorrow at 9am`.
3. Within ~3 seconds: Chandler should reply `📅 Confirm: 'Quick test event' on <date> 9:00am (30 min). Reply 'yes' to add or 'no' to cancel.`
4. Reply: `yes`.
5. Chandler should reply `✅ Added 'Quick test event' to your calendar.`
6. Open the iOS Calendar app. Within ~1 minute, the event should appear on tomorrow at 9am.
7. Back in the PWA, type: `what's on tomorrow?` → Chandler should list it.
8. Open Obsidian on the Mac. Navigate to `04-People/` — if the test event was named with a person, you'll see their note created.

If all of that works, you're done.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Chandler: Google not connected.` in chat | Token file missing / never ran OAuth | Run `uv run python -m src.integrations.google_calendar auth` |
| `Chandler: Google authentication expired.` | Testing-mode token expired (7 days) | Re-run the auth flow. OR publish your OAuth app to remove the 7-day limit |
| Event created via Chandler doesn't appear in iOS Calendar | iOS sync not enabled, or wrong calendar | Verify Part 3 step 4. Make sure the right calendar is checked in iOS Calendar's "Calendars" panel |
| `invalid_grant` errors | Token was generated for a different scope or different client | Delete `backend/secrets/google_token.json` and re-run auth |
| iOS Calendar shows event under the wrong calendar | `GOOGLE_CALENDAR_ID` is `primary` by default; iOS labels your primary calendar with your email | Either accept this, or set a specific calendar in `backend/.env` (`GOOGLE_CALENDAR_ID=<the calendar's ID from calendar.google.com settings>`) and restart the backend |
| Push sync delay > 5 minutes from iOS to Google | iOS sometimes throttles. Background refresh disabled | Settings → General → Background App Refresh → enable for Calendar |

---

## Security notes

- `backend/secrets/google_client_secret.json` and `backend/secrets/google_token.json` are LOCAL FILES on your Mac. They're tied to your Google account; whoever has them can read/write your calendar and read your contacts.
- These files are in `.gitignore` (verify!). Never check them in.
- If you ever think a token is compromised: go to https://myaccount.google.com/permissions, find "Second Brain", click "Remove Access". Then delete `secrets/google_token.json` and re-auth.
- Chandler asks for `calendar` (read + write) and `contacts.readonly` scopes only. It cannot send email, cannot delete your account, cannot read your Gmail.
- iOS Calendar / Contacts sync is between Apple and Google — Chandler isn't involved. Both Apple and Google encrypt these in transit and at rest.
