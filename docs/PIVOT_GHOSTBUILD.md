# GhostBuild — PIVOT (authoritative from Sat 2026-10-17 15:45 PDT)

> **Superseded (Sat 2026-10-17 evening):** GhostBuild v2 (guided builds + test jig + Creao compiler) replaces this plan. `CLAUDE.md` is the execution authority. Kept for history and G2 notes only.

> This document supersedes docs/00–21 wherever they conflict. Those docs are **historical**: the LEGO rocket/rover, perception, CAD, spatial/RealityKit, twin, minimap and every sponsor integration are **cut**. The old docs are still useful for G2 platform notes (08 §2–§6 text and glyph rules) and the honesty labels. Times below are PDT. Deadline: **Sun 12:00**.

---

## 0. The decision in one screen

| | |
|---|---|
| **Product** | **GhostBuild: a closed-loop repair copilot.** The device being repaired runs its own tests. G2 says one thing only when a test fails, and the fix itself clears the message. |
| **Tagline** | *Quiet until it breaks. Silent once it's fixed.* |
| **Pattern** | **ASSIST + GLANCE.** Assist: the AI reads the documentation ahead of time, and a deterministic engine watches live telemetry. Glance: a one-second, two-line cue. READ is an optional one-page "why" (P1). LISTEN is cut. |
| **Hero cue** | `CHECK ECHO WIRE` / `→ PIN 10` |
| **Differentiator** | **The fix is the input.** Nobody taps "done". The hardware confirms the repair, and the glasses go dark. |
| **Hero demo** | A broken automatic gate: an ultrasonic sensor, a servo arm, and an end-stop micro switch. The judge repairs a real wiring fault without touching the phone. The gate lifts, the end-stop confirms it, G2 shows `● GATE VERIFIED`, then goes blank. |

---

## 1. Phase A — red team: three concepts

### Concept 1 — Closed-loop bench copilot (the device talks, the fix replies)
- **Promise:** "Work on your circuit. GhostBuild stays silent until a test fails, tells you the one thing to check, and confirms when your hands have fixed it."
- **User and moment:** a maker or student repairing a microcontroller project that stopped working. Their hands are holding a jumper wire and their eyes are on the breadboard.
- **G2 shows:** nothing while the device is healthy. On a failure it shows one fact and one action. When the fix lands, it shows `SENSOR OK`, then blank.
- **Physical world:** a real wire is reseated, a real switch is flipped, a real arm lifts and presses a real end-stop.
- **Why phone-only is worse:** the value is cause and effect within about a second, in the same field of view as your hands. A face-down or locked phone can't deliver that. A propped-up phone pulls your eyes off the connector at exactly the moment you need to watch it.
- **Originality:** the glasses become an instrument on the test bench. The cue is triggered by the device's own tests and dismissed by the physical repair.
- **Wow moment:** the judge flips the power switch, the cue changes instantly, they push one wire in, and `SENSOR OK` appears before they look up.
- **Risk:** medium. The hardware is cheap and well documented. The biggest risk is Even WebView networking.
- **Effort:** about 6–8 h per lane to the first end-to-end run.

### Concept 2 — Verified build-along (wire the gate from scratch)
- **Promise:** "Build the circuit one wire at a time; each wire is verified before the next appears."
- **G2 shows:** a cue for every step (`WIRE 3/7: ECHO → PIN 10`) and a confirmation after each one.
- **Phone-only worse?** Somewhat. It is hands-busy, but it is basically a paged tutorial.
- **Originality:** medium. Step-by-step assembly is the most common AR demo.
- **Problems:** **loud by construction**, since a cue is always on screen. The judge has to wire seven connections (2–3 min). Firmware can't reliably detect *every* connection before the circuit is complete.
- **Effort:** higher than Concept 1, and the demo is longer.

### Concept 3 — Hands-free manual (LISTEN + READ)
- **Promise:** "Ask the datasheet a question out loud and get a few words back."
- **G2 shows:** `ECHO → PIN 10` after you ask "where does echo go?"
- **Phone-only worse?** Only marginally. This is ChatGPT with a PDF plus a microphone.
- **Originality:** low. Judges will have seen it ten times.
- **Problems:** a noisy hall breaks speech recognition. It needs network STT. Nothing is verified, and the judge has to invent a question.
- **Effort:** low to medium, but demo reliability is low.

### Against the five Even criteria (qualitative; these are not judging probabilities)

| Criterion | 1 Closed-loop | 2 Build-along | 3 Hands-free manual |
|---|---|---|---|
| Made for G2 | **Strong.** Feedback lands in line of sight while the hands work. | Good, hands-busy. | Weak. The answer would be just as good on a watch or phone. |
| Quiet by design | **Strongest.** Healthy means blank; a cue exists only while a fault exists. | Weak. Always showing a step. | Medium. Speaks only when asked. |
| Originality | **High.** Telemetry-triggered and repair-dismissed. | Medium. | Low. |
| Experience & polish | High. Three or four total screens. | Medium. Long flow. | Low in a noisy hall. |
| Execution | High. Cheap kit, deterministic engine. | Medium. | Medium-low. Depends on STT. |

### Selection checks A–I

| Check | Winner | Why |
|---|---|---|
| A. Most natural ASSIST + GLANCE | 1 | AI and engine work out of sight; the lens shows one result. |
| B. Useful with the phone face down | 1 | The whole loop runs without the phone screen. 3 needs a mic pipeline; 2 needs constant cues. |
| C. Fewest interruptions | 1 | About 4 cues per repair, 0 while healthy. |
| D. Clearest one-second cue | 1 | Cue words match the labels printed on the hardware ("ECHO", "10"). |
| E. Least like reading docs on a phone | 1 | The docs live behind the cue. 3 *is* reading the docs. |
| F. Most dramatic genuine physical outcome | 1 = 2 | Both lift a gate. Only 1 shows failure, then recovery, then verification. |
| G. Easiest for a first-time judge | 1 | One sentence of instruction. The device leads. |
| H. Repeatable with minimal setup | 1 | Reset means pulling one wire (about 5 s). 2 needs a full re-wire. |
| I. Highest chance of a polished Beta | 1 | One text container and three gestures. |

**Winner: Concept 1.** It beats 2 because it is quiet by construction, not by restraint. It beats 3 because it is grounded in measured physical evidence, not a chatbot. Concept 2's "verified step" idea survives as the functional gate test.

---

## 2. Phase B — final experience design

1. **Name/tagline:** GhostBuild (Even Hub app name `GhostBuild`, 10 chars, no "Even"). *Quiet until it breaks. Silent once it's fixed.*
2. **Persona and moment:** Maya is a second-year student whose capstone gate stopped opening the night before demo day. She is hunched over the breadboard, holding a jumper in one hand, unsure which of eleven wires is wrong. The moment is "it doesn't work and I don't know why".
3. **10-second pitch:** "GhostBuild turns your glasses into a quiet test bench. Your device tests itself; when something fails, G2 tells you the one wire to check, and when your fix works, the device confirms it and the glasses go dark."
4. **Why G2 and not a phone:** repair is a tight loop: look at the connector, move it, see whether it worked. That loop's value is **latency and co-location**. The confirmation has to land within about a second, in the same field of view as your hands, so you know *this* wire was the cause. A phone either pulls your eyes away (propped up), arrives late (notification, pick up, unlock), or never arrives (face down). On G2, the instruction appears when power goes off, and `SENSOR OK` appears while you're still looking at the wire you just pushed in. Take away the glasses and you are back to "fix, look at the screen, fix, look at the screen".
5. **Single memorable differentiator:** **the fix is the input.** No "done" button anywhere. Measured evidence advances the state.
6. **Every G2 screen.** One text container, at most 2 lines. Line 1 ≤ 18 chars (the fact), line 2 ≤ 24 chars (the one action). Glyph whitelist: `A–Z 0–9 space · → ● + - / ' .` (B verifies `→ ●` in the hour-1 glyph test; if `→` drops, use `-`).

| # | Event (deterministic trigger) | Line 1 | Line 2 | Clears when |
|---|---|---|---|---|
| S0 | App opened, device healthy | `GHOSTBUILD ON` | `QUIET MEANS OK` | 3 s |
| S1 | App opened, no telemetry for 3 s | `NO DEVICE FOUND` | `PLUG IN USB` | telemetry arrives |
| F1 | A test fails for ≥ 1.5 s while power is on | `SENSOR SILENT` | `SWITCH POWER OFF` | power goes off (→ F2) or test passes |
| F2 | Power goes off while a fault is open (check chosen from evidence, §6) | `CHECK ECHO WIRE` | `→ PIN 10` | test passes after power-on, or superseded |
| F3 | Power back on, same test still failing after 3 s | `STILL SILENT` | `SWITCH POWER OFF` | power off → next check (F2 with check k+1) |
| U1 | All documented checks tried | `NOT SURE WHY` | `SEE WIRING ON PHONE` | test passes; dims after 30 s (P1) |
| K1 | Failed test passes for ≥ 1 s | `SENSOR OK` | `WAVE TO TEST GATE` | wave, or 15 s (then blank; test stays pending) |
| V1 | Servo commanded open **and** end-stop closed within 1.5 s | `● GATE VERIFIED` | | 3 s, then **blank** |
| F4 | Servo commanded open, end-stop **not** closed within 1.5 s | `GATE DIDN'T OPEN` | `SWITCH POWER OFF` | power off → `CHECK SERVO WIRE` / `→ PIN 6` |
| V0 | Build without an end-stop installed (config flag) | `GATE COMMANDED` | `ARM NOT MEASURED` | 3 s |
| O1 | Telemetry lost > 5 s with no open fault | `DEVICE OFFLINE` | `CHECK USB CABLE` | telemetry returns |
| P1 | Single press, healthy | `ALL TESTS PASSING` | `LIVE` | 3 s |
| P2 | Single press, fault open | (repeat the current cue) | | as that cue |
| L1 | Plugin cannot reach backend (plugin-local) | `GHOSTBUILD OFFLINE` | `TAP TO RETRY` | reconnect |
| W1 | Swipe down on a fault cue (P1, READ) | one page from the card's `why` + source tag, e.g. `ECHO PULSES AFTER EACH PING. NONE FOR 1.5S.` / `HC-SR04 DATASHEET` | | swipe up or 8 s → back to cue |

7. **When the display clears:** healthy means blank. Success screens last 3 s. Status lasts 3 s. A fault cue stays **only while the fault is real**: it is the one useful thing, and it clears itself when the evidence changes. A cue is never re-sent if it hasn't changed. At most one new cue per 2 s.
8. **G2 inputs (documented only):** **single press** = repeat the current cue or show status (a recheck, never a commit). **Double press** = the system exit dialog (`shutDownPageContainer(1)`, canonical). **Swipe down/up** = why page / back (P1). Nothing else. The R1 ring works the same way.
9. **Phone companion scope (A):** one page served by the backend at `/phone`. (a) **Wiring card:** an SVG of the real wiring, with the pin from the current cue highlighted. (b) **Why and sources:** each check's explanation, the datasheet quote with page, and a provenance badge. (c) **Evidence timeline:** "15:42:07 echo pulses: none for 1.5 s (MEASURED LIVE)", "15:42:31 end-stop closed 640 ms after open command". (d) A live/simulated source banner. It is never needed during the hero loop.
10. **Withheld from G2 on purpose:** citations, raw readings (cm, µs), test names, step counts or progress, timeline, confidence numbers, wiring diagram, the "why" (unless swiped), anything about passing tests.
11. **Honest uncertainty:** all cues say `CHECK …`, never `… IS DISCONNECTED`. Evidence narrows the *order* of checks, not the conclusion. When the documented checks run out, it says `NOT SURE WHY`, not a guess. `VERIFIED` requires the measured end-stop. A sensor pass is `SENSOR OK`, not "repaired". No telemetry means `OFFLINE`, never a stale OK. No AI model decides any physical state at runtime.
12. **Before/after:** *before*, you wave at the gate and nothing happens. *After*, you wave, the arm lifts, the end-stop clicks, and the glasses briefly say `● GATE VERIFIED`. Wave again: the gate works and **the glasses say nothing**. That silence is the demo's last beat.

---

## 3. Phase C — hero demo

**Hardware (C):** Arduino Uno, HC-SR04, SG90 servo driving a foam-core arm, lever micro switch as the end-stop at the open position, slide/toggle **POWER** switch on the sensor and servo 5 V rail (Arduino stays on USB and reads the rail on a sense pin), green LED. Pins: TRIG 9, ECHO 10, SERVO 6, END-STOP 7 (INPUT_PULLUP), RAIL-SENSE 8 (10 kΩ pull-down), LED 13. Arduino headers and HC-SR04 pins get masking-tape labels **exactly as the cues name them**. Add a 470 µF capacitor across the servo rail to stop brownout resets. If no switch is in stock, USB unplug acts as "power off": the backend sees the link drop, and the cue text becomes `UNPLUG USB` instead of `SWITCH POWER OFF`.

**Faults we inject physically (rotate between judges; never software-faked):**
- **A, echo unplugged** (default): `SENSOR SILENT` → `CHECK ECHO WIRE → PIN 10`.
- **B, trig unplugged:** echo line idles low (sensor powered, echo connected) → `CHECK TRIG WIRE → PIN 9`. This shows the cue depends on evidence, not a script.
- **C, servo signal unplugged:** the sensor is fine. The judge waves, the arm doesn't move → `GATE DIDN'T OPEN` → `CHECK SERVO WIRE → PIN 6`.

**60-second version (Tanush narrates, judge wears G2, phone face down on the table):**
- 0:00 "This gate should open when you wave at it. It's broken. Fix it; the glasses will help." The judge waves and nothing happens.
- 0:08 G2: `SENSOR SILENT` / `SWITCH POWER OFF`. The judge flips the switch.
- 0:12 G2 changes instantly: `CHECK ECHO WIRE` / `→ PIN 10`. "It changed because *you* did something."
- 0:15–0:35 The judge finds ECHO and 10 and pushes the wire in, then turns power on.
- 0:37 `SENSOR OK` / `WAVE TO TEST GATE`. The judge waves, the arm lifts, the end-stop clicks.
- 0:40 `● GATE VERIFIED`, then **blank**. "It didn't say verified because you finished. A switch the arm physically pressed said it."
- 0:48 The judge waves again. The gate works and the glasses stay silent. "Quiet means OK."
- 0:55 "The phone never left the table. The AI did its work ahead of time: it read the datasheets and built this repair card. The glasses only show the result."

**90-second version:** the 60 s script plus (a) a single press → `ALL TESTS PASSING` (shows that blank isn't broken), (b) flip the phone over to show the evidence timeline and the datasheet quote behind the cue, with the AI-EXTRACTED / VERIFIED-QUOTE badges, (c) one line on generality: "a new device is a new datasheet plus our 20-line telemetry sketch".

**Reset (≤ 15 s):** power off, pull the fault wire for the next scenario (rotate A → B → C), power on. The backend detects the fault on its own. Wipe the lens. Check G2 battery and Arduino link every 3 judges.

**Evidence and functional test:** `SENSOR OK` = echo pulses present in at least 3 of the last 5 samples, with a range within the datasheet's 2–400 cm. `VERIFIED` = the open command transitions **and** the end-stop reads closed within 1500 ms. Both events are logged with timestamps and shown on the phone timeline.

**Contingencies**

| Failure | Fallback (all honest) |
|---|---|
| Sensor dead | Swap in the pre-wired spare HC-SR04 (borrow 2). |
| Servo dead or arm jams | Spare servo. Otherwise run fault A or B only and say "gate test unavailable". Never claim verified. |
| No micro switch | `GATE COMMANDED` / `ARM NOT MEASURED` (V0). Say so out loud. |
| Arduino resets on servo move | Capacitor; otherwise a 4×AA pack for the servo with common ground. |
| Phone background breaks the plugin | Phone face down with **screen on** (auto-lock off). Same experience. |
| Venue Wi-Fi down | Laptop joins the phone hotspot. Runtime needs **no internet**: the card is precompiled and the engine is local. Backend URL is configurable in the plugin's phone settings. |
| G2 dead or disconnected | `evenhub-simulator` on the laptop, fed the same live frames. Labelled SIMULATOR. The hardware loop stays real. |
| Backend crash | `make demo` restarts in under 5 s. State rebuilds from live telemetry in about 2 s. |
| Everything else | The through-the-lens video of a real run (clearly a recording). |

---

## 4. Phone-face-down test (required, 45–60 s, zero phone screen)
Phone face down. The judge is wearing G2 with no coaching beyond the one sentence. Pass if the judge: (1) sees `SENSOR SILENT` / `SWITCH POWER OFF` within 2 s of power-on with fault A, (2) flips the switch and sees `CHECK ECHO WIRE` / `→ PIN 10`, (3) reseats the wire and powers on, (4) sees `SENSOR OK` / `WAVE TO TEST GATE`, (5) waves, sees the arm lift and `● GATE VERIFIED`, (6) sees the display go blank and stay blank across two more waves, and (7) single-presses to get `ALL TESTS PASSING`. Total time ≤ 60 s. Any glance at the phone fails the test.

**Judge-ready interaction:** "Make the gate open when you wave at it. The glasses will help. Double-press the temple to exit." That's all. Everything else is discovered: each cue names the physical label the judge can see.

---

## 5. Phase D — minimum viable implementation

### 5.1 Architecture (one laptop process plus one sketch plus one plugin)
```
[Gate: Uno + HC-SR04 + SG90 + end-stop + POWER switch]   firmware/barrier/barrier.ino (C)
   │ USB serial 115200, one JSON line / 100 ms (raw observations only)
[Laptop: python -m ghostbuild_core  :8787]               core/ghostbuild_core (D)
   serial.py   → reader with auto-reconnect (/dev/cu.usbmodem*), link up/down events
   tests.py    → deterministic test evaluators (windowed, debounced) driven by the card
   engine.py   → repair state machine (§5.2), the only thing that decides cues
   hud.py      → THE single HUD writer: emits a frame only on change, ≤ 1 new cue / 2 s
   server.py   → WS /ws?role=g2, GET /hud?after=seq (poll fallback), /state, /card,
                 /health, /sources/*, static /phone (A's web/), CORS on everything
   log         → logs/session-*.jsonl (observations, events, frames) → replay tests + quiet metric
[knowledge/cards/barrier.json]  Repair Card: authored now, AI-compiled at P1 (§5.6)
[Phone: Even app WebView → g2/ plugin (B)]  renders hud frames; sends presses/swipes
[Phone or any browser: /phone (A)]          wiring card, why and sources, evidence timeline
```
The firmware runs the gate itself (range < 15 cm → open for 2 s). The device works without GhostBuild. **GhostBuild observes; it never drives the device.**

### 5.2 Smallest state machine (core/ghostbuild_core/engine.py)
States: `NO_LINK · HEALTHY · FAULT(test, k, phase∈{powered, off}) · EXHAUSTED(test) · AWAIT_FUNC`.
- `HEALTHY` + test fails ≥ 1.5 s (power on) → `FAULT(t, k0, powered)`. k0 = the first check whose `when` predicate matches current evidence (else check 0). Emit F1.
- `FAULT(…, powered)` + power off → `FAULT(…, off)`. Emit F2 (check k).
- `FAULT(…, off)` + power on + test passes ≥ 1 s → if the card has a functional test, `AWAIT_FUNC` (K1); else `HEALTHY` (`SENSOR OK`, 3 s).
- `FAULT(…, off)` + power on + still failing 3 s → `FAULT(t, k+1, powered)` (F3). If k+1 is past the end → `EXHAUSTED` (U1).
- `EXHAUSTED` + test passes → as above.
- `AWAIT_FUNC` / `HEALTHY` + functional trigger: pass → `HEALTHY` (V1 the first time after a fault, otherwise **silent**); fail → `FAULT(func, k0, powered)` (F4).
- `AWAIT_FUNC` + 15 s without a trigger → blank, still pending.
- Any state, link lost: during `FAULT` keep the cue (USB-unplug-as-power-off counts as "off"); else after 5 s → `NO_LINK` (O1).
- Press → repeat the current cue, or P1. Tests are evaluated only while the rail is on.
- Fault priority follows card order (sensor before gate). Exactly one cue at a time.

### 5.3 Contracts (D, **lock Sat 17:00**; replaces 05 entirely)
```jsonc
// observation — firmware → core, one line / 100 ms
{"v":1,"dev":"barrier-01","seq":812,"ms":40213,"rail":1,"echo_us":2410,"echo_idle":0,"servo":"open","limit":1}
//  echo_us: 0 = pulseIn timeout · echo_idle: ECHO read with INPUT_PULLUP before trigger (1 = line not driven low)
//  servo: COMMANDED state · limit: MEASURED end-stop (1 = pressed)
// core wraps it: {"rx_at": <epoch ms>, "source": "serial" | "replay" | "simulated", "obs": {...}}

// hud — core → G2, only on change
{"type":"hud","seq":42,"kind":"clear|cue|ok|verified|status|uncertain|offline_device|why",
 "line1":"CHECK ECHO WIRE","line2":"→ PIN 10","ttl_ms":null,"cue_id":"sensor_responds/0",
 "source":"serial"}           // plugin honours ttl_ms locally as a fallback clear

// g2_input — G2 → core (double press is handled locally: exit dialog)
{"type":"g2_input","gesture":"press|swipe_down|swipe_up","seq_seen":42}

// state — GET /state for the phone (polled 1 Hz)
{"engine":"FAULT","test":"sensor_responds","check":0,"power":"off","link":"up","source":"serial",
 "hud":{...last frame...},"events":[{"at":...,"text":"echo pulses: none for 1.5 s","label":"MEASURED LIVE"}]}
```
**Repair Card** (`knowledge/cards/barrier.json`; the only device-specific artefact core reads):
```jsonc
{"card_id":"barrier-01","title":"Automatic gate (Uno, HC-SR04, SG90, end-stop)",
 "provenance":"AUTHORED DEMO METADATA" | "AI-EXTRACTED · HUMAN-REVIEWED",
 "sources":[{"id":"hcsr04","kind":"MANUFACTURER DOC","title":"HC-SR04 datasheet","url":"…","file":"knowledge/sources/hcsr04.pdf"},
            {"id":"wiring","kind":"AUTHORED PROJECT SPEC","title":"GhostBuild gate wiring","file":"hardware/WIRING.md"}],
 "tests":[{"id":"sensor_responds","signal":"echo_us","pass":{"gt":0},"fail_after_ms":1500,"pass_after_ms":1000,
           "fact":"SENSOR SILENT","ok":"SENSOR OK",
           "checks":[{"when":{"echo_idle":1},"action":["CHECK ECHO WIRE","→ PIN 10"],"why":"…",
                      "cites":[{"source":"hcsr04","loc":"p.2","quote":"<verbatim>"},{"source":"wiring","loc":"§2"}]},
                     {"when":{"echo_idle":0},"action":["CHECK TRIG WIRE","→ PIN 9"], …},
                     {"action":["CHECK SENSOR POWER","VCC + GND"], …}]}],
 "functional":{"id":"gate_opens","trigger":{"servo":"open"},"expect":{"limit":1},"within_ms":1500,
               "prompt":"WAVE TO TEST GATE","ok":"● GATE VERIFIED","fact":"GATE DIDN'T OPEN",
               "checks":[{"action":["CHECK SERVO WIRE","→ PIN 6"], …},{"action":["CHECK SERVO POWER","RED + BROWN"], …}]}}
```
`make contracts`: D updates `contracts/tools/lock_check.py` `REQUIRED_FILES/GLOBS` to `observation_*.json, hud_*.json, g2_input_*.json, state_*.json, card_barrier.json`, and adds models for each to `contracts/models.py`. B consumes the generated `contracts/ts/index.ts`.

### 5.4 Evidence and provenance model
Every engine event carries `{at, text, label, evidence:{signal, window, values}}`. The labels are fixed: **MEASURED LIVE** (from serial), **COMMANDED** (servo state the firmware reports issuing), **DETERMINISTIC** (engine inference such as "check order chosen because echo_idle=1"), **MANUFACTURER DOC** / **AUTHORED PROJECT SPEC** (card sources), **AI-EXTRACTED · HUMAN-REVIEWED** or **AUTHORED DEMO METADATA** (card provenance), **REPLAY** / **SIMULATED** (non-live sources, shown as a banner on the phone and as a `source` field on every frame; never used in judging). Pin numbers come from *our* wiring spec, labelled as such. Electrical facts come from the datasheet, with quotes.

### 5.5 LLM vs deterministic boundary
- **LLM (claude-opus-5-5, official `anthropic` SDK, structured outputs; build time only):** reads the datasheets and our wiring spec, then proposes the card: tests mapped to signals, check order, `why` text, ≤ 18/24-char cue text in silkscreen words, and citations.
- **Deterministic (all runtime):** test evaluation, debouncing, check selection, power-cycle advance, functional verification, every HUD frame and every clear. **No model output reaches G2 without passing through the reviewed card.** The network can be down at runtime.
- **Mechanical honesty gate on the AI card:** every `quote` must match the pymupdf-extracted source text verbatim (whitespace-normalised), or the card is rejected. Cue lengths and glyphs are validated, and every `signal` must exist in the observation contract. A human reviews the diff before commit.

### 5.6 Manual ingestion path
Docs come from real sources: the HC-SR04 datasheet PDF, the SG90 datasheet PDF, the Arduino Uno Rev3 pinout (docs.arduino.cc), and `hardware/WIRING.md`. Copy them into `knowledge/sources/` with their URLs. Flow: `make compile` → `knowledge/compile_card.py` → draft card → validator → human review → `knowledge/cards/barrier.json`. **P0 uses a hand-authored card labelled AUTHORED DEMO METADATA**, so the demo never depends on extraction working. The AI card replaces it only when it passes the validator (gate 23:00).

### 5.7 Source diagrams
No CAD, no image understanding. A draws one SVG of the real wiring (`web/assets/wiring.svg`) with an `id` per wire (`wire-echo`, `wire-trig`, …). `/phone` highlights the wire for the current `cue_id`. The datasheet's own diagram is linked from the source card by page number.

### 5.8 G2 implementation (B; verify each call with `everything-evenhub:sdk-reference` before coding)
- One page, **one text container** `cue` (`isEventCapture: 1`), roughly x16 y80 w544 h128 (adjust on hardware). Content is `line1 + "\n" + line2`; blank is `" "`.
- `createStartUpPageContainer` once, then `textContainerUpgrade` per frame. Brightness via `textColor` only if verified on 0.0.16 (P1 dimming).
- Events: `sysEvent` type 0 → send `press`. Type 3 → `shutDownPageContainer(1)`. `textEvent` 2/1 → `swipe_down`/`swipe_up`. Types 4/5/6/7 → re-render / persist / cleanup. Always use `?? 0`.
- WebSocket to `BACKEND_URL` (stored with `setLocalStorage`, editable on a phone-side settings screen) with auto-reconnect. If the WS fails in the WebView, poll `GET /hud?after=seq` every 300 ms. `setBackgroundState('hud', …)` holds the last frame and URL.
- `app.json`: `permissions:[{name:"network",desc:"Talk to the GhostBuild bench server",whitelist:[<backend URL(s)>]}]`. The backend must send CORS headers. **Verify at the 17:00 gate** whether a LAN `http://IP:8787` whitelist works in a packaged build; fallback is a Tailscale Funnel `https://<host>.ts.net`.

### 5.9 Tests
- **core (pytest, synthetic observation sequences):** a 1.0 s glitch makes no cue · a 1.5 s failure gives F1 · power off gives F2 with echo vs trig chosen by `echo_idle` · power-cycle still failing gives F3, then the next check, then U1 at the end · pass gives K1 · end-stop within 1.5 s gives V1, then a clear 3 s later · no end-stop gives F4 · **60 s healthy produces zero frames** (the quiet test) · identical cues never re-emitted · press gives status or repeat · **property: no `verified` frame unless `limit==1` within the window** · link loss during a fault keeps the cue.
- **card validator:** lengths, glyphs, signals, verbatim quotes.
- **replay golden (integration):** a recorded *real* session from C's hardware (`recordings/*.jsonl`, source=replay) → the expected HUD frame sequence.
- **g2 (vitest):** frame → container text, gesture → message, ttl fallback clear.
- **firmware:** `tools/serial_probe.py` validates live lines against the contract and prints the test verdicts.
- **Live acceptance:** §8.

### 5.10 Cut order if behind
1 swipe-for-why (W1) → 2 dimming → 3 AI card compile (keep the authored card, labelled) → 4 phone evidence timeline (keep wiring card) → 5 `echo_idle` discriminator (fixed check order) → 6 power-cycle advance (single check per fault). **Never cut:** fault cue → physical fix → `SENSOR OK` → functional end-stop → `VERIFIED` → blank, on real G2.

---

## 6. Phase E — repository execution

**What exists:** docs only, plus reusable bootstrap: `Makefile` (targets `core`, `g2-dev/sim/qr/pack`, `test`, `contracts`, `check-secrets`), `scripts/doctor.sh|health.sh|check_secrets.sh`, the `contracts/` lock tooling (Python lock check plus TS generator/ajv checker), and `pyproject.toml` (fastapi, uvicorn, websockets, pydantic; groups `knowledge` = pymupdf + anthropic). **No product code exists yet**, so nothing has to be thrown away except plans.

**Superseded:** docs 00–21 (historical), `integrations/*` (sponsors cut: delete), the perception dependency group (opencv, mediapipe: remove), Makefile targets `perception, compile-proof, twin, sentry-bridge, fetch-agent` (the iOS/spatial targets and `lock_check.py` REQUIRED lists are already updated), README and START_HERE content, and **CLAUDE.md rules about the rocket grid, spatial and sponsors**. Every teammate's agent obeys CLAUDE.md, so it was updated with this pivot (§12).

**Missing:** `pyserial` dependency, `core/ghostbuild_core/*`, `contracts/models.py` + examples, `g2/` plugin, `firmware/`, `hardware/WIRING.md`, `knowledge/`, `web/`.

**Merge and contract hazards:** `Makefile`, `pyproject.toml`/`uv.lock` (D only; one dependency change per commit; `uv lock`, never hand-merge), `contracts/` (D only; lock 17:00, consumer approval after), `CLAUDE.md`/`README.md` (A only). The pin numbers in `hardware/WIRING.md` (C) are the source of truth for the card, the SVG and the cues: **any pin change is announced in chat and updated in all three within 10 min.**

### Ownership

| | First task (start now) | Owns | Done when | Depends on | Next milestone |
|---|---|---|---|---|---|
| **A** | **A0** ~~update CLAUDE.md~~ (done); rewrite README quick start for the new lanes (15 min). **A1** download the real datasheets (HC-SR04, SG90, Uno pinout) with URLs into `knowledge/sources/` and hand them to D. **A2** `web/` phone page skeleton reading `/state` and `/card` (served at `/phone`) + `wiring.svg` drawn from C's WIRING.md | `web/**`, `README.md`, `CLAUDE.md`, this doc, Devpost, video, pitch | `/phone` shows the current cue with the right wire highlighted and the evidence list, from a live backend | D's `/state` shape (contract 17:00), C's pin list (17:30) | 21:00: full phone page; 01:00: run 5 first-time wearers; 02:45: footage |
| **B** | **B1** scaffold `g2/` from the official template; render a hard-coded `CHECK ECHO WIRE / → PIN 10` on **physical G2** via `make g2-qr`; glyph test `→ ● · '`. **B2 (the 17:00 transport gate)** WS frame from laptop to G2; press round-trip; phone face-down / screen-off test; packaged `.ehpk` with LAN whitelist + CORS test | `g2/**`, Beta packaging and QA, device custody | A frame typed on the laptop appears on G2 in < 500 ms with the phone face down; press arrives at backend; exit dialog works | D's stub server at `/ws?role=g2` (D gives a 20-line echo stub by 16:45) | 19:30: E2E; 00:00: **first Beta upload**; 06:45: Beta QA checklist signed |
| **C** | **C1** Hardware Lab now: borrow the kit (§9). **C2** gate working standalone (wave → arm lifts → end-stop presses). **C3** emit the observation JSON line at 10 Hz; validate the `echo_idle` discriminator on the bench (echo unplugged vs trig unplugged vs powered OK) and report a yes/no | `firmware/**`, `hardware/WIRING.md`, `tools/serial_probe.py`, `recordings/**`, the physical rig | `serial_probe.py` shows correct lines for healthy, fault A, B, C; WIRING.md committed with pins | none | 19:30: E2E; 21:00: first real recording for replay tests; then rig polish (labels, sturdy arm, spare pre-wired sensor) |
| **D** | **D1** stub WS server for B (16:45). **D2** contracts v2 + `lock_check` update → **lock 17:00**. **D3** `tests.py` + `engine.py` + `hud.py` with the §5.9 unit tests, driven by a dev-only simulated device (`--simulate`, source=simulated). **D4** `serial.py` against C's board | `core/**`, `contracts/**`, `knowledge/**` (card + compiler), `Makefile`, `pyproject.toml`, `uv.lock` | pytest green; `make core` with the real board drives B's plugin through F1→F2→K1→V1→blank | C's line format (contract), A's sources | 19:30 E2E; 21:00 functional and press; 23:00 AI card gate; 02:00 P0 freeze |

### Fastest path to the first end-to-end run (target **19:30**)
1. 16:45 D stub `/ws?role=g2` echoes typed frames. 17:00 B shows them on physical G2. **Transport proven.**
2. 17:00 contracts locked. D's engine runs on `--simulate` and produces frames into B's plugin (banner: SIMULATED).
3. 18:00 C's board streams real lines. D swaps `--simulate` for serial.
4. 18:30 hand-authored card loaded. Unplug echo → G2 shows F1 → switch → F2 → fix → K1.
5. 19:30 **M1:** the full sensor loop on real G2 with real hardware. Functional end-stop by 21:00.

### Timeline (PDT)
Sat 16:45 stub · 17:00 contract lock + transport gate · 18:00 hardware streaming · **19:30 M1 E2E** · 21:00 M2 functional + press + phone page + first recording · 23:00 AI card gate · **Sun 00:00 first Beta upload** · 01:00 five first-time wearers (fix every confusion they show) · **02:00 P0 freeze** · 02:45 through-the-lens footage secured · **04:00 feature freeze** · sleep B+C 03:00–06:00, A+D 05:00–08:00 · 06:45 Beta QA · 08:30 video cut · 10:30 Devpost complete · 11:00 final Beta · **12:00 deadline**.

---

## 7. Phase F — judge defense

- **Why not a mobile app?** The repair loop needs feedback within a second, in the same field of view as your hands. A phone is either in your way, late, or face down. Here the phone stayed face down the whole time and you fixed the gate.
- **Why not ChatGPT with a PDF?** ChatGPT can't see that your sensor stopped answering. It can't tell when your fix worked, and it talks until you stop it. GhostBuild is driven by measured device tests, and it stops talking the moment the evidence says you're done.
- **What is the role of AI?** It does the reading. It turns real datasheets and our wiring spec into a repair card: which test means what, which check comes first, and the exact words to show, each tied to a verbatim, machine-checked quote. At runtime a deterministic engine decides when to speak.
- **What if the AI is wrong?** It can only be wrong at build time, and it is caught there: quotes must match the source text exactly, cue text is validated, and a human reviews the card. At runtime the worst case is a `CHECK` that doesn't help. The engine then moves on, and finally says `NOT SURE WHY`. It never claims success without a measurement.
- **Does the device really know the repair worked?** For the sensor, yes: echo pulses are measured with a plausible range. For the gate, yes: an end-stop switch the arm physically presses must close within 1.5 s of the open command. If that switch weren't installed, we would say `GATE COMMANDED · ARM NOT MEASURED`.
- **What makes this native to G2?** It's the only display that can be both always available and usually empty. Our whole interface is four short cues and silence. Blank means healthy, and one press confirms it.
- **What is genuinely original?** A glasses app where the *device* raises the message and the *physical fix* dismisses it. That gives Even Hub a new moment: the test bench.
- **More than one device?** The engine has no device words in it (enforced by `make lint-generic`). A new device is a datasheet, a wiring spec, and our telemetry line format: compile a card, review it, done.
- **What did you build in 24 h?** The firmware and rig, a telemetry contract, a deterministic test and repair engine with unit, property and replay tests, an AI card compiler with a quote verifier, the G2 plugin (Beta build), and the phone evidence page.
- **Network down?** Nothing at runtime needs the internet. Laptop and phone can run on a hotspot. The AI step already happened. If G2 can't reach the laptop, it says `GHOSTBUILD OFFLINE`, never a stale OK.

---

## 8. First live acceptance test (run at M1 and before every judging block)
1. `make core` (real serial). `/health` shows `link: up, source: serial`.
2. Open GhostBuild on G2 with the phone face down. Expect `GHOSTBUILD ON` / `QUIET MEANS OK`, then blank in 3 s.
3. Wave 3 times; the gate works. **Expect no frames** (check that the session log has 0 hud frames in that window).
4. Power on with echo unplugged. Within 2 s: `SENSOR SILENT` / `SWITCH POWER OFF`.
5. Switch off: `CHECK ECHO WIRE` / `→ PIN 10` in < 1 s.
6. Reseat, switch on: `SENSOR OK` / `WAVE TO TEST GATE` in ≤ 2 s.
7. Wave: arm lifts, `● GATE VERIFIED`, blank 3 s later.
8. Press: `ALL TESTS PASSING`, blank in 3 s.
9. Repeat with fault B (expect `TRIG … PIN 9`) and fault C (expect `GATE DIDN'T OPEN`).
10. Kill the backend: G2 shows `GHOSTBUILD OFFLINE`. Restart: recovers without reopening the app.
11. Double press: system exit dialog; cancel keeps the app working.
**Pass = all 11 steps, no phone glance, no stale or contradictory frame.**

## 9. Hardware to borrow (C, now)
2× Arduino Uno (or Uno-compatible, 5 V) + USB cables · 2× HC-SR04 · 2× SG90 servo · 2× lever micro switch · 1–2 slide/toggle switches (if stocked) · breadboard + jumpers · green LED + 220 Ω · 10 kΩ resistors · 470 µF capacitor (ask) · 4×AA pack (backup servo power). Bring foam core, popsicle sticks, hot glue, masking tape and a marker for labels.

## 10. Official submission checklist (Even challenge)
- [ ] Even Hub app **`GhostBuild`** (≤ 20 chars, no "Even") packaged (`make g2-pack`) and **uploaded as Beta** (first by Sun 00:00, final by 11:00)
- [ ] Works on **physical G2** (the §8 test passed on the device, not the simulator)
- [ ] Devpost submitted with **Even Realities challenge selected** and the Even Hub app name included
- [ ] Demo video shows the G2 experience (through-the-lens footage of a real run; simulator clips labelled)
- [ ] README: install and run (backend, firmware flash, plugin install via Beta or QR), hardware list and wiring, required accounts (Even developer account; Anthropic API key **only** for `make compile`, never in `g2/`)
- [ ] Content scope: general low-voltage maker repair (not medical, financial or emergency)

## 11. Things we will NOT build
any iOS/Xcode/Swift app of our own (the phone side is only the Even app running our plugin, plus the `/phone` web page), 3D/CAD, RealityKit/ARKit/spatial, LEGO anything, webcam perception, MediaPipe, Create ML, digital twin, minimap/images on G2, voice/LISTEN/mic, always-on chatbot, runtime LLM on the cue path, phone camera checks, OCR of the breadboard, generic manual search/RAG, multi-device fleet UI, progress bars or step counters on G2, Sentry/Fetch/any sponsor integration, a second hardware demo before the first is rock-solid, user accounts.

## 12. CLAUDE.md
Applied Sat 2026-10-17: `CLAUDE.md` now carries the pivot rules (single HUD writer, no VERIFIED without the end-stop, CHECK-phrasing, device-agnostic core, contract lock 17:00, source labels, pins in `hardware/WIRING.md`). README and START_HERE point here.

---

## RECOMMENDED PIVOT
GhostBuild becomes a **closed-loop repair copilot**. The device under repair tests itself, G2 shows one documentation-grounded check only when a test fails, and measured evidence of the fix clears it.

**ONE-SENTENCE PITCH:** Your device tests itself; when it fails, G2 shows the one wire to check, and when your fix works, the hardware confirms it and the glasses go dark.
**HERO DEMO:** A broken automatic gate. The judge switches power off, sees `CHECK ECHO WIRE → PIN 10`, reseats the wire, waves, the arm presses its end-stop, `● GATE VERIFIED`, blank. Waving again produces silence. The phone stays face down.
**G2-NATIVE DIFFERENTIATOR:** The fix is the input: cues appear because of device evidence and change because of what your hands do. No "done" button exists.
**HARDWARE TO BORROW:** 2× Uno, 2× HC-SR04, 2× SG90, 2× lever micro switch, slide switch, breadboard, jumpers, LED, resistors, 470 µF cap, AA pack.
**SMALLEST WORKING VERTICAL SLICE:** Real serial telemetry → engine (one test, one check) → hud.py → G2 shows F1/F2/K1 → blank, on physical G2.
**FIRST TASK FOR A:** Rewrite the README quick start, fetch the real datasheets, scaffold `/phone`.
**FIRST TASK FOR B:** A hard-coded cue on physical G2 via QR, then the 17:00 transport gate (laptop → G2 frame, press back, phone face down, packaged whitelist + CORS).
**FIRST TASK FOR C:** Borrow the kit now; standalone gate plus the 10 Hz JSON line; bench-validate `echo_idle`.
**FIRST TASK FOR D:** Stub WS for B by 16:45; contracts v2 locked at 17:00; engine with the quiet tests on `--simulate`.
**TOP THREE RISKS:** (1) Even WebView networking in a packaged Beta (whitelist, CORS, mixed content, background WebView). Proven or replaced by 17:00. (2) Hardware flakiness (servo brownout resets, HC-SR04 noise, arm/end-stop mechanics). Mitigated with a capacitor, spares and a sturdy rig by 21:00. (3) First-time wearers misreading a cue. Mitigated with silkscreen-matched words and five strangers at 01:00.
**THINGS WE WILL NOT BUILD:** see §11.

**Does it meet the Even "Quiet Tech" bar? Yes, with one condition.** The healthy state is literally an empty lens. Each cue is a single action that exists only while its fault is real and disappears because of a physical event. The intelligence (reading docs, choosing checks, verifying) is all off-lens. The condition is that this only holds if B proves at 17:00 that the plugin receives frames with the phone face down. If it doesn't, we use the screen-on face-down fallback and say so.
