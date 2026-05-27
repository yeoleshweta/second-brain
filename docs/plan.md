# Build Plan — Phased Approach

> The roadmap. Build in this order. Each phase delivers real value on its own.

Trying to build everything at once is the #1 way to never finish. Resist scope creep.

---

## Phase 0 — Foundation ✅ (this scaffold)

What you have right now:
- Working React UI with chat, file upload, Plaid Link button
- FastAPI backend with SSE streaming, file uploads, Plaid endpoints
- LangGraph orchestrator with intent routing
- Six integration stubs ready to flesh out
- Obsidian working end-to-end
- 4 agent stubs that capture to your vault

**Done when:** you can message the UI, see it route to an agent, and find the captured note in Obsidian.

---

## Phase 1 — Knowledge Agent (Week 1-2)

Easiest, gives immediate daily value, establishes patterns.

**Build:**
- [ ] Replace `agents/knowledge.py` stub with real implementation
- [ ] Detect intents: "save this link", "what's new", "summarize this paper"
- [ ] For "save": fetch URL via Jina Reader → summary via Claude → append to `01-Knowledge/To-Read.md`
- [ ] Add scheduler (APScheduler) running in FastAPI lifespan
- [ ] Daily 06:00 job: pull RSS + arXiv + (optional) Tavily → ranked digest → `00-Inbox/Daily/YYYY-MM-DD-AI-Brief.md`
- [ ] Add Dataview-powered "Reading List" note to your vault

**Done when:** every morning, an AI digest shows up in your daily note, and "save this link" works.

---

## Phase 2 — Calendar/Networking Agent (Week 3-4)

Google APIs are well-documented. Builds on existing OAuth.

**Build:**
- [ ] Wire up `agents/calendar_agent.py` to `integrations/google_calendar.py`
- [ ] Add Google People API integration
- [ ] On message intent "schedule X with Y on Z": parse → confirm → create event
- [ ] Person notes: one note per contact in `04-People/<Firstname-Lastname>.md` with frontmatter (`last_contacted`, `company`, etc.)
- [ ] Daily morning briefing: today's events + suggested prep from each person's note
- [ ] Sunday job: surface people not contacted in 90+ days

**Done when:** your calendar is in the agent's hands and you have a relationship-tracking system.

---

## Phase 3 — Better Orchestration (Week 5)

Polish the conversational layer.

**Build:**
- [ ] Multi-turn memory — last N messages flow through state
- [ ] Voice messages: file upload of audio → Whisper → orchestrator
- [ ] Confirmation gates: any agent action that's irreversible asks "Confirm? [y/n]"
- [ ] Better error handling — agents shouldn't crash the chat, just apologize and log
- [ ] Add `/api/feedback` endpoint + thumbs up/down in UI for prompt improvement

**Done when:** the chat feels conversational, not transactional.

---

## Phase 4 — Health Agent (Week 6-8)

This is where most "personal AI" projects break because of integration complexity. Read `docs/integrations-cookbook.md` first.

**Build:**
- [ ] Food logging: parse natural language ("2 eggs and toast") → USDA lookup → `food_entries` table → append to `02-Health/Food/YYYY-MM-DD.md`
- [ ] Receipt upload: existing `receipt_ocr.py` → parse → write to `02-Health/Groceries/`
- [ ] Apple Health watcher: wire `apple_health.py` into the scheduler, ingest new exports → `health_metric_daily` table
- [ ] Weekly summary: weight trend, calorie average, workout consistency → `02-Health/Weekly/`
- [ ] Workout plan generation: based on recent Apple Health data + goals
- [ ] (Optional) Smart scale via Withings if you have one

**Done when:** you talk to it about food and workouts and it actually knows your stats.

---

## Phase 5 — Finance Agent (Week 9-10)

Hardest and most security-sensitive. Save for last.

**Build:**
- [ ] Encrypt Plaid access tokens at rest (use `cryptography.fernet`)
- [ ] Daily scheduler: sync transactions per linked Item, store in `transactions` table
- [ ] LLM-based recategorization for ambiguous Plaid categories
- [ ] Weekly summary written to `03-Finance/Weekly/YYYY-WW.md`: top spends, anomalies vs your own past, savings rate
- [ ] On-demand queries: "how much did I spend on coffee this month?"
- [ ] Subscription detection: recurring charges, flag unused ones

**Security checks (non-negotiable):**
- [ ] No write endpoints. No transfer. No payment.
- [ ] Tokens never logged in full.
- [ ] Confirmation required on any action that modifies state outside the vault.

**Done when:** every Sunday you get a finance review note, and you can ask spending questions in chat.

---

## Phase 6 — Proactive + Polish (Week 11-12)

Now the agents reach out to you, not just respond.

**Build:**
- [ ] Notification system: send a chat message from the system (not user-initiated) when conditions trigger
- [ ] Examples:
  - You haven't logged food in 6 hours
  - You're under-step-count for the day
  - Tomorrow's first meeting starts at 8 — leave by 7:35
  - You crossed your monthly dining-out budget
  - New paper on a topic you flagged as interesting
- [ ] Dashboard view in the React UI: today's stats + suggested actions
- [ ] Backup automation: daily git commit of vault, weekly off-site backup

**Done when:** the brain talks to you first sometimes, not just when you talk to it.

---

## Phase 7+ — Wherever you want to take it

By now you have all the patterns. Suggested directions:
- **MCP servers** — wrap your integrations so Claude Desktop / Cursor can use them directly
- **Mobile** — Telegram bot in front of the same backend, for capture on the go
- **Multi-agent collaboration** — agents talk to each other (e.g., calendar agent asks health agent if you have energy for a hard workout)
- **Local LLMs** — swap Claude for Llama via Ollama where quality isn't critical (intent classification, simple summarization)

---

## Honest time estimates

At part-time pace (a few hours per week):
- **Phase 0-1:** ~3 weeks total
- **Phase 0-3:** ~5 weeks
- **Phase 0-5:** ~10-12 weeks
- **Phase 0-6:** 3-4 months

**Stay in scope. Finish each phase before adding to the next.**
