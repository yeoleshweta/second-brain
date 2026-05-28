# Mobile Access via Tailscale

Access your Second Brain from your iPhone (or any device) anywhere on your Tailscale network.

---

## How it works

Tailscale creates an encrypted mesh VPN between your devices. Once your Mac and phone are on the same Tailscale network, your phone can reach `http://<mac-name>:5173` directly — no port forwarding, no cloud exposure.

---

## Step 1 — Install Tailscale on Mac

```bash
brew install --cask tailscale
open /Applications/Tailscale.app
```

Sign in with Google, GitHub, or email. Your Mac will appear in the admin console at https://login.tailscale.com/admin/machines.

---

## Step 2 — Enable MagicDNS

1. Go to https://login.tailscale.com/admin/dns
2. Under **MagicDNS**, click **Enable MagicDNS**
3. Your Mac now has a stable hostname, something like `shwetas-macbook-pro` (shown in the Machines tab)

---

## Step 3 — Install Tailscale on iPhone

1. Install **Tailscale** from the App Store
2. Open it → **Sign in** with the same account as your Mac
3. Toggle the VPN on

---

## Step 4 — Start the app on Mac

Make sure both backend and frontend are running:

```bash
# Terminal 1 — backend
cd ~/Documents/Projects/second-brain/backend
uv run python -m src.api.main

# Terminal 2 — frontend
cd ~/Documents/Projects/second-brain/frontend
npm run dev -- --host
```

> The `--host` flag makes Vite listen on `0.0.0.0` so it accepts connections from other devices.

---

## Step 5 — Open on iPhone

In Safari (or any browser), navigate to:

```
http://<your-mac-name>:5173
```

For example: `http://shwetas-macbook-pro:5173`

Your full Second Brain app should load. The frontend automatically points its API calls to `<mac-name>:8000`.

---

## Troubleshooting

### Check backend is reachable from phone

Open `http://<mac-name>:8000/api/health` in the phone browser. You should get:
```json
{"status": "ok"}
```

If that doesn't work:
- Make sure Tailscale is toggled ON on both devices
- Check the Mac firewall: **System Settings → Network → Firewall → Options** — make sure `uvicorn` / `node` isn't blocked
- Try `curl http://<mac-name>:8000/api/health` from your Mac terminal first to confirm the backend is running

### MagicDNS hostname not resolving

- Open the Tailscale app on the phone → check the machine list — it should show your Mac
- Try using the Tailscale IP instead (e.g., `100.x.x.x`) — find it in the Machines tab

### Vite not accessible from phone

Make sure you started Vite with `--host`:
```bash
npm run dev -- --host
```

Or add to `frontend/vite.config.ts`:
```ts
server: {
  host: '0.0.0.0',
}
```

### Internet access (Tailscale Funnel)

If you want to reach the app when NOT on Tailscale (e.g., from a friend's network), use **Tailscale Funnel**:

```bash
tailscale funnel 5173
```

This exposes port 5173 publicly via a `*.ts.net` URL. **Use with caution** — the app is token-gated but make sure your `APP_API_TOKEN` is a strong random value first.

---

## Security notes

- All traffic between devices is encrypted by Tailscale (WireGuard under the hood)
- The backend requires `Authorization: Bearer <APP_API_TOKEN>` on every request
- Nothing is exposed to the public internet unless you explicitly enable Funnel
- If you travel and want access without your Mac running, the app is unavailable — it's local-only by design
