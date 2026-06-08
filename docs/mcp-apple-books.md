# Apple Books MCP — Ross + Cursor

Ross reads your **macOS Books app** library through [apple-books-mcp](https://github.com/vgnshiyer/apple-books-mcp) — highlights, in-progress books, and library stats. **Read-only.** No writes to Apple Books.

## What works

| Ask Ross in chat | Apple Books MCP tool |
|---|---|
| "What am I reading in Apple Books?" | `get_books_in_progress` + `get_recently_read_books` |
| "My recent highlights" | `recent_annotations` |
| "Highlights from Verity" | `search_annotations` |
| "Library stats" | `get_library_stats` |
| "Search my books for stoicism" | `search_books_by_title` |

Store-purchased DRM books: metadata + highlights work; full chapter text may be blocked (EPUB imports / Gutenberg titles work best).

## One-time macOS permission

The first time Ross (or Cursor) calls the MCP, macOS shows:

> **uvx** would like to access data from other apps.

Click **Allow**. Without this, tools return empty results.

The server reads only:

`~/Library/Containers/com.apple.iBooksX/Data/Documents`

## Cursor (this IDE)

Already configured in `.cursor/mcp.json`:

```json
"apple-books": {
  "command": "uvx",
  "args": ["apple-books-mcp@latest"]
}
```

**Restart Cursor** after pulling this change. Then you can ask the agent directly: *"List my Apple Books in progress"*.

## Second Brain backend (Ross in the web app)

Ross spawns the same MCP server over stdio when you ask Apple Books questions in Central Perk chat.

Optional overrides in `backend/.env`:

```bash
APPLE_BOOKS_MCP_COMMAND=uvx
APPLE_BOOKS_MCP_ARGS=apple-books-mcp@latest
```

Health check:

```bash
curl -H "Authorization: Bearer $APP_API_TOKEN" http://localhost:8000/api/integrations/apple-books/health
```

## Verify in Cursor

```bash
npx @modelcontextprotocol/inspector uvx apple-books-mcp@latest
```

## Security

- Local-only, same as the rest of Second Brain.
- Read-only access to Books container data.
- No bank/calendar scopes — separate MCP servers for those when added.

## Adding more Mac apps

Follow the same pattern:

1. Vetted MCP server on GitHub (prefer read-only, local data).
2. Add to `.cursor/mcp.json` for Cursor.
3. Wrap in `backend/src/integrations/<app>.py` using `mcp_stdio.call_mcp_tool`.
4. Route from the right agent (Ross = knowledge, Chandler = calendar, etc.).

See `docs/cursor-setup.md` and `docs/integrations-cookbook.md`.
