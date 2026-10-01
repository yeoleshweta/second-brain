# Frontmatter and inline fields (v1)

Keep the field set small. Add a field only when a query you actually run needs it.

## Daily note (`type: daily`)

| Field | Meaning |
|---|---|
| `type` | Always `daily` |
| `date` | `YYYY-MM-DD` (the note's day) |
| `created` | `YYYY-MM-DDTHH:MM` when the file was first created |
| `mood` | Optional, you fill this |
| `energy` | Optional, you fill this |

## Log entry types

One list item under `## Log`. Five types only:

| Type | Emoji | Use |
|---|---|---|
| `food` | 🍽 | Meals, snacks, estimated portions |
| `finance` | 💸 | Spend, receipts, amounts |
| `idea` | 💡 | A thought worth keeping |
| `task` | ✅ | Something to do (optional `[due:: YYYY-MM-DD]`) |
| `exercise` | 🏃 | Movement, duration |

Format:

```
- HH:MM emoji **type** :: text [src:: bot|user]
```

Low-confidence extractions add `[confidence:: low]`. Corrections add `[corrects:: HH:MM]` as a new line — never edit the old one.

Anything that fits none of the five types goes to `00-Inbox/Unsorted/` verbatim.

## `src`

| Value | Meaning |
|---|---|
| `user` | You said it (chat dump, correction) |
| `bot` | The bot inferred it |
| `receipt` | Pulled from a receipt / structured source |

## `confidence`

| Value | Meaning |
|---|---|
| `low` | Bot guessed (type, amount, or wording). Filter this in weekly review. |

Omit `confidence` when the type is a clear keyword match.

## Other note types (you write these)

- **note** — `status`: `seed` \| `developing` \| `stable`; `tags`; `source` (wikilink)
- **source** — `kind`: `paper` \| `article` \| `book` \| `video`; `authors`; `year`; `read`; `rating` (1–5, usefulness to you)
- **person** — `last_contact`; `tags`
