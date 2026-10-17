# 03 — Scope & Gates (final reconciliation 2026-10-16)

> **Final reconciliation.** Applies 18 v3 §13 and the sponsor decisions in 19 (with its final amendments). Changes from the ambition pass: W3 voice → P2 opportunistic; W4 Mac three.js twin → W4-lite only if spatial dies early; W5 VLM label → CUT; W6 live iFixit → optional offline generality proof; **W8 Spatial added**; M10 owner A → B; X1/X2/X4 removed; sponsor integrations listed separately and isolated from P0. The clock-ordered list with owners is `21_HACKATHON_CHECKLIST.md`; the automatic release valves are 18 v3 §8.

Tiers:
- **P0**: the demo cannot die. The rocket/grid loop must run with Spatial, voice and every sponsor integration disabled or absent.
- **P1**: the winner layer: each item gated, flagged, and failing independently.
- **P2**: only after its gate and only if P0 + P1 are green. Never scheduled.
- **CUT**: do not start.

Ratings: GREEN proven/straightforward · YELLOW feasible, validate early · RED trap.

**Release-valve rules (18 v3 §8):** at each clock D reads green or red at the standup. Anything not demonstrably green at its clock is **red**; "almost" is red. The action fires with no discussion. **A killed feature is never reopened**; its hours go to the named fallback.

## P0 — must work
| # | Feature | Owner | Rating | Done when |
|---|---|---|---|---|
| M1 | Contracts (generic core + spatial, 05) + fixtures + `--mock-vision` replay; **one lock Sat 12:45** | D | GREEN | `make contracts` green; G2 sim + 2D supervisor render the full scenario from mocks |
| M2 | Board, markers, rectification, LAB cells, calibration | C | YELLOW | gate G2 |
| M3 | Part fitting incl. dots; cap bridging red + green | C | YELLOW | gate G2 |
| M4 | Occlusion gate + temporal vote (+ hand landmarks, 06 §14) | C | GREEN | T2/T5 + V2 pass |
| M5 | World model, diff (incl. `premature`), replanner, deviation classification, HUD arbiter (TDD, BFS test) | D | GREEN | `make core-test` green |
| M6 | WS hub, REST control, session log | D | GREEN | all roles connect; replay works |
| M7 | G2 plugin: 4-container page, modes, input, exit, ladder, persistence | B | GREEN/YELLOW | runs on real G2 from core |
| M8 | **Beta build reaches the laptop + passes QA** | B | YELLOW | gate G0 + 08 §11 |
| M9 | Golden target JSON (hand-authored, from the Studio model) | D | GREEN | used if the compiler fails; CI-diffed |
| M10 | 2D supervisor page (HUD mirror, plan, turns, provenance, log), served by core | **B** | GREEN | 21:30; fallback = core-served text page |
| M11 | Demo runbook, reset kits (rocket + rover), backup video | A + C | GREEN | 90 s scripts rehearsed |
| M12 | Eval numbers (10), incl. the Even quiet metric | D (+ A) | GREEN | table filled with real n |

## P1 — winner layer
| # | Feature | Owner | Rating | Gate (clock) |
|---|---|---|---|---|
| W1 | **Answer engine** (deterministic, cited) + **G2 contextual menu**: 1 `WHY THIS STEP?` · 2 `WHERE DOES IT GO?` · 3 `CAN I SKIP?` · 4 `WHAT'S DONE?` · 5 `WHAT NEXT?` | D (engine), B (menu) | GREEN | menu answers on real G2 ~19:00; **D valve 21:30** → engine limited to WHY/WHAT_NEXT/CAN_I/WHAT_DONE, item 2 hidden |
| W2 | **Manual compiler:** LDraw → task graph/target (deterministic) + Opus PDF extraction → evidence + validator + review | D | YELLOW | **K1 17:00** (red → authored evidence for rocket and rover sheet; extraction frozen, not debugged) · G3 21:00 |
| W4-lite | Mac three.js twin of the rocket, **only if the spatial lane is killed at S2 (17:30) or S4 (19:30)** | A | YELLOW | 23:00 (red → M10 2D supervisor) |
| W6 | **Generality proof, offline, optional** (18 v3 §11): one real external repair guide (iFixit 158506 as a saved PDF) through the same `service_pdf` path; Devpost/README only, "compiled, not executed" | D | YELLOW | 08:30 validated; dropped if K1 fired, the rover sheet didn't compile, or any code change is needed |
| W8 | **Spatial prototype** (18 v3): native iPhone RealityKit app, exact rover CAD, base locked in AR, motor = one markerless hero, deck/bar on image cards, `adapters/spatial_pose` → core → planner → G2 | A (app + rig), C (adapter, only after G2 at 20:00), D (CORE-MIN / CORE-FULL) | YELLOW | S0–S8 (below); spatial leads only under 18 v3 §9 |

**W8 phone MUST features (exactly seven; V2 §9.1):** live CAD registered to reality · target ghost · current-vs-target spatial diff · select/highlight · one explode control · intelligent goal-specific teardown · honesty/source labels.

## Sponsor integrations (outside P0/P1; isolated; never imported by P0)
| # | Integration | Code | Lands | Kill |
|---|---|---|---|---|
| I1 | **Sentry bridge**: read-only tail of `logs/session-*.jsonl` → Tracing + Logs (+ Issues) | Devin → `integrations/sentry_bridge/` | B, Sat 22:00–22:30 (B's polish valve) | 23:00 live trace; 08:30 real finding + decision or not entered |
| I2 | **Fetch agent**: ASI:One supervisor (uAgent, mailbox, ACP, cards, ARMED switch) | Devin → `integrations/fetch_agent/` | B, Sun 06:45–07:45 under the isolated sponsor-client exception | F0 Fri · F1 00:30 · Beta QA 06:45 · F2 07:45 · F3 08:15 |

No sponsor code may live in or modify `core/`, `contracts/`, `perception/`, `g2/` or `spatial/`.

## P2 — only after gates, never scheduled
| # | Feature | Owner | Gate |
|---|---|---|---|
| W3 | **Hold-to-ask voice** (plugin PTT + Deepgram Flux + Haiku intent). May start only if every gate up to that clock is green **and** the person starting it has no assigned task in that slot; must pass G1 and G5 and be merged flag-off before 00:45 (PTT touches the P0 plugin) | B + C | G1, G5 (only if it starts) |
| X3 | MANUAL_SAYS free-form cited QA (Haiku + `search_result` citations) | D | only if W3 shipped |
| X5 | Swipe `detail` page (plugin-local view, not a core `hud.mode`) | B | — |
| — | Spatial stretch (V2 §9.2: deck X-ray toggle, minimal component sheet, LiDAR occlusion, battery card, B1 ArUco base, deck A2) | A / C | every MUST green, flagged, before 00:45 |

## CUT (do not start)
- **Perception:** YOLOE/ByteTrack · Brickognize · SAM 2/3/EdgeTAM · learned 6-DoF on GPU/cloud (FoundationPose etc., CUDA-only) · LiDAR depth for state · Prompt Depth Anything / depth models · scene reconstruction · the VLM foreign-object label (W5) · hero-tag 6-DoF float (X1) · Mac AR ghost (X2).
- **Phone app** (18 v2 §9.3): generic scan/identify · internet model lookup / CAD search · image-to-3D · generic component sheets · elaborate X-ray · in-phone chat/Q&A · manual thumbnail browser · generic product recognition · complex teardown timeline · rocket AR on the phone.
- **Knowledge / guidance:** live iFixit demo · G2 guided mode (X4) · compiler at demo runtime.
- **Voice:** local STT (parakeet) · continuous listening · wake word.
- **Other:** handheld scanning · Technic · powered motor functional verification (Hardware Lab) · public store submission.
- **Sponsors:** StepFun · Cognition-specific features (e.g. a "Devin verifies reality" MCP) · Fetch Payment Protocol · a second agent · image cards beyond an optional URL · the Sentry JS SDK in the G2 plugin · Paper, QNX, Espressif, Base44, Visa, Intuit, Photon, Browser Use, CREAO, veri, MLH platform prizes.

Native code is allowed **only** in `spatial/` (and the optional Swift `hands_helper`). On-phone ML is allowed **only** as ARKit image/object tracking (Create ML `.referenceobject`).

## Gates (single source of truth for pass/fail; clocks match 18 v3 §8 and 19 §14)
| Gate | Clock | Owner | Pass | Red → automatic action |
|---|---|---|---|---|
| S0 tooling | Fri night | A + trainer owner | iOS 27 spatial phone; Xcode 27 signs to it; `createml objecttracker -h`; sample ETA | No iOS 27 → A2 dead (cards only). No Xcode 27 Mac → spatial lane dead; A plans W4-lite |
| F0 Fetch | Fri night | A | official example agent answers in ASI:One | Fetch dead before the hack |
| G2 loan | Sat 12:30 | B | loaner approved | Even effectively lost; optimise for Overall (08 §14) |
| **Contract lock** | **Sat 12:45** | D | every core + spatial schema and fixture in `contracts/`; `make contracts` green | The whole lock moves as one unit; nobody codes against a partial schema |
| S1 motor training | 13:45 | A | job running, ETA ≤ 22:45 | A2 dead; motor gets a card; no retraining |
| **G0 transport** | **15:00** | B | Stub Beta `.ehpk` shows laptop-pushed text over LAN `ws://` or Funnel `wss://`; round trip < 300 ms; survives 5-min lock | Funnel by 16:00; own router/hotspot; both fail by 17:00 → all hands on transport |
| Devin dispatch | 15:15 | B | both briefs dispatched | Devin not used (19 §14) |
| V2 hands | 16:00 | C | 0 false commits over 20 insertions | Motion-energy gate |
| **K1 extraction** | **17:00** | D | ≥ 80% steps' part multiset correct; 100% schema-valid | Authored evidence for the rocket **and** the rover sheet; extraction frozen; W6 cancelled |
| S2 app floor (kill) | 17:30 | A | app on device, base gizmo aligned | Spatial lane dead; A builds W4-lite from 17:30 |
| S3 rig | 18:15 | A | deck, bar, chassis built; cards mounted; `component_frames.json` | Deck + bar only |
| S4 cards | 19:30 | A | Gate A for the cards (18 v3 §6.2), 0 unsafe errors | Spatial lane dead; A builds W4-lite 20:00–23:00 |
| M3 | 19:30 | all | live replanning + dependency catch on hardware | (milestone) |
| **G2 perception** | **20:00** | C | bench under venue light: 19/20 correct states; 0 wrong commits | C stays on P0 entirely and never starts the adapter; spatial visual-only; S6/S7 cancelled |
| G3 compile | 21:00 | D | compiled target == golden; every step ↔ PDF page | Golden target + hand citations |
| **D valve** | **21:30** | D | G3 green, rover bundle merged, WHY answering on the fixture | Engine limited to WHY/WHAT_NEXT/CAN_I/WHAT_DONE; item 2 hidden; review page → JSON diff |
| M10 | 21:30 | B | 2D supervisor page | Core-served text page |
| Motor training done | 22:45 | trainer | `.referenceobject` exists | A2 dead; motor card |
| W4-lite | 23:00 | A | only if being built | M10 2D supervisor |
| **Sentry kill** | **23:00** | B | live `glasses_instruction` trace from a real run in Sentry | Sentry dead, never reopened |
| **S5 motor** | **23:30** | A (C as hand) | motor Gate A + Gate B (18 v3 §6) | Motor card; spatial cannot lead |
| **CORE-FULL** | **23:30** | D | `teardown.py`, inspect action, `requires_goal`, `/control/goal` unit-green | Merge CORE-MIN only; 90 s spatial script dead; +20 s add-on still possible |
| **S6 / F1** | **Sun 00:30** | C + D / D | replay loop green (V2 §13) / Fetch PR green + clarification "yes" + exception approved | Spatial visual-only, no more core spatial work / Fetch dead |
| **Core merge cutoff** | **00:45** | D | — | Nothing spatial merges into `core/` or `contracts/`; no schema change of any kind; stretch stops |
| **P0 FREEZE** | **02:00** | D | 5 consecutive clean rocket runs | Nothing merges into P0 paths |
| Footage secured | 02:45 | all | rocket footage on 2 drives + cloud | S7 does not start until it is |
| S7 live loop | 03:30 | A + D | 0 wrong G2 instructions over 10 trials; 10-min drift check | Visual-only add-on |
| **Product feature freeze** | **04:00** | all | — | Bugs and rehearsal only. **One isolated sponsor-client exception** may exist for `integrations/fetch_agent/` (below) |
| S8 selection | 04:15 | A + D | 5 clean 90 s spatial runs | The rocket leads |
| Even Beta QA | 06:45 | B | Beta #N QA signed | Fetch dead (B stays on Even) |
| F2 | 07:45 | B | live ASI:One: intent → state → Approve → G2 instruction → status → VERIFIED on the real rig | Fetch dead |
| F3 | 08:15 | B | shared-chat URL + 20–30 s ASI:One clip delivered to A | Fetch dead; no FETCH export |
| **Video / eval / Sentry** | **08:30** | A / D / B | GENERAL export (2:50–2:58) done; eval table filled; Sentry entry condition holds | Ship the rough cut; delete unmeasured rows; Sentry not selected |
| W6 generality proof | 08:30 | D | validated offline | Dropped |
| FETCH export | 09:00 | A | 3:10–3:30 export (only if F3 green) | Fetch not submitted |
| Workday gate 1 | 09:00 | A | multi-challenge confirmed + exports done | Not entered |
| Submissions complete | 10:30 | all | Devpost + every selected challenge's materials complete | Deselect any incomplete sponsor |
| Lead + final Beta | 11:00 | D / B | 18 v3 §9 lead rule; final Beta pushed; QA signed | Ties go to the rocket |
| **Deadline** | **12:00** | — | — | — |

**Isolated sponsor-client exception (the only post-04:00 change allowed; 19 amendment 4).** It may exist only if all are true: F1 green at the 00:30 standup; D approves at 00:30; the Fetch agent's tests are green; code is isolated in `integrations/fetch_agent/`; it consumes only frozen APIs/contracts; it runs as a separate process on B's machine; `GB_AGENT_ARMED` defaults to 0; Even Beta QA is green before B spends time on it; it cannot alter GhostBuild when not running. It may land the tested integration, set env vars, register/connect Agentverse, run ASI:One QA and fix client-local bugs. It may **not** change interfaces, core, contracts, perception, planner logic, G2 or Spatial, or request a Beta rebuild. **Any forbidden change needed → Fetch dies.**

## Mock modes (every vertical runs alone)
| Vertical | Mock input | Check |
|---|---|---|
| perception | recorded video/stills | `--print` / `--dump` overlays |
| core | `--mock-vision scenarios/*.yaml` + `knowledge/fixtures/*.json` | jsonl log; golden HUD/answer snapshots |
| knowledge | cached PDF/LDraw fixtures | bundle validates; diff vs golden |
| spatial adapter | synthetic `pose_observation` sequences; A's recorded sessions | 18 v3 §3.4 tests T1–T14 |
| spatial phone | `contracts/examples/twin_v2.json`, `spatial_transforms.json` | Swift transform tests 1–7 |
| g2 | `?mock=1` canned HUD/answer frames; simulator | simulator screenshots |
| 2D supervisor | `?replay=logs/*.jsonl` | screen |
| integrations | `core --mock-vision` + its session log | `pytest` in each `integrations/*` dir |
| voice (P2, only if started) | WAV files → `/ws/audio`; text via `/control/ask` | turn records |
