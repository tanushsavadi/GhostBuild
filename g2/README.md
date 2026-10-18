# g2 - GhostBuild Even G2 plugin (lane B)

A quiet renderer. Core (`core/ghostbuild_core`, FastAPI :8787) pushes `HudFrame` JSON; this plugin draws it on the G2 and
sends `G2Hello` / `G2Input` back. It never decides what to say. Authority: `docs/PIVOT_GHOSTBUILD.md` §0A (+ §5.8 for the
transport plan). Types come from the generated `contracts/ts/index.ts`; nothing is hand-copied.

**Evidence status: everything below was exercised in unit tests, in `evenhub-simulator` 0.9.5, and against `core --simulate`
and a stub. None of it is hardware proof. The physical-glasses checklist at the end is for a human.**

## Versions

| Package | Version | Note |
|---|---|---|
| `@evenrealities/even_hub_sdk` | `0.0.16` (exact pin, the newest on npm) | `min_sdk_version` in `app.json` |
| `@evenrealities/evenhub-cli` | `0.1.14` | `evenhub pack/qr/init` |
| `@evenrealities/evenhub-simulator` | `0.9.5` | needs `npm rebuild @evenrealities/evenhub-simulator` after install to get the `.bin` link |
| `vitest` / `ws` / `ajv` | dev only | tests, stub server, schema check of stub frames |

SDK facts used here were read from `node_modules/@evenrealities/even_hub_sdk/dist/index.d.ts`, not from the docs. Where the docs or
the installed skills disagree with the `.d.ts`, the `.d.ts` wins (see Discrepancies).

## Layout of the code (`src/`)

| File | Role | Pure/tested |
|---|---|---|
| `view.ts` | `frameToView(frame)`: quiet -> `" "`; 1-2 centred lines; menu with `> FIX` / `  BUILD` (2 or 3 options); step frames = action cue + small counter on the dim tag line (`3/8`, `● 3/8` measured, `3/8 OK` confirmed); picture + caption (+ step counter when opened from a step); stale -> `STALE DATA`; non-live source tag | yes |
| `glyphs.ts` | whitelist sanitizer (ASCII + documented glyphs, folds the rest, `VITE_GLYPHS=ascii` fallback) | yes |
| `gestures.ts` | SDK event -> `press / swipe_up / swipe_down / hold_start / hold_end`; DOUBLE -> local exit only | yes |
| `gate.ts` | `SeqGate` (never backwards, never a duplicate seq) + `isHudFrame` runtime guard | yes |
| `controller.ts` | gate + identical-view skip + `ttl_ms` local clear + 3 s offline view + re-hello; no SDK calls | yes |
| `conn.ts` | WS `/ws?role=g2` + hello first + backoff; 4 s -> poll `GET /hud?after=` every 300 ms + `POST /hello`, `POST /input` | yes |
| `renderer.ts`, `layout.ts` | serial, latest-wins apply to the glasses; rebuild only when the layout changes | yes (fake bridge) |
| `image.ts`, `png.ts` | fetch `${backend}${image.url}`, validate PNG, size limits, latency log | yes |
| `session.ts`, `config.ts` | stored `client_id`/`session_id`/backend (SDK storage mirrored to `localStorage`), env + query config | yes |
| `voice.ts`, `bgstate.ts` | flag-gated hold-to-ask capture; feature-detected background-state API | yes/n.a. |
| `main.ts`, `phone.ts` | wiring; companion link, touch/privacy guidance, connection settings | no |

## Page model (verified against the 0.0.16 `.d.ts` + docs, simulator-checked)

* One page, three container IDs: `cue` (id 1, **the only `isEventCapture: 1`**), `tag` (id 2, dim non-capture line for `SIMULATED` /
  `REPLAY` / `2/3`), `img` (id 3, only on picture pages).
* Text-only layout: cue at x16 y72 w544 h168. Picture layout: image centred at y8 (PNG size, 288x144 for guides), caption container
  below it, tag at y248.
* `createStartUpPageContainer` runs once (text layout, blank). Text changes are `textContainerUpgrade` (id + name must match, else
  silent no-op). `rebuildPageContainer` runs **only** on text <-> picture or a different picture size (docs: "rebuild only when the
  layout itself changes"). Picture -> picture (swipe) is `textContainerUpgrade` + `updateImageRawData`, no rebuild.
* Image containers cannot be filled at startup, so a picture frame is: fetch + validate the PNG first (screen untouched), rebuild to
  the picture layout, `updateImageRawData`. Any failure (HTTP, not a PNG, size outside 20-288 x 20-144, rebuild `false`, send result
  not `success`) renders the frame's text cue instead. One in-flight bridge call at a time; newer frames overwrite the pending slot.
* `updateImageRawData` takes the **encoded PNG bytes as a `Uint8Array`** (official `image` template; the host converts to 4-bit
  grey; `imageToGray4Failed` is its failure code). We do not convert client-side.
* "Centring" is space padding. The font is proportional (a space is about half a capital), so padding = `(cols - len)` spaces with
  `cols` about 50 (measured in the simulator; **calibrate on glasses** with `VITE_CENTER_COLS`).

## Transport and honesty rules

* On every (re)connect the first message is `G2Hello {client_id, session_id|null, surface}`; core answers with the current frame
  (WS: pushed; poll mode: `POST /hello` reply). The plugin never renders its own welcome or menu.
* `session_id`: restored from storage, else `null` on a fresh install. Core (`session.py`) treats an unknown id as a new session, so
  the plugin never invents one. It adopts `HudFrame.session_id` from every frame, persists it (SDK `setLocalStorage` + `localStorage`)
  and sends it in every later hello, so a reconnect does not replay the welcome.
* Gate: a frame renders only if `seq` is strictly newer than the last accepted one; the gate resets on each reconnect because a
  restarted core restarts its seq. An identical rendered view is never re-sent to the glasses. A `ttl_ms` frame is cleared locally
  to blank when the timer fires, and is not resurrected by a reconnect replay.
* Not healthy for more than 3 s: `GHOSTBUILD OFFLINE` / `RECONNECTING` replaces whatever was shown (an old success never lingers).
  Healthy = the server answered the hello (first inbound WS message, or a successful poll).
* `stale: true` frames render `STALE DATA / CHECK LINK`. Non-`pi_live` sources always show a `SIMULATED` or `REPLAY` tag, including
  in quiet mode.
* Gestures: single press -> `press`; text-container scroll 2 -> `swipe_down`, 1 -> `swipe_up`; `LONG_PRESS_EVENT (9)` /
  `LONG_PRESS_RELEASE_EVENT (10)` -> `hold_start` / `hold_end` (core can ignore them); **DOUBLE (3), checked first in every envelope ->
  `shutDownPageContainer(1)` locally, never sent**. A press is a recheck, never a commit. Inputs are dropped (not queued) with no
  connection, because a stale recheck is meaningless later.
* Surface label: `?surface=simulator|g2`, else the simulator's hard-coded device sn (`S2001234567890`, observed) marks it
  `simulator`; hardware reports `g2`. Used on hello and inputs so a simulator run is never mistaken for the glasses.

## Configuration

| Setting | How | Default |
|---|---|---|
| Backend URL | `?backend=` query (also stored) > stored value > `VITE_BACKEND_URL` > default; editable on the phone screen | `http://localhost:8787` |
| `VITE_FLAG_VOICE` | `1` enables consent-gated hold-to-ask capture (requires physical microphone testing) | off |
| `VITE_GLYPHS` | `ascii` maps every non-ASCII glyph to ASCII (`->` `>`, bullet `*`, middle dot `-`) | `full` |
| `VITE_CENTER_COLS` | approximate characters per line for centring | `50` |

No API keys exist in `g2/` and none may be added (`make check-secrets` passes).

## Run it

Install once: `cd g2 && npm ci && npm rebuild @evenrealities/evenhub-simulator`.

### A. Simulator against the real core (simulated observations)

```bash
# terminal 1 (repo root; same env the Makefile uses)
make core-sim                         # = PYTHONPATH=... uv run python -m ghostbuild_core --simulate  (banner: SIMULATED)
# terminal 2
cd g2 && npm run dev
# terminal 3
cd g2 && npm run simulate             # evenhub-simulator "http://localhost:5173/?surface=simulator" --automation-port 9898
```

Drive core with `curl -X POST "localhost:8787/sim/scenario?name=blocked|recover|healthy"`. The simulator window: Up/Down = swipe,
Click = press, Double Click = exit dialog. Automation: `curl localhost:9898/api/screenshot/glasses -o shot.png` (RGBA, alpha > 0 =
lit), `curl localhost:9898/api/console`, `POST /api/input {"action":"click|up|down|double_click|long_press|long_press_release"}`.
The plugin logs `[ghostbuild] ready` once the page exists (wait ~4 s after launch before sending input).

### B. Simulator against the stub (no core needed)

```bash
cd g2 && npm run stub                 # node tools/stub-server.mjs  (:8787, every frame source "simulated")
cd g2 && npm run dev && npm run simulate
cd g2 && npm run sim:smoke            # scripted walk-through, PNG screenshots into g2/sim-shots/
```

Playbook flow (generic sample task, `HudFrame.mode 'step'`; stub only, **not the real core PlaybookEngine**):

```bash
cd g2 && npm run stub:playbook        # stub --flow playbook: welcome -> menu -> chooser(3) -> step 1/4 manual -> picture -> step 2/4
                                      #   -> measured step 3/4 -> press = NOT MET YET -> POST /admin/fix = CHECK PASSED -> step 4/4
                                      #   -> swipe down = completion (you confirmed) -> quiet.   swipe up = previous step.
cd g2 && npm run dev && npm run simulate
cd g2 && npm run sim:playbook         # asserts the stub phase after every simulator input + screenshots into g2/sim-shots/
```

A measured step never advances on a gesture (press = recheck only); the stub's `POST /admin/fix` stands in for measured evidence.
Step counter: `StepRef.index` is 0-based on the wire and shown 1-based. `✓` is not in the plugin's glyph whitelist (folded to `OK`);
`●` is (official table), `VITE_GLYPHS=ascii` renders it as `*`.

The stub speaks the same endpoints as core (`/ws?role=g2`, `/hud?after=`, `/hello`, `/input`, `/guides/camera_lens/*.png` with
generated 288x144 4-bit PNGs) and echoes every hello/input to its console. `POST /admin/fix` stands in for the physical fix.
`npx vite-node tools/poll-check.mts` forces the WebSocket to fail and exercises the polling fallback against any backend.

### C. Physical G2 via QR sideload (dev server, hot reload)

1. Laptop and phone on the same Wi-Fi (or the phone's hotspot). Developer Mode on in the Even app.
2. Core must be reachable from the phone: `make core-sim` (or `make core`) listens on `0.0.0.0:8787`.
3. `cd g2 && VITE_BACKEND_URL=http://<laptop-ip>:8787 npm run dev`, then `make g2-qr` or
   `npx evenhub qr --url "http://<laptop-ip>:5173"` (`make g2-qr` uses `ipconfig getifaddr en0`, macOS only).
4. Scan the QR in the Even Hub tab. Alternatively open once with `http://<laptop-ip>:5173/?backend=http://<laptop-ip>:8787`; the
   backend is then stored. Keep the phone screen on: **QR sideload dies when the phone locks** (docs). Packaged builds do not.

### D. Packaged `.ehpk` (Beta / private testing)

```bash
cd g2
VITE_BACKEND_URL=http://<laptop-ip>:8787 npm run pack:lan   # build + app.local.json + evenhub pack -> ghostbuild.ehpk
```

`app.json` (committed) names the app `GhostBuild`, package `com.ghostbuild.ghostbuild`, SDK floor 0.0.16, and whitelists
`http://localhost:8787`. `tools/gen-app-json.mjs` rewrites the network whitelist from `VITE_BACKEND_URL` (or comma-separated
`GB_BACKEND_URLS`) into the git-ignored `app.local.json`, adding the matching `ws://` / `wss://` origin. The same variable becomes
the plugin's default backend at build time. For a Tailscale Funnel fallback, use `https://<host>.ts.net` (core sends CORS `*`).

A default build declares only `network` (no microphone; docs: unused permissions are flagged at review). A **voice build**
(`VITE_FLAG_VOICE=1 VITE_BACKEND_URL=... npm run pack:lan`) makes `tools/gen-app-json.mjs` also declare `g2-microphone` (name verified in
the Packaging doc; `desc` is 1-300 chars). See "Voice (optional)" below.

`make g2-pack` runs `npm run build && evenhub pack app.json dist -o ghostbuild.ehpk --sdk-ver 0.0.16 -c`. The flags are valid for CLI
0.1.14, but (1) `-c` needs `evenhub login` (otherwise `Not authenticated ... Failed to check package ID availability`, exit 1), and
(2) it packs the committed `app.json`, i.e. a `localhost` whitelist that is useless on a phone. Use `npm run pack:lan` for a device build.

## Voice (optional, flagged; hold-to-ask)

Off by default in both halves: plugin `VITE_FLAG_VOICE=1` AND core `python -m ghostbuild_core --voice` (or `GB_VOICE=1`; `/health` then
shows `"voice":"on"`; the STT key `ELEVENLABS_API_KEY` lives only in core's environment, never in g2/). With either side off, long press
behaves as before (core ignores `hold_start`/`hold_end`) and touch/menu/phone-text paths are unchanged.

Flow (`src/voice.ts`, `core/ghostbuild_core/voice.py`): LONG_PRESS -> `hold_start` (core shows `LISTENING`) -> open `WS /ws/voice`,
`{"type":"start","consent":true}` -> `bridge.audioControl(true, AudioInputSource.Glasses)` -> `audioEvent.audioPcm` (16 kHz s16le mono,
docs: device-apis) sent as binary in ~100 ms (3200 byte) batches -> LONG_PRESS_RELEASE (or 10 s cap) -> `audioControl(false)`,
`{"type":"end"}`, `hold_end` (core shows `THINKING`, then the answer, or `DIDN'T CATCH THAT` after 8 s). Any failure
(`audioControl` false/throw, no PCM within 1.5 s, socket lost, `FOREGROUND_EXIT`, transport down, server `unavailable`) closes the mic,
sends `{"type":"abort"}` + `hold_end`, and core shows `VOICE UNAVAILABLE / USE TOUCH`. The mic is never opened outside a deliberate long
press. Output stays on the HUD (the glasses have no speaker). While voice is active the controller hands hold gestures to `voice.ts`,
which sends `hold_start`/`hold_end` itself (after the consent gate); the stub server (`tools/stub-server.mjs`) has no `/ws/voice`.

Consent: the first hold sends `{"start","consent":false}`; no mic opens and no `hold_start` is sent; core shows `HOLD TO TALK / AUDIO TO
ELEVENLABS`. A hold within 8 s of that screen stores `gb.voice_consent.elevenlabs.v1=1` (SDK storage + localStorage mirror) and records; the stored value is
sent as `consent` on every later start, and core drops audio from a start without it.

### Voice device test (human; NOT verified: needs the physical G2 + an ElevenLabs key)
- [ ] Build with `VITE_FLAG_VOICE=1`, run core with `--voice` and `ELEVENLABS_API_KEY` set; `curl :8787/health` shows `"voice":"on"`; the packed manifest lists `g2-microphone`.
- [ ] First long press: `HOLD TO TALK / AUDIO TO ELEVENLABS`, mic stays off (glasses mic indicator, if any, does not light). Second long press: `LISTENING`.
- [ ] Does the OS claim the long press (docs: tap-then-hold opens the OS contextual menu)? If `hold_start` never reaches core, record exactly which gesture sequence works.
- [ ] "where is it" -> WHERE picture; "how do I fix it" -> HOW; "what should it look like" -> CORRECT; "show the next picture"; "why does it matter" (expect `NOT IN MY CARD / SEE PHONE` for long card text, full text under phone events); "what if that didn't work".
- [ ] At the FIX/BUILD menu: "my camera view is black" -> `FIX: ...` task; "set up the station" -> BUILD task; "build a rocket" -> `NOT SUPPORTED YET`.
- [ ] Healthy + "is it fixed" -> `ALL TESTS PASSING / LIVE` only while measurements pass; it never clears a fault.
- [ ] Hold in silence 2 s: `VOICE UNAVAILABLE / USE TOUCH` (no PCM within 1.5 s). Unplug core network mid-hold: mic closes (plugin offline view), no stuck `LISTENING`.
- [ ] Background the app while holding: mic closes (`FOREGROUND_EXIT`). Check PCM frame size/rate on a real run (docs do not state chunk size; the plugin re-batches to 3200 bytes).
- [ ] Core log has `voice_transcript` lines (text only) and no audio files anywhere under `logs/`.
- Fallback if the OS claims long press on real glasses: the alternative would be a phone-side push-to-talk control using `AudioInputSource.Phone` (permission `phone-microphone`) on the `/phone` page. That is out of scope here; touch and phone-text goal entry remain the supported paths.

## Physical-device checklist (human; none of this is verified yet)

Glyphs (one frame each, read from the glasses, not the simulator):
- [ ] `● CAMERA VIEW BACK` bullet shows. `→`, `·`, `°`, `×` show (community-documented only). If any is missing build with `VITE_GLYPHS=ascii`.
- [ ] Menu marker `> FIX` / `  BUILD` aligns and reads clearly; selected option is obvious.
- [ ] Centring: two-line cue looks centred. If left or right heavy, tune `VITE_CENTER_COLS`.
- [ ] `tag` line (`SIMULATED`, `2/3`) is legible at `textColor: 2` and not distracting. Blank stays fully dark in quiet mode.

Playbook (generic step cards; physical G2 needed, none of this is hardware-verified):
- [ ] Step frame: the action cue is readable and the small dim counter (`3/8`, `● 3/8` for a measured step, `3/8 OK` after a confirm) does not crowd it; `●` shows (else `VITE_GLYPHS=ascii` -> `*`).
- [ ] **Swipe down confirms a manual step** (`OK DONE (YOU CONFIRMED)` for the last one) and moves to the next; swipe up goes back. Direction feels right on the touchpad and the ring.
- [ ] **Accidental-swipe guard:** brush the temple / scroll a few times quickly; confirm how many steps a stray swipe skips and that core's guard (not this plugin) stops a double-advance. Press must NEVER confirm a step (press = open picture / recheck only).
- [ ] A measured step does not advance on swipe; press shows `NOT MET YET`, and the step clears only when the measured evidence arrives (`● CHECK PASSED`), never from a gesture.
- [ ] Picture opened from a step: the 288x144 picture is legible, the caption and `2/8  PIC 1/2` counter are readable under it; press or swipe up returns to the same step; a failed image fetch shows the text cue.
- [ ] Chooser (3 options, `> ` marker): swipe moves one option per swipe, press selects, double press still exits; all three rows fit the container.
- [ ] Double press during a step shows the system exit dialog and sends nothing to core.

Input:
- [ ] Single press arrives once (not twice). Swipe down/up map the right way (down = next view).
- [ ] Double press shows the system exit dialog; cancel keeps the app working; nothing was sent to core (check core log).
- [ ] Long press: does `hold_start`/`hold_end` reach core, or does the OS menu claim it (docs: tap-then-hold opens the OS menu)?
- [ ] Ring (R1) gestures behave the same, if available.

Pictures:
- [ ] The 288x144 guide is legible on the real display (16 greys, green): WHERE / HOW / CORRECT.
- [ ] Time from press to picture, and from swipe to next picture (the plugin logs `fetch/rebuild/send/total` ms in the WebView console; phone-side inspect needed). Page rebuild flicker acceptable?
- [ ] A forced failure (stop core between frame and image fetch) shows the text cue, not a blank page.

Lifecycle and network:
- [ ] Phone face down, screen off, 5 minutes (use a packaged build, not QR): reconnects, correct current frame, no welcome replay.
- [ ] Packaged build can reach `http://<lan-ip>:8787` (HTTP + CORS + whitelist) and a WebSocket to it. If the WS is blocked, the 4 s poll fallback should take over; confirm the cue latency (< 500 ms WS; ~300 ms polling).
- [ ] Kill core: `GHOSTBUILD OFFLINE / RECONNECTING` within about 3 s of loss; restart core: recovers without reopening the app.
- [ ] Network permission denied / WebView suspended on Android: no crash, offline view.
- [ ] Never an old success (`● ... BACK`) left on screen while disconnected.

## Discrepancies and caveats found

* The `everything-evenhub:background-state` skill documents `setBackgroundState` / `onBackgroundRestore`; SDK **0.0.16 does not export
  them** (absent from `index.d.ts` and `index.js`). The official Background & Lifecycle page does not use them either: it says to persist
  to `localStorage`. `bgstate.ts` feature-detects them; today persistence is `setLocalStorage` (+ `window.localStorage` mirror) and a
  re-hello + forced redraw on `FOREGROUND_ENTER`.
* The `sdk-reference` skill is for 0.0.12 and omits `textColor`, `menuObject`, `LONG_PRESS_EVENT (9)` and `LONG_PRESS_RELEASE_EVENT (10)`;
  the 0.0.16 `.d.ts` has them.
* `docs/08_G2_EXPERIENCE.md` says `→ ← ↑ ↓ ● ○ ■ □ ▲ ▶ ▼ ◀ · ° ×` are "confirmed". The official docs only list the geometric/selection set
  (`●○■□▲△▶▷▼▽◀◁★☆`); the arrows and Latin-1 symbols come from the community glyph table (simulator-tested, "real hardware may differ").
* The old template README said `evenhub pack` rejects an empty whitelist; CLI 0.1.14 packed an empty whitelist, a bare hostname, a path
  and `ws://` entries without complaint. The host app or portal may still validate. Not verified.
* Simulator caveats (docs): no BLE timing, image decode is faster and ignores device size limits, no LZ4 path, glyph rendering is not
  pixel-exact. The simulator's logged `total` image time is therefore meaningless for hardware.


## Final sprint reliability checkpoint (2026-10-17)

`npm test`: **183 passing**. `npm run build`: **PASS** (TypeScript + production Vite).
Official simulator 0.9.5 playbook walkthrough: **15/15 phases pass**, including two actual SDK image sends,
manual completion, a measured step that refuses swipe completion, and quiet after completion. This run used the
**simulated stub**, not live hardware or a provider. Screenshots are local artifacts under `sim-shots/final-sprint/`.
The simulator returns green RGBA pixels with brightness in alpha; inspect alpha, rather than stripping transparency.

Reconnect now resets health before accepting a restarted backend's lower sequence. Poll hello replies reset health
before their HUD frame, and obsolete HTTP responses cannot overwrite a new socket/backend or revive a stopped app.
An expired transient success reconnects to quiet instead of being stuck OFFLINE. Failed SDK text upgrades rebuild
the current cue immediately; thrown image transfers show the text fallback. Foreground redraw preserves the newest
queued frame and remains serialized with image sends.

ElevenLabs consent has a new provider-specific storage key, so a retired provider's consent cannot authorize the
new processor. Socket construction failure never opens the microphone, and background/disconnect abort cancels
a pending voice response after release. GhostBuild does not save microphone recordings. Sustained G2 capture and
provider STT remain **NOT physically verified**; this build uses intentional hold-to-talk only when flagged.
The phone landing screen links to `/phone/` in a separate browsing context and keeps connection settings available.
