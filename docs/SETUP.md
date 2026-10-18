# Set up GhostBuild

Run commands from the repository root unless a step explicitly changes directory. The minimal path uses authored guides without provider calls, glasses or a Pi.

## Prerequisites

- Git, `make`, Python **3.11**, and [uv](https://docs.astral.sh/uv/).
- Node.js **20 or later** and npm.
- For G2: a paired phone, Even app and Developer Mode, with phone and laptop able to reach each other on the LAN.
- For the optional Pi station: Raspberry Pi OS, a compatible Pi camera and physically documented LED wiring. See [Pi setup](../pi/README.md).

```sh
git clone https://github.com/tanushsavadi/GhostBuild.git
cd GhostBuild
make setup
make doctor
cp .env.example .env
```

`make setup` synchronizes all Python groups, installs contract/G2 npm dependencies and rebuilds the simulator launcher. `make doctor` reports missing tools; optional lane tools are informational. If installation reports a G2 problem, rerun `cd g2 && npm ci && npm rebuild @evenrealities/evenhub-simulator` and inspect that result directly.

## 1. Start the local companion

```sh
make core
```

Open **http://localhost:8787/phone/**. Enter **“fold a paper cup”**. Ask **“Where is that?”**, return to the step and confirm it through the phone. Manual confirmation is labelled HUMAN CONFIRMED. A telemetry-dependent task cannot be completed this way.

```sh
curl -fsS http://localhost:8787/health
```

Health confirms that the service responds; it does not establish a G2 connection or a working provider. Logs and resumable session state go under `logs/` by default. A second instance should use a different port and log directory:

```sh
make core CORE_FLAGS="--port 8791 --log-dir /tmp/ghostbuild-isolated"
```

Use a separate browser/session when testing. Do not reset another operator's active session. API shapes are documented at **http://localhost:8787/docs**.

## 2. Use the official G2 simulator

Keep core running. Start these in separate terminals:

```sh
make g2-dev
```

```sh
cd g2
npm run simulate
```

The plugin connects to localhost:8787 by default. Click represents press; up/down represent swipes. Simulator output is not physical-device evidence. On question menus, swipes select and press answers. On manual action steps, swipe down confirms and advances; swipe up returns. Press opens the current picture; an answer has an explicit return. Double press goes Home (back to the task list) from any step; on the root screen it exits G2.

To exercise simulated Pi observations instead of a real device, stop the ordinary core instance and run `make core-sim`. The resulting evidence is labelled SIMULATED. Do not present it as live telemetry.

The existing `npm run sim:core` harness in `g2/` uses isolated core/Vite/simulator ports and changes task progress. Exact commands and harness assumptions live in [G2 documentation](../g2/README.md#actual-core-simulator-regression-two-generic-cards); do not run it against an active presentation session.

## 3. Connect a phone and physical G2

Use the laptop address reachable by the phone. On macOS Wi-Fi:

```sh
export BACKEND="http://$(ipconfig getifaddr en0):8787"
make g2-dev
```

`make g2-dev` reads `BACKEND` into the plugin. Keep that terminal open. In another terminal, from the repository root:

```sh
make g2-qr
```

Scan in the Even app's Even Hub tab. `make g2-qr` uses macOS `en0`; if your network uses another interface or OS, generate a QR explicitly from `g2/` with `npx evenhub qr --url http://YOUR_LAPTOP_IP:5173`. First verify the phone can open `http://YOUR_LAPTOP_IP:8787/health`.

QR development sideloading requires the phone screen to remain on. A packaged build is the appropriate lifecycle test. Guest networks may isolate devices; use a network or hotspot that permits local connections. Do not copy another operator's old IP address.

### Build the package

```sh
export BACKEND="http://$(ipconfig getifaddr en0):8787"
make g2-pack
```

Output: **`g2/ghostbuild.ehpk`**. The build generates ignored `g2/app.local.json` with the HTTP/WebSocket backend origins whitelisted. The committed localhost manifest is not suitable for a phone pointed at the laptop. A successful pack is not an install or a physical acceptance result.

For a consent-gated microphone build:

```sh
cd g2
VITE_FLAG_VOICE=1 VITE_BACKEND_URL="$BACKEND" npm run pack:lan
```

This declares the G2 microphone permission. Backend voice must also be enabled. Physical capture, gesture behavior and noisy-hall recognition require an actual device test.

## Optional providers

The server reads `.env` at startup from the working directory. The supplied example deliberately disables paid/live calls. Restart after changing backend settings. Vite flags must be present when starting/building Vite; root `.env` is not automatically the G2 Vite environment.

| Goal | Backend configuration | Notes |
|---|---|---|
| Conversational intake and contextual answers | `ANTHROPIC_API_KEY`, `GB_ASSISTANT=1` | Official SDK; default `GB_BRAIN_MODEL=claude-opus-5-5`. With no key or disabled assistant, deterministic commands/cards remain. |
| Live IKEA product search | `ANTHROPIC_API_KEY`, `GB_DISCOVERY=1`, `GB_DISCOVERY_LIVE=1` | Cached identity/manual flow is available with live search off. Search validates official product pages. |
| Compile a new task asynchronously | `ANTHROPIC_API_KEY`, `GB_LIVE_RESEARCH=1`, `GB_RESEARCH_ENGINE=compile` | Paid search/compile; `GB_LIVE_RESEARCH_MAX=3` is the default per-process cap. Generated guides remain unreviewed. |
| Explicit CREAO research/review | `GB_CREAO=1`, `CREAO_API_KEY`, `CREAO_APP_ID`, `GB_ADMIN_TOKEN` | Use your CREAO app. Approval requires a reviewer name and local admin token. |
| Live CREAO guide path | Above plus `GB_LIVE_RESEARCH=1`, `GB_RESEARCH_ENGINE=creao` | Can start a labelled unreviewed draft; distinct from human approval. |
| Optional unknown-product manual research | `GB_DISCOVERY_RESEARCH=1` | Off by default; adapter wiring is mock-tested. Keep disabled for the reliable demo unless separately verified. |
| Voice input | `GB_VOICE=1`, `ELEVENLABS_API_KEY` | Explicit user consent; phone recording generally requires localhost or HTTPS secure context. G2 needs its voice build too. |
| Spoken replies | `GB_TTS=1`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Choose an account-available voice. Plays through phone/earbuds, never a G2 speaker. |

Provider requests may incur charges. Keep all API credentials backend-only. `VITE_*` variables are embedded in public frontend output and must never hold keys. `VITE_FLAG_HEADSHAKE` remains experimental; leave it off for a reliable release.

## Source assets and caches

The clone includes authored cards, compiled demo card text and bundled first-party/demo assets. Compiled-guide third-party photographs and downloaded source material live under ignored `knowledge/live/` and may be absent in a fresh clone. Missing images use a text fallback; a cached card does not imply all its pictures are bundled.

To rebuild guides from existing local sources, use `make guides`. The IKEA adapter has its own manual builder, exact source/part checks and rights notes in [its README](../integrations/ikea/README.md). Compiling new source material requires the optional Anthropic key and makes paid requests; `make compile ARGS="--help"` shows the supported CLI.

For asynchronous external research, `make card-import FILE=envelope.json` validates an envelope into a draft. Human approval is a separate `knowledge.approve` operation; never use a software agent's name to imply a person reviewed a card.

## Optional measured Pi station

Follow [the Pi README](../pi/README.md) and run its hardware spike before the station. Record actual camera details, measurements and BCM pin in [WIRING.md](../hardware/WIRING.md); its current template is not wiring proof. Start core first, then run the Pi client with the actual reachable core URL.

The camera has a fixed external view. A fresh frame is measured; an unobstructed view is inferred. LED output is commanded, not independently observed light. A missing/frozen camera is never success. Fake-camera and replay modes remain labelled.

## Verification and recovery

```sh
make contracts
make lint-generic
make check-secrets
make test
node --test web/tests/*.mjs
cd g2 && npm run build
```

`make test` already includes the first three checks plus existing Python lanes and G2 types/Vitest. The separate web command covers companion logic. Do not infer a general formatter/linter pass: the Makefile's generic lint is a domain-boundary check.

If the companion cannot reach core, inspect the running process and port before starting another one. If the phone cannot reach it, check the address, laptop firewall and network isolation. If an image fails, retain text guidance and inspect its source cache. If a provider fails or voice is disabled, use the text and gesture paths. Final hardware verification follows [ACCEPTANCE.md](ACCEPTANCE.md); current evidence and remaining gates are in [FINAL_SPRINT_STATUS.md](FINAL_SPRINT_STATUS.md).
