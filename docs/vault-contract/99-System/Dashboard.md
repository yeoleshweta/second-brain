---
type: dashboard
---

# Dashboard

Review queries. Requires the Dataview plugin.

## Today's log

```dataview
TASK FROM "00-Inbox/Daily" WHERE file.day = date(today)
```

## Everything the bot guessed this week (review queue)

```dataview
LIST rows.L.text FROM "00-Inbox/Daily"
FLATTEN file.lists AS L
WHERE L.confidence = "low" AND file.day >= date(today) - dur(7 days)
GROUP BY file.link
```

## Seed notes older than 30 days (thinking debt)

```dataview
TABLE created, tags FROM "01-Knowledge/Notes"
WHERE status = "seed" AND created <= date(today) - dur(30 days)
SORT created ASC
```

## People you haven't contacted in 60 days

```dataview
TABLE last_contact FROM "04-People"
WHERE last_contact <= date(today) - dur(60 days)
SORT last_contact ASC
```
