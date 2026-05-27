# Second Brain

Personal multi-agent AI system running locally on your Mac. Custom React web UI on the front, Python (FastAPI + LangGraph) on the back, Obsidian as the source of truth.

## Layout

```
second-brain/
├── backend/      # Python: FastAPI + LangGraph + agents + MCP servers
├── frontend/     # React + Vite + Tailwind chat UI
├── docs/         # Architecture, setup, integration cookbook
└── scripts/      # Dev convenience scripts (start.sh, stop.sh)
```

## Quick start

```bash
# 1. Backend
cd backend
curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv
uv sync
cp .env.example .env                              # fill in keys
uv run python -m src.api.main                     # http://localhost:8000

# 2. Frontend (in a second terminal)
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```

Open the UI, send a message, watch it route through the orchestrator and write to your Obsidian vault.

## What's in the scaffold

| Component | Status |
|---|---|
| FastAPI backend with SSE streaming | ✅ Working |
| React + Vite + Tailwind chat UI | ✅ Working |
| LangGraph orchestrator with intent routing | ✅ Working (stub agents) |
| Obsidian integration | ✅ Working client |
| Google Calendar integration | 🔧 Stubbed with OAuth scaffold |
| Plaid integration | 🔧 Stubbed with sandbox setup |
| RSS / arXiv knowledge fetchers | 🔧 Stubbed |
| Apple Health JSON importer | 🔧 Stubbed (file watcher) |
| Receipt OCR (Claude vision) | 🔧 Stubbed |
| 4 specialist agents | 🔧 Stubs that capture to Obsidian |

See `docs/setup.md` for the full first-run walkthrough, `docs/architecture.md` for the design, and `docs/integrations-cookbook.md` for the full menu of APIs you can plug in.

## License

Personal use. Hack freely.
