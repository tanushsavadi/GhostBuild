# 08 — G2 Experience (Even Hub plugin)

**Owner:** Person B (also owns Beta packaging/QA and the loaner device). **SDK:** `@evenrealities/even_hub_sdk@0.0.16` (Even App ≥ 2.2.10). **CLI:** `@evenrealities/evenhub-cli` (0.1.14+). **Simulator:** `@evenrealities/evenhub-simulator` (0.9.x).

> Before writing any bridge code, verify API names/params with the official `everything-evenhub` skills (`sdk-reference`, `glasses-ui`, `handle-input`) and https://hub.evenrealities.com/docs. Do **not** rely on model memory. The skills on `main` target SDK 0.0.12; for `textColor`, long-press and contextual menu, the docs pages (0.0.14+) win.

## Objective
A quiet, glanceable HUD that shows **one physical action** only when the user needs it, alerts on mistakes, goes dark when the build is right, and passes Even's Beta QA checks.

## Non-goals
Rendering the 3D model on glasses; streaming video; continuous listening or a wake word; partial transcripts on glass; audio output (G2 has no speaker); custom exit UI (auto-rejected).

**Ambition-pass additions:** an ANSWER slot (§2), a contextual menu of canned questions (P1, built first), hold-to-ask voice, and a guided mode for documentation-only tasks. The HUD is still driven only by core's HUD arbiter.

> **Final reconciliation (2026-10-16).** Even Realities is the **primary** sponsor, and this plugin is the entry. The core interaction is **the next verified action + silence when correct**. Do not add more G2 UI.
> - **Contextual menu = P1** (items 1–5 below; item 5 is `WHAT NEXT?`). **Hold-to-ask voice = P2 opportunistic, never scheduled** (§16). **Guided mode = CUT** (§17).
> - A **tap is a recheck request** (05 §8); it never forces a commit.
> - No sponsor code or traffic touches the plugin: no whitelist change, no Sentry JS SDK, no Beta rebuild for sponsors.

## 0. What the Even judge must experience
instruction → physical action → mistake → corrective instruction → correct sequence → `● VERIFIED` → **dark display** (hold one beat of silence). The phone/Mac twin is for the *second* judge and must not upstage the glasses.
- **Quiet metric (E-a, measured from the session log; 10 §3):** HUD changes per run, and % of task time the display was dark or dimmed. Quote them only if measured, with n.
- **The three judge questions** (phrase card): *Who?* someone repairing or assembling with a manual and their hands full. *When?* the moment they would stop to search the manual. *Why G2?* hands in the work, eyes on the work, one action at a time, and dark when nothing is wrong.
- **On uncertainty** the HUD abstains (`CHECKING`, `ADJUST …`, `SHOW … / TO THE CAMERA`, or holds dimmed while hands are over the work). It never shows a confident physical instruction from unknown state.

## 1. Design principles (from Even's brief, verbatim intent)
- "Technology that stays in the background until the moment it becomes useful." → HUD is **event-driven**: it changes only when the next action, an alert, or progress changes.
- "One thoughtful interaction… is more valuable than a long list of features." → one instruction, one map, one status line.
- The judge's eyes never leave the work. The supervisor screen faces the *other* judge.

## 2. Page layout (576 × 288, one page, 4 containers, no `zOrderIndex`)

```
 ┌──────────────────────────────────────────────────────────────┐
 │ [1] text "instr"  x16 y24 w300 h120  border 1, pad 8          │
 │     TURN RED 2x4                         [2] image "map"      │
 │     DOT AWAY · 180°                      x336 y24 w144 h144   │
 │                                          (16×16 board, 9px    │
 │                                           cells; target       │
 │                                           footprint bright)   │
 │ [3] text "status" x16 y232 w544 h40, no border                │
 │     6/9 · LIVE                                                │
 └──────────────────────────────────────────────────────────────┘
```
- Container 4 `answer` (text, x16 y150 w300 h76, border 0, content `' '` when idle) shows `hud.answer` lines; the instruction text dims to brightness 2 while an answer shows. Total: 4 containers.
- Container 1 `instr` is the **only** `isEventCapture: 1` container (images can't capture input).
- Content ≤ 1,000 chars at create; updates via `textContainerUpgrade` (flicker-free, ~83 ms).
- Centering = space padding only (no alignment API).
- Brightness via `textColor`: 4 normal, 2 dim (hands in frame / offline). Never 0.

## 3. Modes (driven by `hud.mode` from core)

| Mode | instr | map | status | When |
|---|---|---|---|---|
| `instruct` | line1/line2 | target highlighted | `6/9 · LIVE` | next action exists |
| `instruct` + `alert` | `X WRONG SPOT` / corrective line (3 s), then normal | wrong cells + target | same | deviation |
| `hold` | same text, brightness 2 | unchanged | `watching…` | hands over board |
| `uncertain` | `ADJUST BRICK` / `PRESS IT FLAT`, `CLEAR UNKNOWN ITEM`, or (rover) `ADJUST MOTOR` / `SEAT IT SQUARE`, `SHOW MOTOR` / `TO THE CAMERA` | region highlighted | `CHECKING` | unknown part/region/component |
| `verified` | `● VERIFIED` / `MATCHES TARGET` | full board bright | `9/9` | distance 0 |
| `idle` | ` ` (blank) | blank (1-px placeholder) | faint `●` | 8 s after verified, no session, or `awaiting_goal` (rover before a goal is set) |
| `offline` *(plugin-local)* | last instruction, brightness 2 | unchanged | `OFFLINE · TAP RETRY` | WS down (core cannot send this) |
| `detail` *(plugin-local, P2)* | up to 4 diff lines | unchanged | `SWIPE ↑ BACK` | after swipe down |

`offline` and `detail` are plugin-local display states, **not** values of `hud.mode` (05 §7). The rover has no grid, so the map container shows the 1-px placeholder.

## 4. Text & glyph rules
- line1 ≤ 20 chars, line2 ≤ 28 chars (verify on hardware with `font-measurement` skill / `@evenrealities/pretext`).
- Confirmed glyphs: `→ ← ↑ ↓ ● ○ ■ □ ▲ ▶ ▼ ◀ · ° ×` and ASCII. **Not confirmed:** `✓`. Hour-2 hardware glyph test: render `✓ ✔ ● → · ° ×` once; record what shows.
- Unsupported glyphs are silently dropped by firmware — the core composer whitelists characters.

## 5. Minimap (image container)
- Plugin draws a 144×144 canvas from `hud.map` (16×16, 9 px cells): empty = off; correct part = grey 6; wrong part = grey 10 with 1-px gap; highlighted cells = white (15) + 1-px outline; board border grey 4.
- Encode PNG via `canvas.toBlob('image/png')` → `Uint8Array` → `updateImageRawData` (SDK decodes/greys PNG internally). [VERIFIED: official `image` template]
- Send **only when highlight/board changes**, never concurrently, after the text update. Expected ~100–300 ms per send (community measurement ~104 ms + ~3.9 ms/KB; flat graphics PNG ≈ 1–3 KB).
- Image placeholder must exist at `createStartUpPageContainer` (no image data at create).
- If image sends misbehave on hardware: drop the map; line2 carries the direction (MVP remains text-only-capable).

## 6. Input

| Gesture | Action |
|---|---|
| Single press | send `g2_input: tap` → core **re-checks**: re-plans on the latest committed world and re-sends the HUD; it never forces a commit or bypasses the stability vote (05 §8). When `offline`, it retries the WS. |
| Double press **at root** | `bridge.shutDownPageContainer(1)` — **required by QA; 0 or custom exit is auto-rejected** |
| Swipe down / up | `detail` view on/off (P2, plugin-local) |
| Contextual menu (OS-owned; tap-then-hold) | **P1, build first:** `menuObject` items 1 `WHY THIS STEP?` · 2 `WHERE DOES IT GO?` · 3 `CAN I SKIP?` · 4 `WHAT'S DONE?` · **5 `WHAT NEXT?`** (each ≤ 32 UTF-8 bytes, non-zero IDs) → `g2_input: menu, item_id` [V: /build/contextual-menu]. Item 2 is hidden if the 21:30 D valve fires. |
| Long press (hold-to-ask) | **P2 only, if voice ships:** `LONG_PRESS_EVENT` (9) → start PTT; `LONG_PRESS_RELEASE_EVENT` (10) → stop (§16). Otherwise a long press does nothing. |
| Single press while an answer shows | dismiss the answer |

Event handling gotchas [VERIFIED in docs/skills]:
- `CLICK_EVENT = 0` can arrive as `undefined` (protobuf drops zero) — treat missing `eventType` on a text/sys event as click.
- Docs disagree on whether clicks arrive on `textEvent` or `sysEvent` — **handle both**. Check `DOUBLE_CLICK_EVENT` **before** click.
- Handle `FOREGROUND_ENTER_EVENT` (4) → reconnect WS + re-render last HUD; `FOREGROUND_EXIT_EVENT` (5) → persist state.

## 7. Startup / lifecycle
1. `await waitForEvenAppBridge()`.
2. `createStartUpPageContainer` with all **4** containers (`instr`, `map`, `status`, `answer`; check result `0`; log 1/2/3 = invalid/oversize/OOM). Show `GHOSTBUILD` / `CONNECTING…` immediately — never a black first screen.
3. Restore `last_hud` from `bridge.setLocalStorage`/`getLocalStorage`; render dimmed.
4. Connect WS via the ladder (04 §4); send `hello`.
5. On `hud`: enqueue on the **single serial bridge queue** (latest-wins; wrap each bridge call in `Promise.race` with a 3 s timeout — a flaky BLE hop can hang ~30 s [VERIFIED: official skill]).
6. After each render → `hud_ack {hud_seq, bridge_ms}`.
7. Persist `last_hud` at most every 2 s (storage shares the BLE link).
8. Reconnect with backoff on close / FOREGROUND_ENTER; no dead sockets left open (lock-test requirement).

## 8. Phone-side page (the plugin's WebView is visible on the phone)
Plain HTML, no framework: large text mirror of line1/line2, connection rung in use, last `hud_ack` latency, a `Reconnect` button. Purpose: judge who can't wear G2 (prescription), and debugging. Must close when the plugin exits.

## 9. Permissions & manifest (`g2/app.json`)
```json
{
  "package_id": "com.ghostbuild.hud",
  "edition": "202601",
  "name": "GhostBuild",
  "version": "1.0.0",
  "min_sdk_version": "0.0.16",
  "entrypoint": "index.html",
  "permissions": [
    { "name": "network", "desc": "Connects to the GhostBuild workstation that watches your build.", "whitelist": ["…see 04 §4…"] }
  ],
  "supported_languages": ["en"]
}
```
- Name ≤ 20 chars and **must not contain "Even"** (templates ship as "Even Hub …" — rename).
- Declare only `network`. Unused permissions are flagged, so **`g2-microphone` is added only in a Beta build where P2 voice has actually shipped** (before 04:00; then re-run the permission-denial QA: mic denied → `MIC OFF · USE MENU`, menu still works). **Permission-denial QA (default build):** network denied → `OFFLINE · TAP RETRY`, no crash.
- Icon: 24×24 greyscale, 1-bit look, lit pixels in 2×2 blocks.
- No API keys in the bundle.
- Pack: `npm run build && evenhub pack app.json dist -o ghostbuild.ehpk --sdk-ver 0.0.16 -c`.

## 9b. Rover lexicon (18 v3; all within 20 / 28 chars)
`LIFT DECK` / `TO CHECK MOTOR` · `REMOVE YELLOW BAR` / `IT LOCKS THE MOTOR` · `TURN MOTOR 90° →` / **`GEAR TO THE RIGHT`** (never LEFT: the gear is on +X, the judge's right) · `PUT BACK YELLOW BAR` · `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` · `PUT BACK DECK` · `● VERIFIED` / `MATCHES TARGET` · answer `BAR LOCKS MOTOR` / `[SERVICE P.2]`. The goal text `FIX MOTOR ASSEMBLY` is a phone chip only; it never appears on the HUD.

## 10. Test paths
| Path | Command / steps | What it proves |
|---|---|---|
| Simulator | `npm run dev` then `evenhub-simulator -g http://localhost:5173` (automation: `--automation-port 9898`, `POST /api/input {"action":"click"}`, `GET /api/screenshot/glasses`) | layout, copy, input routing, mock HUD sequence |
| QR sideload | `vite` `server.host: true`; `evenhub qr --url "http://<lan-ip>:5173"`; Even app → Even Hub → Scan QR | real glasses rendering, BLE timing, glyphs; **dies on phone lock** |
| Beta | portal: Beta group (phone account email) → Builds → upload `.ehpk` → push; phone: Me → Beta tester → Install | the only mode identical to release; network ladder in a packaged build; lock / permission / exit checks |

## 11. Beta QA checklist (run Sat 20:20 first full pass · Sun 05:45 build #N, **signed by 06:45** (Fetch may not start before this) · Sun 11:00 final build)
- [ ] 5-minute phone lock → unlock: state restored, no spinner/black screen, WS reconnected
- [ ] Root double-tap → system exit dialog → `shutDownPageContainer(1)`; phone WebView closes
- [ ] Network denied / core down → `OFFLINE · TAP RETRY`, no crash, no console errors at boot
- [ ] Relaunch a first-party app (Conversate/Navigate) after exiting, without restarting glasses
- [ ] 2 minutes idle → still alive
- [ ] Glasses firmware + Even App updated (≥ 2.2.10)

## 12. Mocked path
`?mock=1` cycles `contracts/examples/hud_*.json` every 2 s; simulator automation script screenshots each mode → `g2/test/snapshots/` (visual regression by eye).

## 13. Definition of done
Real G2 shows the full demo HUD sequence from `core --mock-vision`; Beta build passes §11; p95 `bridge_ms` for text < 300 ms.

## 14. Fallbacks
Image path fails → text-only. LAN rung fails in Beta → Funnel rung. Funnel needs internet and internet is down → QR sideload on our own LAN for the demo (phone auto-lock disabled), and say so if asked. No G2 loan → simulator on a monitor + recorded through-lens video from a teammate's or Even table demo device (Even prize effectively lost; optimise for Overall).

## 15. Known risks
Doc contradictions (click routing; background behaviour; FAQ says no network calls while backgrounded); BLE congestion in a crowded hall; loaner phone OS (prefer iPhone: WKWebView keeps running when locked [VERIFIED: background-lifecycle doc]).


## 16. Hold-to-ask voice capture — **P2, only if voice starts (18 v3 §8)**; gates G1/G5 apply only then
State machine (plugin side; verify every call with the `device-features` / `handle-input` skills and /docs/build/device-apis):
```
IDLE|ANSWER --LONG_PRESS(9)--> LISTENING: audioControl(true, AudioInputSource.Glasses); send {type:"ptt",phase:"start"}; open /ws/audio if closed
LISTENING: on audioEvent → send binary 0xA1+audioPcm on /ws/audio  (never treat audio frames as taps — copy the asr template's eventTypeOf())
LISTENING --LONG_PRESS_RELEASE(10)--> THINKING: wait 250 ms tail → audioControl(false); send {type:"ptt",phase:"end"}
           guard: hold < 400 ms or zero PCM → cancel silently → IDLE
THINKING --hud.answer--> ANSWER (core arbiter owns timing/TTL)
any --FOREGROUND_ENTER(4)--> re-arm WS; audio is NOT auto-restarted
```
- The glasses mic requires `createStartUpPageContainer` to have succeeded [V].
- PCM is 16 kHz s16le mono; simulator events are 100 ms / 3,200 B [V].
- Measure press→first-PCM latency in G1. If the first word is clipped (> 300 ms), keep the mic open while the app is foregrounded and send only the PTT window. Audio outside the window is discarded on the phone.
- The asr template pins SDK ^0.0.10 and bundles an STT key. **Do not copy those parts.** Use SDK 0.0.16; keys stay on the laptop.
- **Simulator dev:** `evenhub-simulator --list-audio-input-devices`, then `--aid "<laptop mic>"`; automation `POST /api/input {"action":"long_press"}` / `long_press_release` [V].
- **Fallbacks, in order:** menu (always) → phone mic (`AudioInputSource.Phone`) → laptop lav mic triggered by the G2 long press (plugin sends only `ptt` control).

## 17. Guided mode — **CUT (final)**: no live iFixit task. Kept as history only.
Core sends `mode: "guided"` with `line1` = the step instruction (≤ 20/28 chars, abbreviated by the composer), `line2: TAP WHEN DONE`, no map. A tap → `g2_input: tap` → core marks the `user_confirm` node satisfied. The plugin always boots into the build task; only a laptop `/control/task` switches tasks.
