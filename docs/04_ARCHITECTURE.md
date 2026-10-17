# 04 — Architecture (final reconciliation 2026-10-16)

**Owner:** Person D (contracts and architecture). Any change needs a line in 16_DECISIONS_AND_ASSUMPTIONS.md.

> **Final reconciliation.** Adds the spatial lane (18 v3: phone RealityKit app, `adapters/spatial_pose`, base-lock lifecycle) and the isolated sponsor processes (19: `integrations/sentry_bridge`, `integrations/fetch_agent`). Removes the Mac three.js twin as a P1 surface (W4-lite only if spatial dies early), the VLM foreign-object label (cut), live iFixit (offline proof only) and voice from the critical path (P2). The honesty map now uses the final provenance classes.

## 1. Topology
```
 BUILD TIME (cached; committed bundles; shown with provenance)
 Studio model ─► rocket.ldr ─► knowledge/ LDraw parser ─► task graph + target      [DETERMINISTIC, CAD]
           └──► instructions.pdf ─► PyMuPDF ─► Claude Opus 5.5 ─► evidence          [AI-EXTRACTED, gate K1]
 rover CAD (Studio→Blender) ─► component_frames.json + USDZ ─► rover bundle + app  [CAD / KNOWN MODEL]
 rover service sheet (team-authored PDF) ─► same extraction path ─► evidence        [MANUAL EVIDENCE, team-authored]
 rover relations / occludes / requires ─► written by us, checked on the rig         [AUTHORED DEMO METADATA]
 (optional) external repair guide PDF ─► same path, offline ─► Devpost only          ["compiled, not executed"]
                    └─► validator + human review ─► knowledge/<task>/bundle.json (git)

 ┌──────────── MAC 1 (perception + brain) — P0 ───────────────────────────────────────┐
 │ USB webcam (overhead) ─► perception/ (Python)                                        │
 │   P0 grid: ArUco→homography→LAB cells→part fit→abstain→vote   [DETERMINISTIC CV]     │
 │   hands: Apple Vision helper → freeze cells under hands         [ML, veto only]      │
 │        │ observation (ws role=vision, source=cv)                                     │
 │ adapters/spatial_pose (separate process, :8790, --spatial only) [DETERMINISTIC]      │
 │        │ observation (ws role=vision, source=spatial)                                │
 │ core/ (Python, FastAPI :8787)                                                        │
 │   world model → diff (premature…) → planner (+teardown, inspect) → HUD arbiter [DET] │
 │   answer engine (deterministic, cited)                                               │
 │   session log (jsonl) · REST control · serves /twin (2D supervisor)                  │
 │ integrations/sentry_bridge (separate process, nice 19, read-only log tail) [OPTIONAL]│
 └───────┬──────────────────────────────┬───────────────────────────────┬─────────────┘
         │ hud ↓  g2_input/ack ↑         │ twin v2 (ws role=twin)          │ LAN REST/WS
         ▼ (LAN ws or Funnel wss)        ▼                                 ▼
  PHONE 1: Even app WebView — g2/      SPATIAL PHONE (iPhone, iOS 27):   B's LAPTOP:
        │ BLE (Even SDK)               spatial/ RealityKit app            integrations/fetch_agent
        ▼                              (pose_observation → :8790)         [OPTIONAL] ⇄ Agentverse ⇄ ASI:One
  EVEN G2: display + touch + mic       USB mirror → MAC 2 (QuickTime)
  (no camera / speaker)                MAC 2: mirror + 2D supervisor + recording
```

**Verified constraints behind this shape:**
- Plugin logic runs only in the phone WebView; the glasses render containers and emit input [V].
- No camera on G2; the SDK camera is single-shot only [V].
- The G2 mic is available as 16 kHz PCM after the startup page [V] (used only if P2 voice ships).
- No audio output [V].
- BLE is ~10–30 KB/s; bridge calls must be serial [V].
- A same-type `ARWorldTrackingConfiguration` re-run with `options: []` keeps added anchors and resumes tracking [V, 18 v3 §5].

## 2. Decisions
| Question | Decision | Why |
|---|---|---|
| Rich UI on the user's phone? | **No.** The plugin's phone page is a HUD mirror + connection status. A **second, stand-mounted iPhone** runs the spatial app as an instrument, not the user's UI. | Quiet by Design; the user's phone stays in the pocket |
| Spatial companion | **Phone RealityKit CAD twin** of the rover (W8, P1, gated), mirrored to Mac 2 for the second judge; 2D supervisor (M10) as the always-available panel | Exact CAD at tracked poses is honest and visible; G2 stays the user's surface |
| Where does AI run? | Hosted Claude for build-time extraction. Local ML: Apple Vision hand pose (veto only) and ARKit image/object tracking (pose source). | No CUDA; keys stay on the laptop |
| Who owns physical state? | **Core**, from committed observations only: the P0 grid path for the rocket; the spatial adapter's state machine (18 v3 §3) for the rover. Learned signals can only veto (≤ 1.5 s). No AI model commits state. | Abstain over guess |
| Where do targets come from? | **CAD** → task graph + target; **manual** → evidence via Claude (or authored if K1 fired); rover blockers/axes/requires are **authored demo metadata**; golden JSON as CI check + fallback | Not hand-scripted where CAD can supply it; labelled where it can't |
| How does G2 get updates? | Core **HUD arbiter** pushes `hud` on change (≤ 4 Hz). Plugin keeps a serial, latest-wins bridge queue. | Single writer avoids races; BLE limits |
| Questions | One **answer engine**: G2 contextual menu (P1) → phone text (testing). Voice P2, only if it opportunistically ships. | Deterministic answers, so no hallucinated instructions |
| Camera | USB webcam on a clamp arm, ~40 cm overhead. Backups: a borrowed Hardware Lab Logitech webcam, then iPhone Continuity Camera. | No network dependency |
| Offline? | The core loop, menu answers, compiled bundles, spatial phone ↔ core and the 2D supervisor work on our own LAN with no internet. Internet (hotspot cellular) is needed **only** for the Funnel rung, Sentry, and Fetch/ASI:One. | Venue-proof demo path |
| LiDAR | **Cut** for state (17 §6). LiDAR scene occlusion of CAD by hands is cosmetic spatial stretch only. | ~1 cm noise vs 9.6 mm step |

## 3. Processes (`make demo` launches Mac 1)
| Process | Tech | Port | Owner | Runs alone with |
|---|---|---|---|---|
| `core` | Python 3.11, FastAPI, uvicorn, pydantic v2, `websockets` | 8787 | D | `--mock-vision scenarios/demo.yaml --bundle knowledge/fixtures/rocket_bundle.json` |
| `perception` | Python 3.11, opencv-contrib-python, numpy + Swift `hands_helper` | — | C | `--video recordings/*.mp4 --print` |
| `adapters/spatial_pose` | Python 3.11 | 8790 (`/pose`) | C (after G2) | synthetic `pose_observation` sequences; A's recordings |
| `knowledge` (CLI, build time) | Python, PyMuPDF, `anthropic` | — | D | fixtures |
| 2D supervisor (`/twin?mode=2d`) | static page served by core | 8787 | B | `?replay=` |
| `g2` | Vite + TS + `@evenrealities/even_hub_sdk@0.0.16` | 5173 dev | B | `?mock=1` + simulator |
| `spatial/` | Swift, SwiftUI + RealityKit `ARView`, iOS 27 | — | A | fixture `twin_v2.json`; Swift transform tests |
| `integrations/sentry_bridge` (optional) | Python 3.11, `sentry_sdk` | — | Devin → B | `--dry-run` on a fixture log |
| `integrations/fetch_agent` (optional) | Python 3.11, `uagents` | — (mailbox) | Devin → B | `core --mock-vision` + explicit `GB_CORE_URL` |
| W4-lite twin (only if spatial dies early) | Vite + TS + three.js LDrawLoader | served at `/twin` | A | `?replay=` |
| voice (P2, only if it ships) | Deepgram Flux WS + Haiku, inside core | — | C | `--wav tests/audio/*.wav` |

## 4. Network plan (still the #1 technical risk for G2)
- **Own network:** a travel router (laptop on a static lease, e.g. `192.168.8.10`) or the Even iPhone's hotspot (laptop typically `172.20.10.2`; record the real IP). Never the venue Wi-Fi.
- **Plugin connection ladder:** all origins are whitelisted from build #1, because a whitelist change means repack + re-upload.
  1. `ws://<laptop-lan-ip>:8787` — fastest, offline. Unverified in Beta builds (mixed-content risk).
  2. `wss://<laptop>.<tailnet>.ts.net` via Tailscale Funnel — stable HTTPS name with a valid certificate; needs internet.
- **Whitelist entries:**
```json
{ "name": "network", "desc": "Connects to the GhostBuild workstation that watches your build.",
  "whitelist": ["http://172.20.10.2:8787", "ws://172.20.10.2:8787",
                "http://192.168.8.10:8787", "ws://192.168.8.10:8787",
                "https://<laptop>.<tailnet>.ts.net", "wss://<laptop>.<tailnet>.ts.net"] }
```
- `evenhub pack` rejects an empty whitelist [V]. **No sponsor or spatial traffic touches the plugin, so no whitelist change is ever needed for them.**
- Mac 2, the spatial phone (`ws://<mac1>:8790/pose` and `ws role=twin`) and B's laptop (Fetch agent, `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`, set explicitly) reach Mac 1 over the same private LAN.

## 5. State ownership
- Core is the single source of truth. Plugin, spatial phone and 2D supervisor are renderers; core sends a snapshot on (re)connect. The spatial phone renders tracked poses locally at frame rate, but **commits** (green ring, G2) come only from core.
- The plugin persists only `last_hud` (`bridge.setLocalStorage`, ≤ every 2 s).
- The KnowledgeBundle is immutable at runtime; switching task loads another bundle.
- Every message is appended to `logs/session-<ts>.jsonl`. The Sentry bridge only reads this file.

## 6. Failure containment
| Component down | Behaviour |
|---|---|
| perception | `status: no_board`; HUD `CAMERA PAUSED`; supervisor red banner. Swap to the spare webcam. |
| hands helper | Motion-energy occlusion gate (P0 original) |
| compiler / K1 | Golden target + `authored` evidence (labelled) |
| 2D supervisor | Core-served text page; the G2 loop is unaffected |
| core | Plugin shows last HUD dimmed + `OFFLINE · TAP RETRY`; ladder reconnect |
| G2 BLE | WS stays up; re-render on reconnect |
| spatial phone down / overheats | Close the spatial app; the rocket leads; G2 loop unaffected |
| spatial adapter down | No `source: spatial` observations → rover plan `no_board`; rocket unaffected |
| **ARKit session interrupted / relocalizing** | `base.state = unset` → every component NO_COMMIT, plan `no_board`; captain presses **Re-lock** between runs (18 v3 §5) |
| Sentry bridge / internet | Events drop silently; demo unaffected; offline `make eval-latency` remains the measurement of record |
| Fetch agent / internet / Agentverse | Supervisor sees "workcell offline"; kill the process; GhostBuild unchanged |
| voice (P2, if shipped) | `MIC OFF · USE MENU`; menu answers still work |

## 7. Honesty map (every visible element; final provenance classes)
| Class | Meaning | Examples |
|---|---|---|
| **TRACKED** | A live sensor pose from ARKit (image card or reference object) or the P0 grid | `DECK TRACKED·IMG`, `MOTOR TRACKED·OBJ`, per-cell classes |
| **MEASURED LIVE** | A number computed now from TRACKED vs TARGET | the `90°` readout; latency; fps |
| **CAD / KNOWN MODEL** | Geometry rendered from the model we built the object from; never a scan | rover CAD on the phone; rocket parts in W4-lite |
| **TARGET** | The pose the CAD says a part should have | cyan ghost |
| **DETERMINISTIC** | Computed by rules over committed state: diff, planner, teardown path, state machine, commits | `TURN MOTOR 90° →`, `X DECK TOO EARLY`, green ring, `● VERIFIED` |
| **AI-EXTRACTED** | Produced by Claude at build time and validated | step evidence when K1 passed (`AI-EXTRACTED · VALIDATED` chip) |
| **AUTHORED DEMO METADATA** | Written by the team, checked on the rig | rover `blocked_by`, `removal_axis`, `occludes`, `requires` (chip `AUTHORED RELATIONS`) |
| **MANUAL EVIDENCE** | Text from a document, always naming the document's origin | `TEAM-AUTHORED SERVICE SHEET`, `ROCKET INSTRUCTIONS (OURS)`, or an external guide (offline proof only) |
| **LAST SEEN** | A state verified while visible, now hidden | `MOTOR · VERIFIED 12:41 · NOW HIDDEN` |
| **MANUAL OVERRIDE** | Operator input, never model output; bannered; banned from lead runs and eval numbers | HUD `M`, red banner |

Rules: never say "AI reasoned physically" (the deterministic planner did it); never say "CAD-derived" for authored relations; always say whose manual; never say "functional verification" (only installation state is verified).

## 8. Isolation rules (red team; enforced in code review)
1. **P0 freeze at Sun 02:00** (git tag). After that, only fixes in P0 paths, approved by D.
2. Every P1 feature sits behind a flag (`--hands`, `--spatial`, twin `?mode`, `--voice` if P2 ships) and can be turned off at the table in < 10 s.
3. **One HUD writer:** core's arbiter. Priority alert > verified > answer > instruct.
4. **The compiler is never called during a demo run.** `/control/ingest` is an offline/build-time convenience wrapper around `knowledge.compile` (same as `make compile`); its output is a committed bundle. CI diffs bundles against the golden target.
5. Answers are pure functions over an immutable snapshot and never mutate state.
6. Learned vetoes expire after ≤ 1.5 s and have a kill switch. P0 output must be byte-identical with `--no-learned` on recorded fixtures.
7. Perception and the 2D supervisor/mirror run on different Macs. The spatial app is never on Mac 1; Create ML training never runs on Mac 1 or A's Mac.
8. The plugin boots into the build task; only `/control/task` switches tasks.
9. **Spatial isolation (18 v2 §11.3):** `adapters/spatial_pose/` is a separate process; core changes for spatial are additive and flag-guarded; CI requires byte-identical rocket HUD snapshots with `--spatial` on and off; **spatial core merge cutoff Sun 00:45**; nothing in `perception/` or the rocket path imports `spatial/` or `adapters/spatial_pose`.
10. **Base-lock rule (18 v3 §5):** after the first run, `ARSession.run` is called only with `options: []`; a code-review grep rejects `.resetTracking` / `.removeExistingAnchors` outside the first-run path; the base anchor's transform is read from `frame.anchors` every frame, never cached.
11. **Sponsor isolation (19 §8):** sponsor code lives only in `integrations/`; it is never imported by, or run inside, P0 processes; its only writes into GhostBuild are `/control/task`, `/control/reset` and `/control/goal`, ARMED-only and approval-gated; it never calls `/control/ask`; killing any sponsor process leaves GhostBuild byte-for-byte unchanged.
12. **Contract rule (18 v3 §4):** one lock at Sat 12:45; after it, a shared schema changes only with D plus every consuming owner; after 00:45, no schema change at all.
