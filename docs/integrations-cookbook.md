# Integrations Cookbook

> The menu of APIs and services worth plugging into your second brain, organized by agent.
> Each entry has: what it does, cost, auth model, quality of the developer experience, and which agent it should belong to.

The six integrations already scaffolded (Obsidian, Google Calendar, Plaid, RSS/arXiv, Apple Health, Receipt OCR) are documented in the code. This doc covers everything **else** worth adding.

---

## How to add a new integration

Every new integration follows the same pattern:

1. **Create a client** in `backend/src/integrations/<name>.py`. Async, typed, uses `httpx.AsyncClient` for HTTP. Reads config from `settings`.
2. **Add settings** to `backend/src/config/settings.py` and `.env.example`.
3. **Add the dep** to `backend/pyproject.toml`. Run `uv sync`.
4. **Use it from an agent.** Don't call it from API routes directly — agents own the orchestration.
5. **Optionally wrap as MCP** in `backend/src/mcp_servers/` if you want Cursor to use the same tool.
6. **Update `.cursorrules`** and this cookbook so the next-you knows it exists.

---

## Knowledge Agent integrations

### 📰 NewsAPI.org
- **What:** Aggregated news from 80,000+ sources, search and filter by keyword.
- **Cost:** Free tier (100 req/day, 24h delay), $449/mo for real-time.
- **Auth:** API key in `X-Api-Key` header.
- **DX:** ⭐⭐⭐⭐ Simple REST, well-documented.
- **Use:** Filter on your field keywords for a morning industry brief.
- **Watch out:** Free tier has 24h delay — fine for "what happened yesterday" but not breaking news.

### 🔥 Hacker News (Firebase API)
- **What:** Top stories, comments, user activity from HN.
- **Cost:** Free, no key needed.
- **Auth:** None.
- **DX:** ⭐⭐⭐⭐⭐ Stupidly simple. Just GET endpoints.
- **Use:** Pull top 30 stories daily, filter for your interests with Claude, append to knowledge digest.
- **Endpoint:** `https://hacker-news.firebaseio.com/v0/topstories.json`

### 🤖 Reddit JSON API
- **What:** Any subreddit's posts as JSON by appending `.json` to the URL.
- **Cost:** Free, but rate-limited (60 req/min). OAuth optional for higher limits.
- **Auth:** Optional. Set User-Agent header to avoid getting blocked.
- **DX:** ⭐⭐⭐ It works, but Reddit will rate-limit you aggressively without auth.
- **Use:** Monitor r/MachineLearning, r/LocalLLaMA, your field-specific subs.
- **Example:** `https://www.reddit.com/r/MachineLearning/top.json?t=day&limit=20`

### 📚 Readwise / Readwise Reader
- **What:** Consolidates Kindle highlights, Pocket, Instapaper, web articles, podcasts.
- **Cost:** $8/mo Readwise, $13/mo Reader.
- **Auth:** Bearer token from settings page.
- **DX:** ⭐⭐⭐⭐⭐ Excellent API, the export endpoint is a goldmine.
- **Use:** If you read on Kindle, this is the easiest way to get highlights into your knowledge agent.
- **Endpoint:** `https://readwise.io/api/v2/export/`

### 📺 YouTube Data API
- **What:** Your watch later, subscriptions, liked videos.
- **Cost:** Free up to 10,000 quota units/day (≈10,000 reads).
- **Auth:** OAuth — same Google credentials you already have.
- **DX:** ⭐⭐⭐ Quota math is annoying, otherwise fine.
- **Use:** Pull videos you saved for later, ask Claude which align with current focus areas.

### 📨 Substack RSS
- **What:** Every Substack publication exposes RSS at `<publication>.substack.com/feed`.
- **Cost:** Free.
- **Auth:** None for public; bring-your-own session cookie for paid subscriptions.
- **DX:** ⭐⭐⭐⭐ Standard RSS — your `knowledge_sources.fetch_rss` already handles it.

### 🐙 GitHub API
- **What:** Trending repos, your starred repos, your activity, releases of repos you follow.
- **Cost:** Free, 5000 req/hour authenticated.
- **Auth:** Personal access token.
- **DX:** ⭐⭐⭐⭐⭐ Best-in-class API.
- **Use:** Weekly "what's new in the repos I starred" digest. Track releases of tools you use.

### 🦋 Bluesky / Mastodon
- **What:** Open-protocol social feeds.
- **Cost:** Free.
- **Auth:** App password (Bluesky) or access token (Mastodon).
- **DX:** ⭐⭐⭐⭐ Both have clean APIs.
- **Use:** Pull AI/research lists, dedupe, summarize. Better signal than X for tech.

### 🎙️ Podcast transcripts
- **What:** Listen Notes API for search; Spotify Web API for podcasts you save.
- **Cost:** Listen Notes free up to 10 req/day, $20/mo for more.
- **Auth:** API key.
- **DX:** ⭐⭐⭐ Transcripts not always available; Spotify is hit-or-miss.
- **Use:** Surface episodes related to your interests, link to your knowledge agent.

### 🔍 Tavily / Perplexity / Exa
- **What:** AI-friendly web search APIs.
- **Cost:** Tavily free 1000/mo, then pay-per-call. Exa pay-per-call. Perplexity Sonar API ~$5/mo.
- **Auth:** API key.
- **DX:** ⭐⭐⭐⭐⭐ All three are designed for LLM consumption — return clean text, not HTML.
- **Use:** "What's trending in <topic> today" queries. Tavily is already scaffolded.

### 🕷️ Firecrawl / Jina Reader
- **What:** Convert any URL into clean markdown for LLM ingestion.
- **Cost:** Firecrawl free 500/mo, Jina Reader free.
- **Auth:** API key (Firecrawl) or none (Jina).
- **DX:** ⭐⭐⭐⭐⭐ Pure plug-and-play.
- **Use:** When you save an article URL, fetch + summarize on the spot.
- **Jina endpoint:** `https://r.jina.ai/<url>` — that's it.

---

## Health Agent integrations

### 🥗 USDA FoodData Central
- **What:** US government nutrition database. Comprehensive food + nutrient data.
- **Cost:** Free.
- **Auth:** API key, free signup at `fdc.nal.usda.gov/api-key-signup`.
- **DX:** ⭐⭐⭐ Schema is dense (multiple food types), but data is authoritative.
- **Use:** Look up nutrition when user logs food in natural language.

### 🥗 Nutritionix
- **What:** Easier food lookup with natural language parsing ("2 eggs and a banana").
- **Cost:** Free tier (200 req/day), $90+/mo for production.
- **Auth:** App ID + API key.
- **DX:** ⭐⭐⭐⭐⭐ Built for this exact use case.
- **Use:** Faster, nicer than USDA for natural language food logging. Worth the cost if you're serious.

### ⚖️ Withings (Health Mate)
- **What:** Smart scales, blood pressure monitors, sleep trackers.
- **Cost:** Hardware cost; API is free.
- **Auth:** OAuth.
- **DX:** ⭐⭐⭐⭐ Solid documentation, sandbox available.
- **Use:** If you have a Withings scale, this gets weight + body comp into your health agent without manual logging.

### 💍 Oura Ring
- **What:** Sleep, readiness, activity, HRV data from the ring.
- **Cost:** Hardware + Oura membership ($6/mo).
- **Auth:** Personal access token (easy) or OAuth.
- **DX:** ⭐⭐⭐⭐⭐ Genuinely excellent API. v2 endpoints return clean JSON.
- **Use:** Daily sleep + recovery summaries that the calendar agent uses to suggest workout intensity.

### 💪 Whoop
- **What:** Strain, recovery, sleep, HRV.
- **Cost:** Hardware + membership.
- **Auth:** OAuth.
- **DX:** ⭐⭐⭐⭐ Solid API, decent docs.
- **Use:** Similar to Oura. If you wear one, no reason not to pipe it in.

### 🏃 Strava
- **What:** Runs, rides, hikes, with route data.
- **Cost:** Free.
- **Auth:** OAuth.
- **DX:** ⭐⭐⭐⭐ Mature, well-documented.
- **Use:** Weekly mileage, pace trends, plug into health agent for workout context.

### 🍳 MyFitnessPal
- **What:** Their database of foods is huge. Their API is **not publicly available** anymore.
- **Recommendation:** Skip. Use USDA + Nutritionix.

### 🥦 Grocery / Recipe APIs
- **Spoonacular** — recipes, meal plans, ingredient search. Free tier 150 req/day, $30+/mo for more. ⭐⭐⭐⭐
- **Edamam** — recipe + nutrition. Free tier limited, pay-per-call. ⭐⭐⭐
- **TheMealDB** — free, basic, ⭐⭐
- **Use:** "I have chicken, rice, broccoli — what can I make?" → Spoonacular's `findByIngredients`.

### 🧾 Reality check on grocery store APIs
Consumer APIs basically don't exist:
- Instacart Developer Platform — for retail partners only.
- Kroger Public API — exists but limited and unreliable.
- Walmart — sellers only.

**Stick with receipt OCR.** It works. Already scaffolded in `receipt_ocr.py`.

---

## Finance Agent integrations

### 🏦 Plaid (already scaffolded)
- **What:** Bank, credit card, brokerage transactions.
- **Cost:** Free in sandbox + development (100 items). Production has per-call pricing.
- **Use:** Transactions sync + categorization. **Read-only.**

### 🏦 Teller
- **What:** Plaid alternative with cleaner DX, similar coverage.
- **Cost:** Free up to 100 accounts (effectively forever for personal use).
- **Auth:** OAuth + mTLS certs (more setup than Plaid).
- **DX:** ⭐⭐⭐⭐⭐ If you can deal with mTLS cert setup, the API is delightful.
- **Use:** Some prefer Teller over Plaid. Both work; pick one.

### 💳 SimpleFIN
- **What:** Open standard for bank data, lower cost than Plaid.
- **Cost:** $1.50/mo per "bridge".
- **DX:** ⭐⭐⭐ Smaller ecosystem.
- **Use:** Alternative if Plaid pricing scares you. Coverage is much smaller though.

### 📈 Brokerage / Investing
- **Plaid Investments** — works with most US brokers, positions + transactions.
- **Schwab API** — official, but cumbersome OAuth.
- **Robinhood / Webull** — no official APIs; scraping libraries exist but break constantly. Don't.
- **Use:** Consolidated portfolio view, dividend tracking. **Read-only, always.**

### 💱 Crypto
- **CoinGecko** — free price data, no key needed for low volume. ⭐⭐⭐⭐
- **Exchange APIs** (Coinbase, Kraken) — if you have accounts, **READ-ONLY KEY**, no trade permissions, ever.
- **Use:** Net worth tracking.

### 💰 Net worth tracking
- **Maybe Finance** (open-source) — has its own data model, you can self-host.
- **Use:** Roll your own. Weekly snapshot to `03-Finance/NetWorth/`.

---

## Calendar / Networking Agent integrations

### 📅 Google Calendar (already scaffolded)
- **What:** Events read + write, attendee management.

### 📧 Gmail API
- **What:** Read, label, search, send emails.
- **Cost:** Free.
- **Auth:** Same Google OAuth — just add scope `https://www.googleapis.com/auth/gmail.modify`.
- **DX:** ⭐⭐⭐⭐ Solid, but the MIME-encoded payload format is a pain.
- **Use:** Daily inbox triage. "Anything important today?" — agent reads unread, summarizes priorities.
- **Don't:** Auto-send emails. Always confirm.

### 👥 Google People (already partly scaffolded)
- **What:** Contacts, with emails, phones, organizations.
- **Use:** Sync to your `04-People/` notes. Fill in details when you mention someone new.

### 🔗 LinkedIn
- **What:** Was an option, isn't anymore for personal use.
- **Recommendation:** Skip programmatic LinkedIn. Manually note connections in `04-People/`.

### 📞 Cal.com / Calendly
- **What:** Booking pages for letting others schedule with you.
- **Cost:** Cal.com self-hosted free; Calendly $10+/mo.
- **Auth:** API key.
- **Use:** Agent can post your availability or surface upcoming bookings.

### 🎁 Reminder / Task management
- **Todoist** — clean API, free tier generous, $4/mo Pro. ⭐⭐⭐⭐⭐
- **Things 3** — no API. Skip.
- **Apple Reminders** — only accessible via AppleScript / Shortcuts on macOS. Possible but hacky.
- **Recommendation:** Just use Obsidian's Tasks plugin. The agent reads and writes markdown checklists. One less integration.

---

## Cross-cutting integrations

### 🗣️ Voice — transcription
- **OpenAI Whisper API** — $0.006/min, ⭐⭐⭐⭐⭐ quality.
- **whisper.cpp** (local) — free, 100% private, slower. Good for Apple Silicon.
- **Deepgram** — fast, real-time, free tier. ⭐⭐⭐⭐
- **Use:** Voice messages from a voice button in the React UI → transcribe → feed to orchestrator.

### 🌤️ Weather — Open-Meteo
- **What:** Forecast, historical, air quality.
- **Cost:** Free, no API key, no limits for reasonable use.
- **DX:** ⭐⭐⭐⭐⭐ Zero-friction.
- **Use:** Calendar agent factors weather into "should you bike today?" or workout planning.

### 🗺️ Maps & directions
- **Google Maps Routes API** — ETAs, travel modes, real-time traffic.
- **Cost:** Free up to $200/mo of usage. Plenty.
- **Use:** Calendar agent calculates if you need to leave by N for your next meeting.

### 🏠 Home automation
- **Home Assistant** — if you have one, its REST API exposes everything. ⭐⭐⭐⭐⭐
- **Use:** Health agent can correlate sleep quality with bedroom temp/humidity from sensors.

### 🎵 Spotify
- **What:** Listening history, playlists, currently playing.
- **Cost:** Free.
- **Auth:** OAuth.
- **DX:** ⭐⭐⭐⭐
- **Use:** Long-term log of what you listened to during focus sessions, surface correlations.

### 📷 Photo intelligence
- **Apple Photos** — no API. Skip.
- **Google Photos API** — listing/search only, no AI features. ⭐⭐
- **Use Claude vision directly** on uploaded photos. Better than any photo API.

---

## My recommended next 4 integrations after Phase 0

If you're asking "what should I add first," in this order:

1. **Gmail API** — you already have Google OAuth. Adds a scope, gives you daily inbox triage. ~1 hour.
2. **Jina Reader** — zero-auth, fetches any URL as markdown. Knowledge agent goes from "save link" to "save link + summary" instantly. ~30 min.
3. **Open-Meteo** — zero-effort, makes the calendar agent smarter about outdoor stuff. ~30 min.
4. **Withings or Oura** (whichever you wear) — gets weight/sleep into health agent without manual logging. ~2 hours including OAuth.

Save Plaid for last — it's the most complex and the most security-sensitive.

---

## Anti-recommendations

Things people ask about that I'd skip:

- **LinkedIn API** — useless for personal use now. Manual notes only.
- **MyFitnessPal API** — not publicly available. Use USDA.
- **Instagram API** — for businesses only.
- **Banking via screen scraping** — fragile, against ToS, security nightmare. Use Plaid/Teller.
- **TikTok API** — for businesses only, useless for personal.
- **Twitter/X API** — pricing is absurd ($100/mo minimum). Use Bluesky or RSS instead.
- **MyFitnessPal/Lose It scraping** — fragile. Log directly through the agent.
- **Calendar AI tools** (Motion, Reclaim) — their value is the AI. You're building the AI.
