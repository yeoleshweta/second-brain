# Second Brain — Architecture (v2, LLM Wiki)

> Read this before non-trivial changes. This **replaces** the v1 capture-only contract.

The product is a **personal LLM Wiki**: one chat app on Mac and iPhone (Safari PWA) that dumps every kind of input into an Obsidian vault. **Claude drafts** filings and links; **you approve** before anything is added to Notes / People / Projects / Concepts. Markdown on disk is the source of truth. SQLite is chat history, an ingest queue, and job metadata — not the knowledge base.

v1 (phrase + keywords, never write `01–05`) is retired. The [research-plan.md](research-plan.md) week-4 gate does **not** apply to this filing pipeline.

This is **not** MindStudio, not a multi-agent Friends product, and not App Store–first. Leftover specialist modules (`knowledge` / `health` / `finance` / `calendar` / `career`) stay unused by chat.

---

# What you experience

On **Mac** (browser at `localhost:5173`) and **iPhone** (Safari → Add to Home Screen):

1. Talk, type, take a photo, or attach a file in one composer.
2. That payload lands in `Inbox/` as a raw note (`status: inbox`).
3. You get a chat reply from Claude (retrieval over the vault, not a specialist bot).
4. Claude **drafts** a filing (`status: proposed`). Open **Review** and Approve or Reject.
5. Only Approve writes Notes / People / Projects / Concepts. Reject keeps it out of the wiki.

Obsidian remains the place you *read* the graph. The app is how you *feed* and *query* it.

---

# Vault contract (v2)

Canonical tree (article folders). Live vault: `OBSIDIAN_VAULT_PATH` (usually `~/Documents/SecondBrain`).

```
Inbox/            ← every new input lands here first (status: inbox)
Notes/            ← processed permanent notes
People/           ← one note per person
Projects/         ← active workspaces
Concepts/         ← evergreen / hub notes
Briefings/        ← Claude daily/weekly summaries (YYYY-MM-DD.md)
Templates/        ← frontmatter + note shapes
99-System/Logs/   ← pipeline failures (never silent)
```

**The Void capture target** is `00-Inbox/Void/YYYY-MM-DD.md` (bot only). `## Log` if exactly one type matches; `## Unsorted` otherwise. The human daily note `00-Inbox/Daily/YYYY-MM-DD.md` embeds `![[Void/YYYY-MM-DD]]` and is never written by the bot. Capture happens only on a phrase (`remember this`, `write this down`, …). Chat does not dump every turn into `Inbox/`. Failures → `99-System/Logs/`.

Optional Mac sync: private GitHub vault repo + Obsidian Git (`syncMethod: merge`, pull every few minutes). Cloud capture can use `GITHUB_VAULT_REPO` + `GITHUB_TOKEN` so `ObsidianClient` writes via the Contents API; the Mac pulls.

### Frontmatter (every note)

```yaml
---
title: "Note Title"
date_created: 2026-10-11
date_modified: 2026-10-11
tags: []
status: inbox   # inbox | processed | evergreen
related: []
source: ""      # chat | voice | photo | clip | email | meeting | upload
---
```

`status: inbox` is the job trigger. After a successful process, Claude sets `processed`. You may promote to `evergreen` in Obsidian.

### Processor may (only after you tap Approve)

- Create/update notes under Notes / People / Projects / Concepts / Briefings.
- Insert `[[wiki-links]]` in the **new** note. Bidirectional edits to older notes are a later reviewed pass, not silent.
- Mark the Inbox item `processed` and keep the raw + proposal for audit.

### Processor must not

- Move money, send email, or create calendar events without an explicit confirmation gate (chat: propose → Add to calendar).
- Delete user notes. Failures append to `99-System/Logs/`.
- Use Claude for simple search (use vault grep / list; Claude only for transform + chat).

---

# System diagram

```
 iPhone PWA (Safari, HTTPS)          Mac browser
   voice / camera / text / files       same UI
                 \                    /
                  \                  /
                   ▼                ▼
              FastAPI  :8000  (one process)
                 │
     ┌───────────┼───────────────┬─────────────────┐
     │           │               │                 │
     ▼           ▼               ▼                 ▼
 POST /api/chat  /api/upload   ingest adapters   jobs (launchd)
 Claude reply    Whisper STT   Gmail / clips     every 2h Inbox
 + write Inbox   Claude vision meeting files     nightly backlinks
     │           + write Inbox + write Inbox     weekly Concepts
     │                                           morning Briefing
     ▼
 Obsidian vault (markdown folder)
     ▲
     └── optional Local REST API if the folder is locked by Obsidian
```

SQLite sits beside the vault: `chat_sessions`, `ingest_items`, `job_runs`. It is not the wiki.

---

# Inputs (everything becomes an Inbox note)

| Channel | How it enters | Immediate write |
|---|---|---|
| **Typed chat** | Composer → `POST /api/chat` | `Inbox/` raw note + Claude reply (schedule/agenda/calendar-confirm turns skip Inbox) |
| **Voice** | Mic → `/api/upload` → Whisper transcribe → same as chat | Transcript in Inbox (`source: voice`) |
| **Camera / photos** | File picker or camera → `/api/upload` → Claude vision caption + OCR-ish description | Image saved under vault attachments; Inbox note with `source: photo` |
| **Files / PDFs** | Upload | Inbox note + extracted text |
| **Web clips** | Obsidian Web Clipper (or Share later) targeting `Inbox/` with `status: inbox` | File appears; next process run picks it up |
| **Email** | Gmail (existing Google OAuth): label or filter → poll/watch → Inbox note (`source: email`) | |
| **Meetings** | Upload .txt/.vtt or forward Fireflies/Otter transcript to the same Gmail label | Inbox (`source: meeting`) |

No extra “six apps.” One PWA. Clipper and Gmail are pipes into the same Inbox.

**Privacy:** Claude API sees note text (and image bytes for photos). Anthropic API data is not used for training by default; it still **leaves the Mac**.

---

# Claude’s two jobs

### 1. Chat (pull)

`POST /api/chat` (SSE, same event names as today: `session_id`, `status`, `message`, `obsidian`, `intent`, `done`).

- Retrieve: keyword/file search over the vault (not a 200k dump of everything).
- Reply with Claude. Cite `[[Note titles]]` when they exist.
- Always dump the user turn (and attachments) to `Inbox/` — no ritual phrase required (v1 phrases retired), **except** Google Calendar schedule/agenda/confirm turns. Those hit Calendar only after you tap Add; they are not wiki notes.
- `intent` stays `general` (one bot). Chat may propose a calendar event; it must not create one until confirm.

Speech-to-text stays **OpenAI Whisper** unless we later swap it. Images and filing use **Claude**.

### 2. Wiki processor (push)

A job, not the chat request (chat must stay fast on the phone):

1. List `Inbox/` where `status: inbox` (and new files from the clipper).
2. For each note, Claude returns JSON: summary, key_concepts, people, action_items, related_topics, destination_folder, processed_content with `[[wiki-links]]`.
3. Write the processed note to Notes / People / Projects / Concepts.
4. Mark Inbox item `processed`.
5. **Backlinks:** find existing notes that mention those concepts; Claude adds `[[New Title]]` where relevant; write back.
6. **Weekly:** concepts seen in 5+ notes without a Concept hub → synthesize `Concepts/{topic}.md`.
7. **Daily briefing:** `Briefings/YYYY-MM-DD.md` (yesterday’s inputs, open actions, one theme, one old-note resurface).

Schedule (Mac `launchd`, while the Mac is on):

| Job | When |
|---|---|
| Inbox process | Every 2 hours, waking hours |
| Backlink pass | Nightly |
| Concept hubs | Sunday |
| Briefing | ~07:00 local |

---

# Mac vs iPhone vs “Mac off”

| Mode | UI | API + vault + jobs |
|---|---|---|
| **Daily driver** | Mac localhost or iPhone PWA on LAN/Tailscale | FastAPI on the Mac, vault = `~/Documents/SecondBrain` |
| **Phone on the couch (Mac on)** | Safari PWA, HTTPS or Tailscale | Same Mac API |
| **Phone anywhere (Mac off)** | Vercel PWA | Serverless chat + Blob is a **staging Inbox only**. Wiki jobs and Obsidian need a long-running API + disk. Vercel cannot run this pipeline. Until a disk host exists, **Mac-off = capture to Blob, no Claude filing.** |

PWA (Add to Home Screen) is the phone app. No App Store. Mic and camera need **HTTPS** (Vercel) or localhost; Tailscale HTTP still cannot use live mic.

Honest split: **the LLM Wiki is Mac-vault-native.** The phone is a full client when the API that mounts that vault is reachable.

---

# Stack

- **App:** React + Vite + TypeScript + Tailwind (existing PWA).
- **API:** FastAPI, LangGraph (one node), `httpx` async.
- **Chat + wiki:** Anthropic Claude (`ANTHROPIC_API_KEY`). Model: a current Sonnet/Opus you set in settings.
- **STT:** OpenAI Whisper (`OPENAI_API_KEY`) until replaced.
- **Vault:** filesystem first (`OBSIDIAN_VAULT_PATH`). Local REST API optional.
- **Auth:** `Authorization: Bearer APP_API_TOKEN`.
- **Finance leftovers:** read-only if ever called. Never move money.

New env (gitignored `.env`):

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # Whisper only
APP_API_TOKEN=...
OBSIDIAN_VAULT_PATH=/Users/.../Documents/SecondBrain
```

---

# Request path (chat)

1. UI POSTs `/api/chat` (message, history, `session_id`, `file_id`s).
2. FastAPI hydrates last 20 SQLite turns; resolves uploads (transcript / image description).
3. Write raw `Inbox/{stamp}-{slug}.md` with frontmatter `status: inbox`.
4. Retrieve a few related vault files; Claude replies.
5. SSE: `status` → `message` → `obsidian` (Inbox path) → `intent=general` → `done`.
6. Processor later files and links. Chat does **not** wait for that.

Uploads still go `/api/upload` then `file_id`.

---

# Dual store

| What | Where |
|---|---|
| Knowledge | Vault markdown (Inbox → Notes/People/Projects/Concepts) |
| Briefings | `Briefings/` |
| Chat bubbles | SQLite |
| Ingest / job status | SQLite |
| Photos / audio blobs | Vault `Inbox/attachments/` (or `99-System/media/`) |
| Plaid / reading-list leftovers | SQLite; not part of the wiki |

---

# Frontend / backend contract

Unchanged wire format so the PWA keeps working:

- All routes under `/api/`
- Bearer token = `APP_API_TOKEN`
- Chat SSE: `session_id`, `status`, `message`, `obsidian`, `intent`, `done`, `error`
- Live chat `intent` is always `general`

---

# Error handling

- Vault unwritable: chat still replies; Inbox write logged; client told capture failed.
- Claude down: short fallback; raw Inbox note still saved if the disk write worked.
- Process job fail: `99-System/Logs/` + Inbox stays `status: inbox` for retry.
- Inbox count above a threshold: log (later: optional notify). Do not email from the bot without a gate.

---

# What is not in the first build slice

These are in the architecture but **not** required to land in one change:

- Fireflies/Otter native APIs (start with file upload + Gmail label).
- Share Sheet → PWA (iOS limitation; clipper + camera cover most of it).
- Always-on cloud disk (user is Vercel-only; wiki jobs stay on the Mac).
- MindStudio.
- Offline queue.

## Component map (target)

```
iPhone PWA  ──►  FastAPI :8000  ──►  Claude (chat)
                            ├──►  Whisper (voice)
                            ├──►  Inbox/*.md
                            └──►  jobs ──► Notes/People/Projects/Concepts/Briefings
                                              ▲
Mac Obsidian ─────────────────────────────────┘
```
