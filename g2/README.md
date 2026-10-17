# g2 — GhostBuild Even G2 plugin

Owner: **B**. Scaffolded from the official [`even-realities/evenhub-templates`](https://github.com/even-realities/evenhub-templates) `minimal` template (commit `8cb0135`). Right now it is still the template demo ("Hello from G2!", tap to count, double-tap to exit). The GhostBuild cue renderer described in [`docs/PIVOT_GHOSTBUILD.md`](../docs/PIVOT_GHOSTBUILD.md) §5.8 replaces `src/main.ts`.

Before writing any SDK call, check it with the `everything-evenhub` skills (`sdk-reference`, `glasses-ui`, `handle-input`) and https://hub.evenrealities.com/docs.

## Versions

| Package | Version |
|---|---|
| `@evenrealities/even_hub_sdk` | `0.0.16` (exact pin; matches `min_sdk_version` in `app.json`) |
| `@evenrealities/evenhub-cli` | `^0.1.14` |
| `@evenrealities/evenhub-simulator` | `^0.9.5` |

`app.json` sets `min_app_version` to `2.2.10`, the floor the CLI stamps for SDK 0.0.16.

## Setup (once)

Needs Node ≥ 20.

```bash
cd g2
npm install
```

If `npm run simulate` says `evenhub-simulator` is not recognised (we saw this on Windows), run:

```bash
npm rebuild @evenrealities/evenhub-simulator
```

## Run

| Goal | Command (from `g2/`) |
|---|---|
| Dev server on port 5173 (LAN-visible) | `npm run dev` |
| Desktop simulator (dev server must be running) | `npm run simulate` |
| Simulator with the automation API | `npx evenhub-simulator http://localhost:5173 --automation-port 9898` |
| Real glasses via QR | `npx evenhub qr --url http://<laptop-wifi-ip>:5173`, then scan in the Even app |
| Type-check | `npx tsc --noEmit` |
| Build and package `.ehpk` | `npm run pack` (or `make g2-pack` from the repo root) |

To get the laptop's Wi-Fi IP, use `ipconfig` on Windows or `ipconfig getifaddr en0` on macOS. The phone and laptop must be on the same network. `make g2-qr` currently works only on macOS because it uses `ipconfig getifaddr`.

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
