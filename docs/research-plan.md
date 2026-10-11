# Second Brain — research framing and test-while-building plan

> **Superseded for product direction (2026-10-11):** you chose architecture **B** — replace v1 and let Claude file/link like the LLM Wiki article. Live rules: [architecture.md](architecture.md). This file remains as the old P1 experiment; it is **not** a gate on the wiki processor.

Source: your research plan (P1 = you). Problem framing: [problem-statement.md](problem-statement.md). One person is enough. Do **not** generalize. Assume little or no real usage until weeks 1–2 produce a baseline.

**Original decision this plan was meant to inform:** what to build next — a capture-proposal flow, an LLM classifier, a changed or dropped type list, or nothing.

Until that decision, **do not** ship a proposal flow or swap keywords for an LLM classifier. Use the bot as it is. The evening tally is the first job.

---

## Framing

- **B (primary):** things worth keeping should reach the vault without a ritual phrase.
- **C (guardrail):** trust and review — the bot must not write anything you did not agree to.

Your intended uses (notes, reminders, email, inspirations, ideas) vs the bot’s five types (food, finance, idea, task, exercise): only **ideas** and **reminders→tasks** map cleanly. Most of what you expect to save may land in Unsorted no matter which classifier you use. That makes **H2 (are types worth it?)** urgent.

---

## How Might We

1. How might we make it obvious, in the moment, whether a message was saved?
2. How might we let the bot offer to save something without writing anything you didn’t agree to?
3. How might we capture things that fit none of the five types without adding a decision at capture time?
4. How might we keep review short enough that you still do it every week?

---

## Hypotheses (and how we know)

| ID | Belief | We’ll know when | We’re wrong if |
|---|---|---|---|
| **H1 missed captures** | Fewer things worth keeping are lost if the bot **proposes** a capture and waits for yes, vs requiring a phrase | Missed captures / messages you judge worth saving **falls** over two weeks vs a two-week phrase-only baseline | Count doesn’t fall, or you decline **more than half** of proposals |
| **H2 value of types** | Typing at capture is worth keeping if you **use the type in review** | Across four weekly reviews, you filter or act by type in **at least two** | You never do → log everything untyped |
| **H3 classifier** | An LLM with Unsorted fallback matches your labels more often than keywords, on ~100 real messages | Agreement is higher and wrong types do not go up | Agreement no better, or wrong types increase |

H1 is before/after on one person: it can show a change, not prove the proposal flow caused it. A real A/B does not fit.

---

## Four-week timeline

| When | What you do | What we build |
|---|---|---|
| **Weeks 1–2** | Baseline: use the bot **as is**. Evening 2-minute tally (below). | Nothing new for capture. Helper script only: count Log vs Unsorted for today. |
| **Week 3** | Blind-label ~100 messages **before** seeing bot types. Run keyword classifier on the same set. | Script to dump unlabeled user messages + run `classify_log_type` offline. **No** LLM in prod. |
| **Weeks 3–4** | **Only if** baseline missed captures are real: trial a proposal flow. Four weekly reviews (audit). | Proposal flow **gated** — not the default until the week-4 decision. |
| **End of week 4** | Decide: proposal, LLM classifier, change/remove types, or nothing. | Implement **one** of those, not all. |

Revisit framing B if the baseline shows **almost no** missed captures.

---

## Metrics (counts, baselined in weeks 1–2)

1. **Missed captures** / messages you judged worth saving.
2. **Unsorted** / all vault writes (Log lines + Unsorted files).
3. **Wrong types** / all typed Log lines (your evening judgment).
4. **Reviews done** / 4 planned.

---

## Daily protocol (weeks 1–2) — 2 minutes

Keep tallies **out of** `00-Inbox/Daily/` Log. Copy [docs/research/p1-tally.template.md](research/p1-tally.template.md) to `docs/research/local/p1-tally.md` (gitignored).

Each evening:

```bash
cd backend && uv run python ../scripts/research_daily_tally.py
```

Then record three numbers:

| Field | How |
|---|---|
| **Saved to Log** | Count from the script (lines under `## Log` today) |
| **Landed in Unsorted** | Count from the script (Unsorted files dated today) |
| **Should have been saved but wasn’t** | You: scan chat. Messages worth keeping that have no vault write |

Also note, if easy: did you use a capture phrase (`remember this` / `write this down`)?

Weekly (20 min, four times): empty Unsorted, scan Log, one line in the tally: did review happen, minutes spent, did you **filter or act by type** (yes/no).

---

## Build gates (while coding)

Do not start these until the table says so:

| Feature | Gate |
|---|---|
| Capture proposal (“save this?”) | Week 3–4 **and** missed-capture rate from baseline is not ~0 |
| LLM `classify_log_type` | After blind labels exist; compare offline first (H3); Unsorted if unsure |
| New / sixth log type | Only if Unsorted is huge **and** one missing type actually hurts |
| Remove types (untyped Log) | If H2 fails (types unused in review) |
| Auto-file 01–05 | Never in this research window |

Engineering tests (pytest) stay on: `classify_log_type`, append-only Daily, refuse 01–05. They do **not** replace P1 tallies.

---

## Data protection

- Labeled set and tallies: `docs/research/local/` (not the vault Log, not git).
- Strip other people’s names and finance details before sharing.
- Chat already goes to OpenAI; check OpenAI data settings.

---

## Week-4 decision checklist

- [ ] Missed-capture rate from 14 days: ______
- [ ] Unsorted share of writes: ______
- [ ] Types used in review (0–4 weeks): ______
- [ ] Next build: proposal / LLM classifier / change types / untyped / nothing
