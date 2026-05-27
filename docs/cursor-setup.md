# Cursor + MCP Setup

This project is built to be hacked on in Cursor. Here's how to get maximum leverage.

## 1. Install Cursor

Download from [cursor.com](https://cursor.com). Sign in, pick Claude Sonnet as your default model.

## 2. Open the project

```bash
cd second-brain
cursor .
```

Cursor auto-detects `.cursorrules`. That file is the bible — keep it updated as conventions evolve.

## 3. Python interpreter

`Cmd+Shift+P → Python: Select Interpreter` → pick `backend/.venv/bin/python`.

## 4. Useful workflows

### A. Building a new agent

1. Open in tabs: `docs/architecture.md`, `backend/src/agents/_base.py`, the agent file you're working on.
2. Open Composer (`Cmd+I`).
3. Prompt: *"Implement the knowledge agent. Read docs/architecture.md and backend/src/agents/knowledge.py. Use patterns from backend/src/integrations/knowledge_sources.py. Add a daily digest function that combines RSS + arXiv into a summary written to today's Obsidian daily note."*
4. Review every diff before applying. Don't auto-accept.

### B. Frontend feature

1. Open relevant component + `frontend/src/types/index.ts` + `frontend/src/lib/api.ts`.
2. Prompt with `@MessageBubble.tsx @types/index.ts add a thumbs up/down feedback button that POSTs to /api/feedback`.
3. Cursor will add the type, the API call, and the UI in one pass.

### C. Cross-cutting refactor

Composer multi-file edits work well here. Always reference `.cursorrules` and `docs/architecture.md` in your prompt to keep conventions intact.

## 5. MCP servers in Cursor

Cursor speaks MCP, so you can give it the same tools your agents use. Config lives in `.cursor/mcp.json` (per-project, version-controlled).

Example:

```jsonc
{
  "mcpServers": {
    "filesystem-vault": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/you/Documents/SecondBrain"
      ]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

Restart Cursor after editing.

Now you can ask Cursor *"what's the structure of my vault?"* or *"fetch https://arxiv.org/abs/... and summarize"* and it'll do it.

### Vetting MCP servers

Before adding any MCP server that touches sensitive data:
1. Look at the source on GitHub.
2. Check it's not phoning home to anywhere other than the service it claims to wrap.
3. Prefer official servers (vendor-published).
4. For finance, **write your own** — see `backend/src/mcp_servers/`.

### Useful servers

| Server | Use |
|---|---|
| `@modelcontextprotocol/server-filesystem` | Read/write your vault directly from Cursor |
| `@modelcontextprotocol/server-fetch` | Web fetching for testing prompts |
| `mcp-obsidian` (community) | Vault via REST API |
| Tavily official MCP | Search testing |
| GitHub MCP | Issue/PR workflows |

## 6. Habits

- **One feature per Composer session.** Don't let scope drift.
- **Pin the right files.** Use `@docs/architecture.md @backend/src/agents/_base.py` in prompts to scope context.
- **Review every diff.** Especially anything touching `storage/models.py` or secrets.
- **Update `.cursorrules`** when conventions shift. Cursor reads it on every prompt.

## 7. Avoid

- Don't put secrets in `.cursor/mcp.json` — use `${ENV_VAR}` references.
- Don't let Cursor edit `.env`. Keep that manual.
- Don't accept multi-file edits without reading each one.
