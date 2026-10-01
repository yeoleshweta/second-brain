# Vault contract (v1)

Capture fast, structure later. One bot, one vault, one daily note.

```
SecondBrain/
├── 00-Inbox/Daily/          # YYYY-MM-DD.md — bot's only structured write
├── 00-Inbox/Unsorted/       # unparseable / no type; raw text kept
├── 01-Knowledge/Notes/
├── 01-Knowledge/Sources/
├── 01-Knowledge/MOCs/
├── 02-Health/Logs/
├── 02-Health/Reviews/
├── 03-Finance/Logs/
├── 03-Finance/Reviews/
├── 04-People/
├── 05-Calendar/
└── 99-System/Templates/
    99-System/Schemas/
    99-System/Logs/
    99-System/Dashboard.md
```

## Bot write rules

- Append only under `## Log` in `00-Inbox/Daily/YYYY-MM-DD.md`.
- Never edit or delete existing lines. Corrections are new lines.
- Never create files in `01–05`, `Career/Profile/`, or `Context/`.
- Log line: `- HH:MM emoji **type** :: text [src:: bot|user]`
- Types: `food` | `finance` | `idea` | `task` | `exercise`. If unsure → `00-Inbox/Unsorted/` verbatim.
- Failures append to `99-System/Logs/YYYY-MM-DD.md`.

## Legacy folders

Un-numbered `Inbox/`, `Health/`, `Finance/`, `People/`, `Projects/`, plus `Career/` and `Context/`, stay in the live vault. Leave them. v1 chat capture does **not** write `Inbox/YYYY-MM-DD.md`.

You own `Career/Profile/` and `Context/`. File 01–05 by hand during review.

## You still do in Obsidian

Install Periodic Notes, Templater, Dataview, and Tasks. Point Periodic Notes at `00-Inbox/Daily/` with format `YYYY-MM-DD`. Open `99-System/Dashboard.md` for review queries.
