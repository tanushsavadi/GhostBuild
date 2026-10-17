# 16 — Decisions & Assumptions

> **Final reconciliation (2026-10-16).** D-01–D-27 are kept with superseded rows marked; D-28–D-50 record the spatial (18 v2/v3) and sponsor/reconciliation (19 + final amendments) decisions.

## Decisions
| ID | Decision | Alternatives rejected | Reason |
|---|---|---|---|
| D-01 | Fixed overhead camera, not handheld phone scanning | Handheld phone; plugin camera | G2 has no camera; SDK camera is single-shot [V]; hands are needed for the repair; fixed pose makes CV tractable |
| D-02 | Fiducial grid + LAB colour + dot markers + part fitting | 3D recon; LiDAR; VLM-primary; YOLO | Latency, determinism, abstention; no training; 180° flips need a marker anyway |
| D-03 | No LiDAR | ARKit depth | ~256×192 noisy depth; 3.2 mm plate at noise floor; needs native app |
| D-04 | Deterministic priority replanner + dependency check, recomputed every commit | A*, PDDL, constraint search, FSM | Tiny uniform-cost action space; BFS test verifies optimality on demo states |
| D-05 | Laptop is the only server; plugin and twin are stateless renderers | Logic in plugin; cloud backend | Single source of truth; survives plugin restarts and lock test |
| D-06 | Own network (travel router / iPhone hotspot) + Tailscale Funnel rung; all origins whitelisted from build #1 | Venue Wi-Fi; LAN-only; cloud relay only | AP isolation; Beta LAN behaviour unverified; whitelist changes need a repack [V] |
| D-07 | 2D supervisor view on the laptop; no rich phone UI; 3D is stretch *(amended by D-29: a second, stand-mounted phone is an instrument)* | Phone 3D twin in plugin; separate phone web app | "Made for G2" / Quiet by Design; red-team: 3D costs 4–6 h and upstages the glasses |
| D-08 | VLM is async, open-world only, never decides state *(final: no VLM on the live path at all; the label is cut)* | VLM as perception | Published LEGO benchmarks show weak VLM state accuracy; latency 1–5 s |
| D-09 | LEGO System bricks, 10–12 parts, LAB-distant colours, one layer-2 cap | Technic; Duplo; tube rack | Recognisability + a real dependency for planning; Duplo is Plan C |
| D-10 | Framing: "the work guide that checks your work"; LEGO as testbed | "LEGO repair app"; medical trays | Product & Impact; Even disallows medical apps [V] |
| D-11 | ~~Targets: Even 1st, Overall (Beyond the Digital), StepFun conditional~~ **SUPERSEDED by D-41–D-46** (final: Even primary, Sentry secondary, Fetch conditional secondary, Beyond the Digital, Commit opt-in, Workday framing-only if free; StepFun dropped) | Paper, others | 19 §1 |
| D-12 | iPhone as the Even phone | Android | WKWebView keeps running when locked; Android may suspend [V] |
| D-13 | Text-first HUD; minimap only on step change | Image-heavy HUD | BLE bandwidth; image pacing [V] |
| D-14 | `●` instead of `✓` until a hardware glyph test passes | — | `✓` not confirmed in the firmware font; unsupported glyphs are dropped [V community glyph table] |

### Ambition-pass decisions (2026-10-16)
| ID | Decision | Supersedes | Alternatives rejected | Reason |
|---|---|---|---|---|
| D-15 | **UPGRADE (trimmed):** P0 + four gated P1 layers | first-pass verdict | Keep constrained (generic AI story); full upgrade (≈120 h demand vs ≈80 h supply) | 17 §1; red team P(win) 30 → 41 |
| D-16 | Task graph + target **derived from CAD (LDraw)**; step evidence **extracted from the PDF by Claude Opus 5.5**; golden JSON as test oracle + fallback | D-04 inputs (hand-authored target) | LLM-only graph (Proc2PDDL ~40%, AssemState 62.8% tree F1 [V]) | Verifiable structure + real AI reading of the manual |
| D-17 | **No vector DB**; whole manual in context with caching; citations via `search_result` blocks | — | ColPali/embeddings | 20–60 pp fits; diagram pages aren't natively citable [V] |
| D-18 | **Deterministic answer engine**; LLM only for intent/slots (and P2 free-form) | D-08 scope | LLM-generated answers | No hallucinated instructions; LLM-Modulo pattern |
| D-19 | **Voice = hold-to-ask** (long press) → Deepgram Flux `ForceEndTurn` → Haiku 5.5; **menu built first** *(final: voice is P2 opportunistic per D-33; the menu is the P1 question path)* | voice cut (first pass) | Continuous listening, wake word, VAD turn-ending, local STT | Exact turn boundaries; noise; Quiet Tech |
| D-20 | ~~**Live CAD twin is P1** (three.js + LDrawLoader) on Mac 2~~ **SUPERSEDED by D-34** (phone RealityKit twin; W4-lite only if spatial dies early) | D-07 (2D only) | 3D reconstruction | Honest "known CAD at inferred poses"; visual wow |
| D-21 | Learned perception limited to **hand landmarks** (P0 hardening) *(final: VLM foreign-object labels cut)* | D-02 (partly) | YOLOE, Brickognize, SAM (measured/assessed; cut) | Closed known part set; risk on the critical-path person |
| D-22 | **LiDAR cut** (future work) | D-03 reaffirmed with evidence | ARKit sensor app, PromptDA | ~1 cm noise vs 9.6 mm step; P≈0.15 for ~8 h |
| D-23 | **Generic core** (components/predicates/verifiers) + LEGO adapter; CI lint for LEGO terms in core. *Final clarification:* the data model and planner skeleton are generic; action semantics (covering, sites, rotation equivalence, blockers, phrasing) are adapter-supplied. Don't claim more. | contracts v1 | LEGO-specific schema | Generality claim must be true in code |
| D-24 | ~~**Generality proof = iFixit 158506** through the same compiler (P1-late; video if gate fails)~~ **SUPERSEDED by D-40** (offline, optional, "compiled, not executed") | — | Second physical rig | Best proof per hour; matches product vision |
| D-25 | **Build redesign:** cap bridges red + green; `premature` diff kind; demo centrepiece = dependency catch | demo v1 | — | Red team: one unforgettable, judge-initiated moment |
| D-26 | Team rebalance (13), P0 freeze Sun 02:00, one HUD arbiter, flags for every P1 | team v1 | B as merger | Isolation; ≈20 h per person |
| D-27 | Hero-tag 6-DoF demoted to P2, physically removable *(final: cut; superseded by the spatial lane)* | — | Learned 6-DoF (CUDA) | P(works) 0.4; P0 interference risk |

### Spatial decisions (18 v2 + 18 v3; final reconciliation 2026-10-16)
| ID | Decision | Supersedes | Reason |
|---|---|---|---|
| D-28 | Spatial prototype per 18 v3 (which amends 18 v2); it leads only under the 18 v3 §9 lead rule | — | Frontier wow without betting P0 |
| D-29 | A second, stand-mounted iPhone is an instrument, not the user's UI | amends D-07 | G2 stays the user's surface |
| D-30 | Apple-native on-device pose (ARKit + RealityKit + Create ML); no cloud GPU, no EC2 | — | No CUDA; latency; cost |
| D-31 | One markerless hero (the motor); image cards on deck and bar; battery/chassis untracked; base by a fixed fiducial locked into world tracking | V1's five trained modules | Training time; slot budget |
| D-32 | Blockers, removal axes, `occludes`, `requires` are `authored_demo_metadata`; CAD supplies poses, hierarchy and bboxes | V1 `cad_derived` relations | An LDraw parser can't derive "bar locks motor" |
| D-33 | Voice demoted to opportunistic P2, never scheduled, to fund the spatial loop | D-19 (P1 voice) | Without it the spatial loop has no owner |
| D-34 | The Mac three.js twin (W4) is replaced; W4-lite only if spatial is killed at S2/S4 | D-20 | If nobody builds W4, the fallback wouldn't exist |
| D-35 | **One contract lock at Sat 12:45** covering every core + spatial schema and fixture; after it, shared-schema changes need D + every consumer owner; none after 00:45 | the 12:30 lock and the 15:00 SP5 slot | A lock that later changes is not a lock |
| D-36 | Task-driven spatial gates: state-classification correctness with **0 unsafe errors**; thresholds derived from measured σ and bias; mm figures are diagnostics | V2 mm gates | Accuracy only matters through the distinctions the demo needs |
| D-37 | Goal "Fix the motor assembly" (access, inspect, correct); claims limited to measured installation state; no functional-health claims | "Replace motor", "isn't broken" | Nothing measures motor function |
| D-38 | Automatic clock valves (18 v3 §8): not green at the clock = red; killed work is never reopened | standups "by feel" | Objective kill decisions |
| D-39 | G2 menu item 5 = `WHAT NEXT?` (REPEAT becomes voice-only) | item 5 `REPEAT` | The judge can ask WHY / WHAT NEXT / CAN I / WHAT'S DONE without voice |
| D-40 | Generality proof is offline only: one external guide through the same compiler, shown in Devpost/README/one frame as "compiled, not executed"; cut if it needs code | D-24 | No live iFixit; zero demo risk |

### Sponsor and reconciliation decisions (19 + final amendments)
| ID | Decision | Supersedes | Reason |
|---|---|---|---|
| D-41 | **Even Realities is the primary sponsor**; the judged interaction is the next verified action + silence when correct; add the quiet metric and the three judge answers; no new G2 UI | — | The brief names our category |
| D-42 | **Sentry secondary** via an isolated read-only log bridge (Tracing + Logs; Issues/agent spans bonus). Enter only with ≥ 1 real FINDING and ≥ 1 real DECISION in `docs/sentry_findings.md` by Sun 08:30 | 01 "not pursued" | Guaranteed-interview prize; real observability need |
| D-43 | **Fetch.ai conditional secondary**: ASI:One supervisor agent in `integrations/fetch_agent/` on B's laptop; ACP, approval before mutation, disarmed by default; **`GB_CORE_URL` required, no localhost default, fail fast** | D-11 "Fetch: no" | Supervision is a real role GhostBuild lacks |
| D-44 | **04:00 = product feature freeze**, with one pre-approved isolated sponsor-client exception for `integrations/fetch_agent/` under nine conditions; any forbidden change → Fetch dies | 19's informal "integrations exemption" | Fetch lands after the freeze without touching the product |
| D-45 | **Two video exports from one master edit:** GENERAL 2:50–2:58, FETCH 3:10–3:30 (+20–30 s ASI:One beat) | one 3:00 cut for both | Don't depend on a single duration satisfying two rules |
| D-46 | StepFun dropped; Cognition network-only (checkbox not selected); Devin is a coding-capacity tool limited to `integrations/*`; Hardware Lab = borrow a spare Logitech webcam only | 00 §3, 19 §5.4 J | No sponsor soup; no new owners or failure modes |
| D-47 | A G2 tap is a recheck request: re-plan on the latest committed world; never a forced commit | 08 §6 "forces a fresh commit" | The tap must not bypass temporal stability |
| D-48 | `hud.mode` on the wire ∈ {instruct, hold, verified, uncertain, idle}; `offline` and `detail` are plugin-local; `guided` removed | 05/08 mismatch | One enum, one meaning |
| D-49 | `Pose.T` = `T_frame_component` with the origin at the footprint's bottom centre; grid formula uses the post-rotation footprint and `Rz(−rot)` | 05 §1 ambiguous formula | The old text mixed anchor corner and centre and had the rotation sign wrong |
| D-50 | Bundle documents carry `origin ∈ {team_authored, external}`; citations always name it | — | "Manual evidence" must say whose manual |

## Assumptions (to validate; owner, when)
| ID | Assumption | Validate by | Owner |
|---|---|---|---|
| A-01 | A Beta build can open `ws://` to a LAN IP, or `wss://` to a Funnel host | E2, Sat 4–5:30 PM | B |
| A-02 | The iPhone hotspot host can reach the laptop client (172.20.10.x) | E2 | B/D |
| A-03 | Venue lighting + own panel allows ≥ 99% cell accuracy | E1, Sat 4–5:30 PM | C |
| A-04 | ~~`step-5-preview` accepts images…~~ retired (StepFun dropped) | — | — |
| A-05 | We get a G2 loan | Sat 12:30 PM | B |
| A-06 | The minimap is legible on glass | E7, Sat 2:30 PM | B |
| A-07 | Judges accept LEGO-as-testbed framing | Rehearse with outsiders Sun 9 AM | A |
| A-08 | No limit on the number of company challenges per project | Ask organizers | A |
| A-09 | Studio exports LDraw with `0 STEP` and an instruction PDF; part mapping is clean | Sat 13:30 | A/D |
| A-10 | Opus extraction ≥ 80% part-multiset match on our PDF | K1 Sat 17:00 | D |
| A-11 | The G2 mic gives intelligible PCM during HUD updates in the hall (only if P2 voice starts) | G1 | B |
| A-12 | Deepgram Flux params work as documented (only if P2 voice starts) | G5 | C |
| A-13 | MediaPipe hands wheel works on our Python/arm64; else the Swift helper | V2 Sat 16:00 | C |
| A-14 | Authoring the LEGO model/PDF before 12:00 is allowed | Ask at check-in | D |
| A-15 | A spatial iPhone on iOS 27 and an Xcode 27 Mac are available | S0 Fri | A |
| A-16 | Motor training finishes ≤ 22:45 on our trainer Mac (standard mode, Upright) | S1 13:45 ETA | A |
| A-17 | Image + object tracking coexist at ≥ 30 fps | S2 / S5 | A |
| A-18 | Base drift keeps seated parts CORRECT for 10 minutes without a re-lock | S7 | A + D |
| A-19 | Anchors persist across a same-type `run(options: [])` [V; confirm at S2] | S2 | A |
| A-20 | Fetch accepts "supervisor workflow complete in ASI:One; technician on G2" as satisfying "no custom frontend" | 11:30 table / Discord; red by F1 | A |
| A-21 | Sentry SDK (≥ 2.35.0) supports explicit span start/end timestamps for log-derived spans [verify] | Devin PR | Devin / B |
| A-22 | An ASI:One agent may send unprompted messages; any reply timeout is workable [verify] | F0 / 11:30 | A |

## Unresolved facts needing organizer/sponsor confirmation
0. (Ambition pass) Is designing the physical testbed models in BrickLink Studio before hacking starts allowed?
1. Whether a packaged **Beta** build may use `http://`/`ws://` LAN origins (Even). Ask at the 3 PM workshop.
2. Which Even rubric is authoritative (4 criteria vs 5 incl. "Quiet by Design").
3. Number of G2 loaners vs applicants.
4. Overall prize; whether exactly one organizer track must be chosen.
5. Can a project select multiple company challenges (A-08)? Does Fetch accept the supervisor interpretation (A-20)? Any separate Sentry form?
6. The Devpost rules page shows a stale "8am Sunday April 26" deadline; the schedule says Sun Oct 18 12:00 PM.
7. Whether the Even app needs internet to launch an already-installed Beta plugin.
8. Whether `getUserMedia` works inside the plugin WebView (not needed by our design; informational).

## Key sources
- Even architecture / display / device APIs / networking / background / packaging / beta: https://hub.evenrealities.com/docs/ (get-started/architecture, build/display, build/device-apis, build/networking, build/background-lifecycle, ship/packaging, test/beta-testing)
- Even LA Hacks prompt + starter pack: https://evenrealities-lahacks.vercel.app/ · /starterpack
- Even Claude Code plugin: https://github.com/even-realities/everything-evenhub · templates: https://github.com/even-realities/evenhub-templates · SDK: https://www.npmjs.com/package/@evenrealities/even_hub_sdk
- Community G2 notes (glyphs, performance): https://github.com/nickustinov/even-g2-notes
- LA Hacks AI Hackathon: https://live.lahacks.com (schedule, tracks) · https://la-ai-hackathon-2026.devpost.com
- Prior art: Khuong et al. IEEE VR 2014 https://www.cs.ucf.edu/~jjl/pubs/vr2014.pdf · Amazon US10366521B1 https://patents.google.com/patent/US10366521B1/en · Caltech SIGGRAPH 2025 https://authors.library.caltech.edu/records/242tm-f6y12 · Augmented Assembly https://arxiv.org/abs/2601.11535 · Vuforia Step Check https://support.ptc.com/help/vuforia/editor/en/vuforia_editor/step_check.html · LEGO Co-builder https://arxiv.org/abs/2507.05515 · TinkerFlow (HtN 2024 gallery)
- Past winners: https://la-hacks-2026.devpost.com/project-gallery · https://la-hacks-2025.devpost.com/project-gallery

- Ambition-pass sources:
  - WorkBenchMark https://arxiv.org/abs/2606.19358
  - RealityBench https://arxiv.org/html/2610.14397
  - LLM-Modulo https://arxiv.org/abs/2402.01817
  - Manual2Skill https://arxiv.org/html/2502.10090v2
  - AssemState https://arxiv.org/abs/2610.08446
  - Claude citations https://platform.claude.com/docs/en/build-with-claude/citations
  - Claude search results https://platform.claude.com/docs/en/build-with-claude/search-results
  - Deepgram Flux https://developers.deepgram.com/docs/flux/force-end-turn
  - LDraw spec https://www.ldraw.org/article/218.html
  - three.js LDrawLoader https://github.com/mrdoob/three.js/blob/dev/examples/jsm/loaders/LDrawLoader.js
  - iFixit https://www.ifixit.com/api/2.0/guides/158506
  - YOLOE https://github.com/THU-MIG/yoloe
  - SAM 3 Mac issue https://github.com/facebookresearch/sam3/issues/164
  - FoundationPose https://github.com/NVlabs/FoundationPose
  - PromptDA https://github.com/DepthAnything/PromptDA
