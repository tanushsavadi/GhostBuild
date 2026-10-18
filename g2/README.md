# g2 — GhostBuild Even G2 plugin

Owner: **B**. Scaffolded from the official [`even-realities/evenhub-templates`](https://github.com/even-realities/evenhub-templates) `minimal` template (commit `8cb0135`). `src/main.ts` now shows the HUD frames core sends over `ws://<core>/ws?role=g2` (HTTP polling of `/state` if the WebView blocks WebSockets) and sends taps back. It decides nothing itself. Double-tap exits.

## Run GhostBuild on real glasses (one laptop, three terminals)

From the repo root, on branch `mvp/floor`, after `uv sync` once:

1. **Core** (simulated jig until the M5Stick is wired): `make core-sim`
   (Windows PowerShell: `$env:PYTHONPATH = ".;core"; uv run python -m ghostbuild_core --simulate-jig`)
2. **Plugin dev server**: `cd g2 && npm install && npm run dev`
3. **QR**: `cd g2 && npx evenhub qr` → scan with the Even app (Even Hub tab → Scan QR).
4. On the laptop, open `http://localhost:8787/review` → **Load on glasses** next to a procedure. Use the
   simulated-jig buttons there to play the jig; tap the temple to confirm GUIDED steps.

The plugin reaches core at the same host that served it, on port 8787. Override with
`?core=http://<ip>:8787` on the QR URL (`npx evenhub qr --url "http://<ip>:5173/?core=http://<ip>:8787"`).
The phone screen shows the connection status. If the glasses say `GHOSTBUILD OFFLINE`, open
`http://<laptop-ip>:8787/health` in the phone browser: if that fails it is the network (same Wi-Fi /
phone hotspot / firewall), not the plugin. If `/health` loads but the plugin can't connect, add a
`network` permission to `app.json` with `"whitelist": ["http://<laptop-ip>:8787"]` and rescan.

Before writing any SDK call, check it with the `everything-evenhub` skills (`sdk-reference`, `glasses-ui`, `handle-input`) and https://hub.evenrealities.com/docs.

## Hold-to-talk (voice)

**Hold the temple** to talk, **release** to send. The glasses mic opens while you hold, and the plugin buffers the
16 kHz PCM. On release (+250 ms tail) it POSTs the clip to core `/audio`. Core transcribes it with ElevenLabs
**server-side** and runs the text as a command (next / back / repeat / done / help) or a question answered from the
procedure. The HUD shows `LISTENING...` while you hold. Holds under 400 ms are ignored, and a tap right after a hold
is not counted as a tap.

- Turn it on: put `ELEVENLABS_API_KEY=...` in the repo-root `.env` (gitignored) and restart core. `/health` then shows
  `"voice": true`. `GB_VOICE=0` turns it off. Dev without a key: `GB_STT_FAKE="which leg is longer"`.
- `app.json` declares `g2-microphone`. If the phone asks for mic access, allow it.
- The phone screen shows what happened: `Listening`, `Sent 1.4 s of audio`, `Heard: "..."`, or the error.
- Not yet verified on physical G2. Check that the first word isn't clipped and how long press-to-answer takes
  (latency is logged per clip in `logs/session-*.jsonl`, kind `stt`).

## Versions

| Package | Version |
|---|---|
| `@evenrealities/even_hub_sdk` | `0.0.16` (exact pin; matches `min_sdk_version` in `app.json`) |
| `@evenrealities/evenhub-cli` | `^0.1.14` |
| `@evenrealities/evenhub-simulator` | `^0.9.5` |

`app.json` sets `min_app_version` to `2.2.10`, the floor the CLI stamps for SDK 0.0.16.

## How to run

You need Node ≥ 20 and git. Real glasses also need a phone with the **Even Realities app**, paired to the G2.

### 1. Install (once per clone)

```bash
git clone https://github.com/tanushsavadi/GhostBuild.git
cd GhostBuild
git checkout template          # until this branch is merged into main
cd g2
npm install
```

If `npm run simulate` later says `evenhub-simulator` is not recognised (we saw this on Windows), run:

```bash
npm rebuild @evenrealities/evenhub-simulator
```

### 2. Start the dev server (terminal 1)

```bash
npm run dev
```

Leave it running. It serves the plugin on port 5173 to `localhost` and to your LAN, and reloads on every save. On Windows, if a firewall prompt appears, allow Node.js on **private** networks. Otherwise the phone can't reach it.

### 3a. Run in the simulator (terminal 2)

```bash
npm run simulate
```

A window opens showing the 576×288 glasses display with `Hello from G2!`. Click the touchpad area to send a tap ("Taps: 1"). Double-tap to exit. Edits to `src/` reload automatically.

### 3b. Run on real glasses (terminal 2)

1. Put the laptop and the phone on the **same Wi-Fi** (or put the laptop on the phone's hotspot).
2. With the dev server still running:
   ```bash
   npx evenhub qr
   ```
   The CLI detects your IP and prints a QR code in the terminal. If it picks the wrong network adapter (VPN, WSL, Ethernet), pass the address yourself:
   ```bash
   npx evenhub qr --url http://<laptop-wifi-ip>:5173
   ```
   To find the Wi-Fi IP, run `ipconfig` on Windows (the "Wireless LAN adapter Wi-Fi" IPv4 address) or `ipconfig getifaddr en0` on macOS. Add `--clear` if it keeps reusing an old address.
3. Scan the QR code with the Even Realities app. The plugin opens on the glasses with hot reload.
4. Keep the phone's screen on while testing (turn auto-lock off).

### 4. Stop

`Ctrl+C` in each terminal. Double-tapping on the glasses only exits the plugin.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Simulator window is blank | The dev server isn't running. Start step 2 first. |
| Phone scans the QR, but nothing loads | Different networks, a firewall block, or the wrong IP. On the phone, open `http://<laptop-wifi-ip>:5173` in a browser; if that fails, the problem is the network, not the plugin. |
| `evenhub-simulator` not recognised | `npm rebuild @evenrealities/evenhub-simulator` |
| Port 5173 is busy | Stop the other Vite server. The QR and the simulator both expect 5173. |

### Other commands (from `g2/`)

| Goal | Command |
|---|---|
| Simulator with the automation API | `npx evenhub-simulator http://localhost:5173 --automation-port 9898` |
| Type-check | `npx tsc --noEmit` |
| Build and package `.ehpk` | `npm run pack` (or `make g2-pack` from the repo root) |

`make g2-qr` currently works only on macOS because it uses `ipconfig getifaddr`. Use `npx evenhub qr` instead.

### Simulator automation (handy for tests and screenshots)

With `--automation-port 9898`:

```bash
curl http://127.0.0.1:9898/api/ping                                     # pong
curl http://127.0.0.1:9898/api/screenshot/glasses -o glasses.png        # 576×288 RGBA
curl http://127.0.0.1:9898/api/console                                  # WebView console logs
curl -X POST -H 'Content-Type: application/json' \
     -d '{"action":"click"}' http://127.0.0.1:9898/api/input            # up | down | click | double_click
```

The simulator does not prove glyph rendering on hardware. Test `→ ● · '` on physical G2.

## Before the first Beta upload

- Add a `network` permission to `app.json` with the backend URL(s) in `whitelist`. `evenhub pack` rejects an empty whitelist, so the template ships without one.
- Run `npx evenhub pack app.json dist -c` to check that the package id `com.ghostbuild.ghostbuild` is available.

## Files

| File | Purpose |
|---|---|
| `app.json` | Even Hub manifest: name `GhostBuild`, package id, SDK floor, permissions |
| `index.html` | WebView host page; locks zoom and scroll on the phone |
| `src/main.ts` | Creates the glasses page and handles input (template demo for now) |
| `vite.config.ts` | Dev server on `0.0.0.0:5173` for QR sideloading |
