#!/usr/bin/env bash
# MyAIFriends — start backend + frontend (with Tailscale mobile access).
# Run this in your Mac Terminal.app, NOT inside Cursor.
# Ctrl+C stops both.
set -e

cd "$(dirname "$0")/.."

cleanup() {
  echo ""
  echo "Stopping backend + frontend..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# ── Tailscale IP ──────────────────────────────────────────────────────────────
TAILSCALE_IP=$(ifconfig 2>/dev/null | awk '/inet /{print $2}' | grep '^100\.' | head -1)

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║           MyAIFriends — Dev Server               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "  Backend  →  http://localhost:8000"
echo "  Frontend →  http://localhost:5173"
if [ -n "$TAILSCALE_IP" ]; then
  echo ""
  echo "  📱 iPhone URL: http://$TAILSCALE_IP:5173"
  echo "     (Tailscale must be ON on your iPhone too)"
fi
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# ── Backend ───────────────────────────────────────────────────────────────────
echo "→ Starting backend..."
(cd backend && uv run python -m src.api.main) &

# Give backend a moment to bind the port
sleep 3

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "→ Starting frontend..."
(cd frontend && npm run dev -- --host) &

wait
