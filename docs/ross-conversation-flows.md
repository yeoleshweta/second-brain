# Ross — Conversation flow design

This is the design doc for Ross v2: the version that goes beyond "save URLs" and becomes a daily knowledge + learning coach. Read this before implementing — it captures intent shape, every flow we expect to support, every failure mode worth handling, and the anti-patterns we explicitly want to avoid.

When Cursor builds Ross v2, this doc becomes the source-of-truth for which conversations are "in scope" and which aren't. If a flow isn't listed here, it's either (a) a `chat` fallback, or (b) a deliberate omission.

---

## 1. Ross's role (what we're really building)

Ross is **your knowledge curator and learning coach**. Three responsibilities, in order of importance:

1. **Knowledge keeper** — captures the things you read, watch, save, write, and practice; structures them in your second brain; answers questions about your own past.
2. **Discovery** — surfaces items from your existing list (and the world) that you should look at today.
3. **Habit coach** — nudges you toward your daily reading + practice goals without becoming an annoyance.

What Ross is NOT: a generic chatbot. He doesn't answer "what's the capital of France." If you want a general-purpose assistant, that's `gpt-4o` directly. Ross's value is that he knows *your* corpus.

### What Ross has access to

| Data | Source | How Ross uses it |
|---|---|---|
| Reading list (status, progress, tags, summaries) | SQLite `reading_list_items` | Suggestions, "what have I read," progress tracking |
| Per-item Obsidian notes | `01-Knowledge/` and `01-Knowledge/Archive/` | Full-text search for "what do I know about X" |
| Practice log | SQLite `practice_sessions` (NEW — see §6) | Streak tracking, "what skills are you working on" |
| Daily inbox entries | `00-Inbox/Daily/*.md` | Recall ("what did I think about transformers last Tuesday") |
| External feeds | RSS, arXiv, Tavily | Fresh content suggestions, on-demand digests |
| Your stated goals | User config (NEW — see §8) | What "daily reading" means (15 min), what skills count as practice |

---

## 2. Voice and tone principles

These constrain every reply Ross writes. They're not flavor text — they're the difference between an app you use and an app you mute.

- **Friendly, never saccharine.** "Saved." beats "🎉 Awesome, I saved that for you!"
- **Surfaces the win, not the gap.** "You read 14 min today — 1 min short. Nice momentum." NOT "❌ You haven't hit your reading goal."
- **Concrete over vague.** "You saved 3 articles last Tuesday — Mamba, RAG eval, vector DBs." NOT "You've saved a lot recently."
- **No streaks-with-shame.** Streaks displayed when present; never highlighted on breaks. A broken 12-day streak is just `"7 of last 14 days had reading time"` — no fire emojis going out.
- **One nudge per channel per day.** Ross doesn't ping you 5 times. If he sent the morning brief at 6am, he doesn't also send "still haven't read?" at 2pm AND "you didn't hit your goal" at 9pm. Pick one.
- **Asks before assuming.** "I see you're 40 min into 'Mamba' and didn't touch it for 8 days — drop it, or keep going?" NOT "Marking 'Mamba' as abandoned."
- **No fake personalization.** "Hey Shweta, hope you're having a great Tuesday!" — no. Ross knows you, not your mood. Skip the small talk.

---

## 3. Intent taxonomy

These are the seven top-level sub-intents Ross handles. Everything else falls to `chat` (a brief conversational reply, no side effects).

| Sub-intent | Trigger | Side effect |
|---|---|---|
| `save` | Save command + content | DB insert + Obsidian mirror file |
| `list` | "Show my reading list" / "what's in my list" | None (chat-only render) |
| `mark_read` | "mark X as read" / "finished X" | DB update + file move to Archive |
| `update_progress` | "I'm 50% through X" / "60% Mamba" | DB update + frontmatter rewrite |
| `delete` | "delete X" / "remove X from list" | DB delete + file delete |
| `query` | "what do I know about X" / "have I read anything on Y" | None (chat-only render with citations) |
| `suggest` | "suggest something to read" / "what should I read next" | None (chat-only) |
| `log_practice` | "I practiced X for Y minutes" / "did 1hr of guitar" | DB insert into `practice_sessions` |
| `practice_status` | "how's my practice going" / "did I practice today" | None |
| `digest_now` | "what's new in AI" / "any new papers" | None |
| `summarize_url` | URL + "summarize" / "tldr" | None |
| `chat` | Anything else | None |

---

## 4. Detailed flows — happy paths

### 4.1 Save a URL

**Input:** `save in notes https://arxiv.org/abs/2312.00752`

**Flow:**
1. Detect save phrase + URL.
2. Fetch via Jina Reader (timeout 15s).
3. `gpt-4o` → `{title, summary (3 sentences), tags, kind}`.
4. Check dedup: `SELECT * FROM reading_list_items WHERE url = ?`.
5. If new: insert row + write `01-Knowledge/<slug>.md` with frontmatter.
6. Reply: `🪄 Saved 'Mamba: Linear-Time Sequence Modeling with Selective State Spaces' → 01-Knowledge/`

**Variants:**
- arxiv.org → `kind=paper`, tagged with arxiv categories.
- youtube.com / youtu.be → fetch transcript via `youtube-transcript-api`, use that as the body for summarization.
- pdf URL → download, parse text with `pypdf`, summarize.
- twitter.com / x.com → just store the link + tweet text (no Jina); single-sentence summary.

### 4.2 Save freeform note

**Input:** `save this: revisit BAML structured output approach`

**Flow:**
1. Detect save phrase, strip it.
2. Body is everything after the phrase.
3. `gpt-4o-mini` → title (≤60 chars).
4. Insert row with `kind=note`, `url=null`.
5. Mirror file in `01-Knowledge/Notes/<slug>.md`.
6. Reply: `🪄 Saved 'Revisit BAML structured output approach' (note)`

### 4.3 Save with PDF upload

**Input:** User taps paperclip, picks PDF, types `save in notes` (or just sends with no text).

**Flow:**
1. Frontend uploads to `/api/upload`, gets `file_id`.
2. Chat message arrives with `attachments=[{file_id, type:'pdf'}]`.
3. Ross sees PDF attachment → extract text via `pypdf` (first 30k chars).
4. `gpt-4o` summarizes.
5. Save to reading list with `kind=pdf`, store the actual file in `data/uploads/`, mirror file at `01-Knowledge/PDFs/<slug>.md`.
6. Reply with title + page count.

**Defaults if message text is empty:** assume save intent (since user attached a PDF — they're not chatting about it).

### 4.4 Show reading list

**Input:** `show my reading list` / `what's in my list` / `reading list`

**Flow:**
1. Query items where `status IN ('unread', 'in_progress')` ordered by `saved_at DESC`.
2. Render:
   ```
   📚 12 items · 3 read (25%)
   
   - **Mamba: Linear-Time Sequence Modeling** — arxiv · unread
   - **Why RAG isn't enough** — anthropic.com · 60% · in progress
   - **Note: revisit BAML** — note · unread
   ```
3. Cap at top 15 if longer; add `… and N more. Ask 'list everything' to see all.`

**Variant: `show my list filtered by <tag>`:** filter the WHERE clause on tag match.

**Variant: `what have I read this week`:** items with `finished_at >= 7 days ago`, render with finished date.

### 4.5 Mark as read

**Input:** `mark Mamba as read` / `I finished Mamba` / `done with Mamba`

**Flow:**
1. Extract candidate title: regex captures words after "mark"/"finished"/"done with" until end or "as read".
2. Fuzzy match: `WHERE LOWER(title) LIKE '%<query>%' AND status IN ('unread','in_progress')`.
3. **0 results:** `Couldn't find anything matching 'Mamba' in your unread list. Try 'show my list'.`
4. **1 result:** update + move file + reply with stats.
5. **>1 results:** disambiguate: `Which one? 1) Mamba: Linear-Time… (arxiv) 2) Mamba whitepaper notes (note)`. Set a pending action for follow-up.

### 4.6 Update progress

**Input:** `I'm 50% through Mamba` / `50% Mamba` / `40 percent of the RAG article`

**Flow:**
1. Extract pct (regex: `\d+\s*%?`).
2. Extract title (rest of message).
3. Fuzzy match item, clamp pct 0–100.
4. Set `progress=pct`, `status='in_progress'` (or `'read'` if 100).
5. Update mirror file frontmatter.
6. Reply: `Got it — 'Mamba' at 50%. Nice halftime.`

### 4.7 Delete

**Input:** `delete Mamba from my list` / `remove Mamba`

**Flow:**
1. Fuzzy match. Disambiguate if multiple.
2. **Always confirm before deleting** (delete is destructive): `Delete 'Mamba: Linear-Time…' from your list? (yes/no)`. Set pending action.
3. On `yes` → delete row + mirror file + reply `🗑️ Deleted 'Mamba'.`.

### 4.8 Query — "what do I know about X"

**Input:** `what do I know about Mamba` / `have I read anything on RAG` / `anything in my notes about transformers`

**Flow:**
1. Full-text search across `reading_list_items` (title + summary) AND `04-People/` AND `00-Inbox/Daily/*.md` AND `01-Knowledge/Archive/`.
2. Rank by tf-idf or simple keyword frequency. (SQLite FTS5 if we can; else `LIKE %X%` on three columns + Python ranking.)
3. Render top 5 with citations:
   ```
   You've encountered 'Mamba' in 3 places:
   
   - **Mamba: Linear-Time Sequence Modeling** — saved 2026-03-14, 60% read. 01-Knowledge/mamba-linear-time-…md
   - Daily inbox 2026-04-02: "Mamba paper is interesting because state space ≠ attention"
   - Note: "Revisit BAML and Mamba for structured output benchmarks"
   ```
4. If 0 hits: `I don't have anything saved about 'Mamba'. Want me to find recent papers on it?` — offer follow-up action.

### 4.9 Suggest — "what should I read next"

**Input:** `suggest something` / `what should I read` / `give me something interesting`

**Flow:**
1. Pull unread items. If <3 items in list → suggest fresh content from RSS + arXiv instead, with a note.
2. Use `gpt-4o-mini` to rank by relevance to: user's tags, recent reads (proxy for current interest), how long the item has been sitting unread.
3. Reply with top 3 picks:
   ```
   Top of your list right now:
   
   1. **Mamba: Linear-Time Sequence Modeling** — picks up where your RAG eval reading left off. arxiv.
   2. **Why RAG isn't enough** — you started this 8 days ago, 60% done. Want to finish?
   3. **Note: revisit BAML** — your own note from 12 days ago.
   ```
4. **Variant: topic-specific** `suggest something about LLM evaluation` → rank by tag/title match.
5. **Variant: time-bounded** `15 min read` → estimate reading time from text length (~250 words/min); filter.

### 4.10 Log practice

**Input:** `practiced guitar for 45 min` / `did an hour of system design` / `coded for 90 minutes`

**Flow:**
1. Extract `{skill, minutes}` via regex/`gpt-4o-mini`.
2. Insert row: `practice_sessions(skill, minutes, logged_at)`.
3. Reply: `🎸 Logged 45 min of guitar. You're at 5 of 7 days this week, 4hr 20min total.`
4. If hitting daily goal for the first time today: `🎯 Daily goal hit (60 min). Nice.`

### 4.11 Practice status

**Input:** `how's my practice going` / `did I practice today` / `what's my streak`

**Flow:**
1. Query last 7 days from `practice_sessions`.
2. Render:
   ```
   This week:
   - Mon ✓ 60 min (guitar)
   - Tue ✓ 45 min (guitar) + 30 min (system design)
   - Wed — nothing
   - Thu ✓ 60 min (system design)
   - Fri — nothing
   - Sat ✓ 90 min (coding)
   - Sun ✓ today, 0 min so far
   
   5 of 7 days. Your most-practiced skill this week: guitar (1hr 45min).
   ```
3. No motivational language. The numbers speak.

---

## 5. Proactive flows (daily nudges)

These are scheduled jobs that don't wait for the user to chat first. The bar for sending one is high — every nudge is friction.

### 5.1 Morning brief (already built — Phase 1)

Time: 06:00. Pushed via the `combined_morning_brief` job. Renders today's reading suggestion + 3-item knowledge brief.

**Add in v2:** at the top of the brief, prepend a one-line state of yesterday: `Yesterday you read 18 min and practiced 70 min of guitar. Today's suggestion below.`

### 5.2 Mid-day reading prompt

**Trigger:** 14:00 (configurable). Only fires if today's reading minutes < daily goal × 0.5 (i.e., user hasn't read the half-time mark).

**Message (in the chat panel as a system-style banner):**
```
You haven't read yet today. 3 candidates from your list, ~10 min each:
- Mamba: Linear-Time Sequence Modeling
- Why RAG isn't enough
- BAML structured output

Want one queued up?
```

**Behavior rules:**
- Sent at most once per day.
- Suppressed if user has chatted with Ross within the last hour (they're already engaged).
- Suppressed entirely if user has muted via `set quiet hours` or `pause nudges for today`.

### 5.3 Evening reading check-in

**Trigger:** 21:00. Only if total reading minutes today < goal.

**Message:**
```
You're 8 min short of today's 15-min reading goal. 'Why RAG isn't enough' is 60% done — ~5 min left. Want to finish it?
```

Same suppression rules.

### 5.4 Practice nudge

**Trigger:** 19:00. Only if no practice session logged today AND yesterday was practiced (we don't nudge mid-week-off — that's the user choosing to rest).

**Message:**
```
No practice logged today. Your guitar streak is at 5 days. 30 min still counts.
```

Carefully avoiding the word "broken" or "lost." We say the current state, no shame.

### 5.5 Weekly review

**Trigger:** Sunday 18:00.

Writes a long-form review to `00-Inbox/Daily/YYYY-MM-DD-Weekly.md` and surfaces a one-line summary in chat:
```
This week: 8 articles read, 5 practice days (2 skills), 3 new saves. Full review → today's weekly note.
```

The review file itself has:
- What you read (with summaries)
- What you saved but didn't read
- Practice totals per skill
- Suggested focus for next week (1 unread item + 1 skill underweighted)

### 5.6 "You started but didn't finish" pings

**Trigger:** when an item has been `in_progress` for more than 14 days with no progress update.

**Once-only** message: `'Mamba' has been at 40% for 14 days. Drop it (mark abandoned) or finish? (or 'mute X' to stop asking)`

### 5.7 Discovery suggestions

**Trigger:** Sunday 11:00 (the lazy Sunday spot).

**Logic:**
- Look at most-tagged topics in last 30 days.
- Fetch 2 fresh items per top-3 topic from RSS/arXiv/Tavily.
- Rank with `gpt-4o`.
- Surface 3 picks as a chat-banner with `[Save it] [Skip] [Mute this topic]` buttons.

---

## 6. Practice tracking — schema and config

### New DB table

```python
class PracticeSession(SQLModel, table=True):
    __tablename__ = "practice_sessions"
    id: int | None = Field(default=None, primary_key=True)
    skill: str                              # normalized, e.g., "guitar", "system-design"
    minutes: int
    notes: str | None = None
    logged_at: datetime = Field(default_factory=datetime.now)
    via: str = "chat"                       # chat | timer | manual
```

### New config table

```python
class UserConfig(SQLModel, table=True):
    __tablename__ = "user_config"
    key: str = Field(primary_key=True)
    value: str

# Seeded defaults:
# - daily_reading_minutes_goal: "15"
# - daily_practice_minutes_goal: "60"
# - active_skills: "guitar, system-design, coding"
# - quiet_hours_start: "22:00"
# - quiet_hours_end: "06:00"
# - nudges_paused_until: ""   (ISO datetime; empty = active)
# - mid_day_nudge_time: "14:00"
# - evening_nudge_time: "21:00"
# - practice_nudge_time: "19:00"
```

### Config-changing commands

| Command | Effect |
|---|---|
| `set reading goal to 20 min` | `daily_reading_minutes_goal=20` |
| `pause nudges for today` | `nudges_paused_until=<today 23:59>` |
| `pause nudges for the week` | `nudges_paused_until=<+7 days>` |
| `add skill X` / `track X` | append to `active_skills` |
| `stop tracking X` | remove from `active_skills`; existing logs stay |
| `quiet hours 22 to 7` | update `quiet_hours_*` |

---

## 7. Worst cases and edge cases (engineer against these)

### 7.1 Intent misfires

| Input | Risk | Mitigation |
|---|---|---|
| `save me from this meeting` | Bare "save" → false save | Phrase-anchored regex; bare `save` never triggers |
| `bookmark a flight to Tokyo` | "bookmark" matches save phrase | Phrase regex requires "bookmark this/it"; alone won't fire |
| `delete that response` | "delete" without target | Require a captured noun; if empty, fall back to `chat` |
| `mark John as read` | Matches a person name, not an article | Search reading list FIRST; if no match, fall to chat. Don't write to People notes from `mark_read` |
| `save the world` | Random match | Phrase regex (see §4.1); no risk |
| `I'm 50% sure about X` | Fake progress signal | Require `%` near a number AND a likely-title noun phrase |
| Long URL with spaces and weird chars | URL extraction fails | Fall back to "I saw a URL but couldn't parse it — try pasting it alone" |

### 7.2 External failures

| Failure | What Ross does |
|---|---|
| Jina Reader 503 / slow | Wait 5s, fall back to "saved with URL only, summary unavailable" |
| OpenAI 429 / quota | Show `Ross: I'm out of credit for now — saved with no summary` |
| OpenAI returns empty / garbled JSON | Retry once with stricter prompt; on second failure, fall back to no-summary save |
| Obsidian REST API down | Save DB row, mark `mirror_path=null`, retry on next save (lazy reconciliation) |
| YouTube transcript unavailable | Save with title + description only |
| Paywalled article | Jina returns the paywall message; Ross stores it but flags `summary_quality=poor` so suggestions can deprioritize |

### 7.3 Concurrency / state weirdness

| Scenario | Behavior |
|---|---|
| User sends 5 messages in a row, all saves | Process sequentially; reply per-message; queue if backend busy |
| User marks "Mamba" read, then 2 sec later says "actually undo" | Within 5 min, accept `undo` → restore from Archive, set status back |
| User saves same URL twice within 1 second | Second save sees row already exists → dedup reply |
| User has 0 items, asks "show my list" | `Your list is empty. Save something with 'save in notes <url>'.` |
| User asks query with 500 hits | Cap at 5, say `… and 495 more matches. Try a more specific term.` |

### 7.4 Ambiguity in saves

| Input | Resolution |
|---|---|
| `save in notes: the Mamba paper` (no URL) | Save as freeform note. Don't try to find "the Mamba paper" automatically — too lossy |
| `save in notes: https://a.com and https://b.com` | Save both as separate items; reply lists both |
| `save in notes` with a PDF attached and no text | Use the PDF as the content. PDF wins over empty text |
| `save in notes` with a PDF AND `tldr: this paper from anthropic` | Save PDF, use the text as the title/tag hint |

### 7.5 Stale streaks and goal misfires

| Scenario | Behavior |
|---|---|
| User had a 30-day reading streak, missed a day | Today's morning brief: `Yesterday was a rest day. Resuming.` No mention of the broken streak unless asked |
| User changes reading goal mid-week | Goal applies forward only — past days keep their original goal |
| User sets goal to 0 | Treat as "no goal" — disable reading nudges entirely |
| Two skills with same name but different casing (`Guitar` vs `guitar`) | Normalize to lowercase on insert. Same skill |
| User asks "did I practice this week" on Monday morning | Counts Sun previous through Mon — show "this calendar week" not "last 7 days" |

### 7.6 Privacy and trust

| Concern | Engineering response |
|---|---|
| User saves something private (e.g., medical paper) | Treat all reading list items as private — never include in shared exports, weekly digests sent externally, etc. |
| User asks Ross to summarize a PDF that contains sensitive info | Don't echo the contents in chat replies beyond what's needed to confirm save |
| User wants to "wipe everything Ross knows about me" | `clear my reading list` should require typing `confirm clear all` separately; cascade to mirror files |
| Hallucinated summary | Always include the source URL/path in the summary reply so user can verify |

### 7.7 Worst-case user states

These are the situations where a habit-coaching bot does damage if poorly designed. Engineer specifically for them.

**The Avalanche:** User has 247 unread items and feels guilty.
- Don't show "0% read" or similar shame metric.
- Suggest: `Archive everything older than 60 days?` as a one-shot bulk action.
- Suggestions favor recent saves; old stuff gets `not suggested unless asked`.

**The Gamer:** User marks everything read without reading to inflate stats.
- We don't fight this. The metrics are for the user; if they game them, the only person they're fooling is themselves.
- BUT: don't ever reward streaks with cosmetic prizes/badges. Keep stats descriptive, not rewardful.

**The Quitter:** User stops engaging entirely for 5 days.
- After 3 days of zero activity, all nudges auto-pause until user explicitly chats.
- When they return: `Welcome back. Want today's brief, or would you rather catch up?`. No "where were you?" no streak-break drama.

**The Resentful:** User starts complaining about Ross.
- Trigger phrases: `stop nagging`, `you're annoying`, `shut up about <X>`, `mute <X>`.
- Immediate response: `Got it. Pausing nudges for the week. Tell me 'resume nudges' when you want them back.` and actually pause them.
- Log this — it's a signal that goal settings are wrong, not that the user is wrong.

**The Lost:** User asks "what can you do?"
- Reply with 5 concrete examples grounded in their actual data:
  > `Here's what I can do:
  >  - "save in notes <url>" → I'll fetch and summarize it
  >  - "show my reading list" → 12 items right now, 3 of them in progress
  >  - "what do I know about RAG" → I found 4 things in your notes
  >  - "I just read for 20 minutes" → I'll log it toward your daily 15-min goal
  >  - "suggest something" → top picks from your list
  >  - Anything else, I'll chat about it — no auto-saving.`

### 7.8 Anti-patterns Ross must avoid

These are things that look smart in design and toxic in use. Don't ship any of them.

- **Streak fire emojis.** Manipulative — they tie identity to a number.
- **"You're falling behind" framing.** No.
- **Pop-up notifications outside the chat tab.** All nudges live INSIDE the app — never on the OS level, never push notifications, never email. The user opens Ross when they want him.
- **Auto-archiving without permission.** Don't delete or hide items the user didn't action.
- **Generating summaries longer than the original.** Cap summaries at 4 sentences max.
- **Echo-chamber suggestions.** If 80% of saves are AI-related, every suggestion shouldn't be AI. Reserve 1 of 3 picks for adjacent / surprising topics.
- **Hallucinating items in the list.** When asked "what's in my list," only render real DB rows. If the LLM is involved, it sees the DB rows and reformats, never generates.
- **Implicit consent.** Every destructive action (delete, clear, mark abandoned) requires a confirmation. No "undo within X seconds" pattern — always ask first.
- **Personality drift.** Don't add jokes, memes, or pop-culture references except when the user does first. Ross is friendly, not bantery.

---

## 8. User configuration UI

A small `/settings` view in the frontend (sidebar tab). Fields:

- **Daily reading goal** (minutes, default 15)
- **Daily practice goal** (minutes, default 60)
- **Active skills** (chips, add/remove)
- **Quiet hours** (start–end)
- **Nudge channels** — toggles for: morning brief, mid-day reading, evening reading, evening practice, weekly review, discovery
- **Pause all nudges** — until tomorrow / next week / indefinitely
- **Export data** — download SQLite + a zip of `01-Knowledge/`
- **Clear data** — requires typing `clear` to confirm

Reading this list, the user should feel: *I control this. It serves me, not the other way around.*

---

## 9. Acceptance criteria for Ross v2

Ross v2 is "done" when ALL true:

1. All 12 sub-intents in §3 dispatch correctly across the manual test matrix in §10.
2. Practice tracking: log, status, weekly summary all work.
3. The 7 proactive flows in §5 fire at the right times AND respect quiet hours, pauses, and per-channel toggles.
4. Settings UI exists and changes take effect immediately (no restart).
5. Every "worst case" in §7 has been manually tested OR has an automated test in `tests/test_ross_v2_edges.py`.
6. Anti-patterns in §7.8: none present in code. Code review covers each one.
7. Reading list FTS works: `what do I know about <topic>` returns ranked results from DB + Obsidian files.
8. Cost: typical daily usage with all nudges enabled stays under $0.10/day in OpenAI tokens. Add a cost log endpoint `GET /api/usage/today` for visibility.

---

## 10. Manual test matrix (every flow, every variant)

Run all of these. Don't ship until each row passes.

### Save flows

| Input | Expected |
|---|---|
| `save in notes https://arxiv.org/abs/2312.00752` | Saved with arxiv summary, paper kind |
| `save this: revisit BAML` (no URL) | Saved as note kind, title from `gpt-4o-mini` |
| `save in notes https://youtube.com/watch?v=ABCD` | Saved with transcript-based summary |
| Upload a PDF + send `save in notes` | Saved as pdf kind, file in `data/uploads/` |
| `save in notes <same URL as 30s ago>` | Dedup reply, no second row |
| `save me from this meeting` | Falls to `chat`, no save |
| `bookmark a flight to Tokyo` | Falls to `chat`, no save |
| `save in notes` with empty body | `Ross: nothing to save — paste a URL or write what you want me to remember.` |

### List / mark / progress / delete

| Input | Expected |
|---|---|
| `show my reading list` | Renders list with stats header |
| `show my list filtered by llm` | Filtered list |
| `mark Mamba as read` (unique match) | Updates row, moves file to Archive, replies with stats |
| `mark Mamba as read` (2 matches) | Disambiguation prompt |
| `mark Xerxes as read` (no match) | Friendly not-found reply |
| `I'm 50% through Mamba` | Updates progress + frontmatter |
| `200% Mamba` | Clamps to 100, marks read |
| `delete Mamba` | Confirmation prompt; yes → delete row + file |
| `clear my reading list` | Requires explicit `confirm clear all` |

### Query / suggest

| Input | Expected |
|---|---|
| `what do I know about Mamba` | Returns hits across reading list + Obsidian files |
| `what do I know about quokkas` | `I don't have anything saved about 'quokkas'. Want me to find recent items?` |
| `suggest something to read` | Top 3 ranked picks from unread + 1 "adjacent" |
| `suggest a 15 min read` | Filtered by estimated length |
| `what's new in AI` | On-demand digest |

### Practice

| Input | Expected |
|---|---|
| `practiced guitar for 45 min` | Logged, replies with weekly count |
| `did 1hr of system design` | Same, parses "1hr" |
| `coded 90 minutes today` | Same |
| `practiced something for an hour` | Asks `What skill?` (no anonymous practice) |
| `how's my practice` | Renders weekly breakdown |
| `did I practice today` | Yes/no + minutes |

### Proactive

| Scenario | Expected |
|---|---|
| 06:00, fresh day | Morning brief in `00-Inbox/Daily/<today>-Brief.md` |
| 14:00, user has read 0 min | Mid-day reading prompt fires (banner in chat) |
| 14:00, user has chatted at 13:30 | Mid-day prompt SUPPRESSED |
| 21:00, user has read 8/15 min | Evening prompt with the unfinished item |
| 21:00, user has hit goal | No nudge |
| 19:00, no practice today | Practice nudge fires |
| 19:00, practice already logged | No nudge |
| Sunday 18:00 | Weekly review note + chat summary |
| Item in_progress 14+ days | Once-only "drop or finish" prompt |

### Settings

| Action | Expected |
|---|---|
| Set reading goal to 30 | New goal active for today's evaluations |
| Pause nudges for today | No nudges fire until tomorrow 00:00 |
| Add skill "drawing" | Practice tracking accepts "practiced drawing" |
| Quiet hours 23–7 | No nudges in window |
| `stop nagging` in chat | Auto-pause for 7 days; confirmation |

### Edge / privacy

| Scenario | Expected |
|---|---|
| OpenAI quota exceeded mid-save | Item saved with title-only; reply explains |
| Obsidian down | DB save succeeds, mirror_path null, reply mentions it |
| Jina paywalled article | Item saved with paywall snippet + flagged poor summary |
| User pastes private URL | Treated same as any URL; not shared anywhere |
| User asks `what do you know about me` | Returns reading list stats + practice stats + nothing else inferred |

---

## 11. Implementation notes for Cursor

When you build this, structure the code so each intent's handler is its own small function in `agents/knowledge.py`. The classifier (regex-based, NOT LLM — keep it deterministic) returns a sub-intent string; a dispatch dict routes to the handler.

**Run order if you're staging this across multiple sessions:**

1. **Stage A — Practice tracking.** New DB table, `log_practice` + `practice_status` handlers, basic stats. ~half day.
2. **Stage B — Query and search.** SQLite FTS5 on reading_list_items, file search across `01-Knowledge/`, `what do I know about X` handler. ~half day.
3. **Stage C — Suggestions.** Ranking logic for `suggest something`. Hooks into existing reading list. ~half day.
4. **Stage D — Proactive scheduler.** All 7 nudge jobs with quiet hours / pause respect. ~1 day.
5. **Stage E — Settings UI.** Sidebar tab + endpoints + persistence. ~half day.
6. **Stage F — PDF + YouTube extensions to save.** ~half day each.

Total: roughly 4-5 days of focused work. Do A and B first — they're the most useful and they unblock everything else.

When in doubt about a flow not listed here, prefer `chat` fallback. Adding flows is easy. Removing them after users learn them is hard.
