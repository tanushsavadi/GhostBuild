# 20 — Final Implementation Bible

**Status:** operational source of truth for LA Hacks AI Hackathon 2026 (Sat Oct 17 12:00 → Sun Oct 18 12:00 PDT). Frozen 2026-10-16.
**Read this instead of docs 00–19.** Go to a source doc only for detail: contracts **05**, spatial **18 v3** (+ the 18 v2 sections it keeps in force), sponsors **19** (+ its final amendments), clocks **21**.
**Precedence if anything conflicts:** this doc and the final amendments → 18 v3 → 19 (sponsors) → 18 v2 (sections V3 keeps) → 17 → 00–16.

---

## 1. One-sentence product
**GhostBuild is an AI copilot for physical work: it reads the manual and the CAD, watches the real object, and shows one verified next action on Even G2, replanning from whatever you actually did and going dark when the work matches the target.**

## 2. What we are actually building

| Layer | What | Must survive without |
|---|---|---|
| **P0** | The **rocket/grid loop**: fixed overhead camera → ArUco board registration → deterministic LAB-cell perception + part fit → temporal stability vote → world model → physical diff → dependency-aware planner → G2 HUD → verify / replan → `● VERIFIED` → dark. Plus the 2D supervisor page and Beta build. | Spatial, voice, Fetch, Sentry, every sponsor integration |
| **P1** | Manual compiler (CAD → task graph; Opus → cited evidence, gate K1) · deterministic cited answer engine via the **G2 contextual menu** · **Spatial prototype** (native iPhone RealityKit app, exact rover CAD, base locked in AR, one markerless motor, cards on deck/bar, tracked pose → adapter → world → planner → G2) | — |
| **Sponsor integrations** (isolated, Devin-built, B lands) | `integrations/sentry_bridge/` (Tracing + Logs from the session log) · `integrations/fetch_agent/` (ASI:One supervisor agent) | — |
| **P2** (never scheduled) | hold-to-ask voice · MANUAL_SAYS · `detail` view · spatial stretch | — |
| **Optional, offline** | generality proof: one real repair guide through the same compiler, "compiled, not executed" | — |

**Fallback ladder:** spatial leads (all gates) → rocket leads + spatial +20 s add-on with a G2 claim (motor on a card or not markerless) → rocket + visual-only spatial (no G2 claim) → rocket only (+ W4-lite twin if spatial died by 19:30, else 2D supervisor) → if G2 hardware fails: simulator + through-lens recording, optimise for Overall.

## 3. System architecture
```
                       REMOTE SUPERVISOR ─► ASI:One ◄─► Agentverse mailbox            SENTRY cloud
                                              [OPTIONAL: FETCH]                        [OPTIONAL]
                                                     │ ACP                               ▲     ▲
            B's LAPTOP ┌──────────────────────────────▼──────────┐   tool spans         │     │
                       │ integrations/fetch_agent (GB_AGENT_ARMED=0 default) ──────────┘     │
                       └──────────────┬──────────────────────────┘                           │
                                      │ LAN: GET /health, /knowledge, one-shot ws?role=twin,  │
                                      │ POST /control/task|reset|goal (ARMED + approved only)  │
┌──────────────── MAC 1 — P0 ─────────▼──────────────────────────────────────────────────────┼──┐
│ USB webcam ─► perception/ (grid CV, abstain, vote) ─► observation(source=cv) ─┐             │  │
│ spatial phone ─► :8790 adapters/spatial_pose (V3 state machine) ─► observation(source=spatial)│
│                                    [P1, --spatial]                            ▼             │  │
│ core/ :8787  world → diff → planner (+teardown/inspect) → HUD arbiter · answer engine        │  │
│              └─► logs/session-*.jsonl ─► integrations/sentry_bridge (read-only, nice 19) ───┘  │
└──────┬──────────────────────────────────────┬────────────────────────────────────────────────┘
       │ hud (LAN ws / Funnel wss)            │ twin v2
       ▼                                      ▼
 PHONE 1 Even app ─BLE─► EVEN G2       SPATIAL iPHONE (iOS 27) RealityKit [P1]
 next action · menu · VERIFIED · dark  CAD twin · ghost · diff · teardown ─USB─► MAC 2 mirror + 2D supervisor
       ▲
       └── technician acts with their hands ─► camera / tracking observe ─► replan ─► VERIFIED
```

## 4. Source-of-truth contracts (05; **one lock Sat 12:45**)
- **Rule:** after 12:45, implementation may change; a shared schema changes only with **D + every consuming owner** (05 approval table). **After Sun 00:45 no schema change of any kind.** If the lock isn't complete at 12:45, the whole lock moves; nobody codes against a partial schema.
- **Ports:** core HTTP+WS `:8787` (`/ws?role=vision|g2|twin`, `/control/*`, `/knowledge/*`, `/health`, `/twin`) · spatial adapter `:8790/pose` · plugin dev `:5173`.
- **Frames/units:** `board` (rocket) and `base` (rover) share axes X right, Y away from the user, Z up. `T_A_B` maps B→A. **mm on the wire, metres in the app; 16 floats row-major.** Yaw CCW-positive; `rot_cw = (−yaw) mod 360`. `Pose.T = T_frame_component`, origin at the footprint's bottom centre.

| Message | Producer → consumer |
|---|---|
| `knowledge_bundle` (incl. rover `relations`, `occludes`, `task_flags.requires_goal`; documents carry `origin`) | `knowledge/` (build time) → core, agents (`GET /knowledge`) |
| `observation` (`source ∈ {cv, spatial, replay, mock, manual_override}`) | perception (C), spatial adapter (C) → core |
| `pose_observation` | spatial app (A) → adapter (C) |
| `world`, `diff`, `plan`, `turn` | core (D) → twin / log |
| `hud` (`mode ∈ {instruct, hold, verified, uncertain, idle}`) | core arbiter (D) → plugin (B) |
| `g2_input` (tap = recheck; menu 1–5), `hud_ack`, `hello` | plugin (B) → core |
| `twin` v2 (+ `spatial_state`, `teardown`, `highlight`, `honesty`) | core (D) → spatial app (A), 2D supervisor (B) |

**Locked enums (selection):** `status ∈ {present, absent, lifted, unknown}` · spatial `reason ∈ {hidden, lost, out_of_view, never_seen, ambiguous_seat, ambiguous_yaw}` · `pose_source ∈ {grid, tag, arkit_object, arkit_image, manual}` · `base.source ∈ {image_lock, image_continuous, aruco, manual}` · `base.state ∈ {locked, unset}` · `verifier ∈ {grid_cv, object_pose, user_confirm(reserved)}` · `node.source ∈ {cad_derived, llm_extracted, authored, authored_demo_metadata}` · `plan.status ∈ {in_progress, verified, uncertain, occluded, no_board, awaiting_goal}` · verbs `REMOVE, LIFT, MOVE, ROTATE, PLACE, CLEAR, WAIT, DONE` · intents `WHY, WHERE, CAN_I, WHAT_NEXT, WHAT_DONE` (+ voice-only `MANUAL_SAYS, REPEAT, UNKNOWN`) · `SpatialState` = the 15 names in 18 v3 §3.2.
**Endpoints:** `POST /control/task {task_id}` · `/control/reset` · **`/control/goal {component}|{clear:true}` → `{goal, path}`** (access, inspect, correct; 404 when spatial off) · `/control/calibrate` · `/control/override` (bannered) · `/control/ask` (testing; never sponsor code) · `/control/ingest` (offline/build time only).
**Fixtures in the lock:** `pose_observation.json`, `twin_v2.json`, `control_goal.json`, `bundle_rover_excerpt.json`, `spatial_transforms.json` + the core examples.

## 5. Physical testbeds
| Rig | What it is | What it proves |
|---|---|---|
| **Rocket** (P0) | 16×16 plate, 4 ArUco corners, 10–12 System bricks in LAB-distant colours, dot stickers for 180° orientation, a black 2×4 cap bridging red 2×4 + green 2×2 | Deterministic perception with abstention; order-violation catch (`X CAP TOO EARLY`); replanning from any state (BFS-optimal on ≤ 2-defect states); quiet HUD; measured latency |
| **Rover** (P1 spatial) | 32×32 baseplate glued to a mat with a base card; chassis+battery (untracked), 6×6 asymmetric motor (markerless hero, gear on +X), L-shaped yellow bar and white deck (image cards); tile border around the motor bay | CAD registered to reality; tracked pose → world → planner → G2; goal-specific teardown from authored relations; occlusion-safe state (LAST SEEN vs never seen); "installed 90° off its documented orientation" → ROTATE |

The rover motor is a passive LEGO part. **Installation VERIFIED ≠ function VERIFIED.**

## 6. Spatial state machine (implementation-critical summary; exhaustive spec + tests T1–T14 in 18 v3 §3)
Evaluated per component per sample as a strict decision list (first match wins):
1. **Session gate:** camera tracking ≠ normal or base ≠ locked → **NO_COMMIT** (`board_visible: false`; plan `no_board`).
2. **Visible:** **LIFTED is tested before SETTLING** (above `z_ref` + `z_lift`, or tilt > `tilt_lift` in the zone; commits after 500 ms) → moving/unstable → **SETTLING** → outside the install zone → **REMOVED** (`absent`, `seen_off_assembly`; the *only* path to absent) → tilted or not seated → **AMBIGUOUS(ambiguous_seat)** → in zone but off site → **PRESENT_MISPLACED** → only now, at `SEATED_AT_TARGET_SITE`, classify yaw: **PRESENT_CORRECT** / **PRESENT_MISORIENTED(k)** / **AMBIGUOUS(ambiguous_yaw)**.
3. **Not visible:** < `t_hold` → **HOLD** (nothing changes) → covered by a committed-present occluder: **HIDDEN_LAST_SEEN** (keeps the state committed while visible, `stale`) only if the occluder arrived after that commit, else **HIDDEN_UNVERIFIED** → **OUT_OF_VIEW** → **NEVER_SEEN** → **LOST**.

Principles: **losing tracking never means absent** · stable-but-unseated is AMBIGUOUS · no ROTATE/MOVE/PLACE on SETTLING, HOLD, AMBIGUOUS, LOST, OUT_OF_VIEW, NEVER_SEEN or HIDDEN_UNVERIFIED · while anything is unknown, only the inspect action is allowed · thresholds are derived from measured σ and bias (18 v3 §6.4); load-time invariants must hold or spatial cannot lead.
**Base lock:** phase 1 detect the base image, average `T_world_base`, add a generic `ARAnchor` (`gb_base`); phase 2 re-run a same-type `ARWorldTrackingConfiguration` with module cards (+ motor reference object) via `session.run(config, options: [])` — never `.resetTracking` / `.removeExistingAnchors` after the first run. Read the anchor transform every frame. Interruption/relocalization → base `unset` → NO_COMMIT → re-lock between runs. Coexistence with `trackingObjects` is [verify] at S2 (fallback: B2-continuous base card).

## 7. Planner behaviour (07)
- Recomputed from scratch on every committed world. Pure functions; BFS-checked.
- **Step 0:** `requires_goal` and no goal → `awaiting_goal` (HUD idle) · occluded → hold head, dim · no board → `no_board` · any unknown → inspect action `LIFT <occluder>` / `TO CHECK <c>` if available, else `WAIT`/`CLEAR` abstention (`ADJUST …`, `SHOW … / TO THE CAMERA`, `CLEAR UNKNOWN ITEM`) or `CHECKING`; **never plan through unknowns**.
- **Priority:** `LIFT` (covering, premature, blockers, inspect) > `REMOVE` > `MOVE` > `ROTATE` > `PLACE`; stickiness prevents flapping.
- **Premature:** a node whose predicate holds but whose `requires` don't is wrong; the fix is to undo it (`X CAP TOO EARLY` / `X DECK TOO EARLY`).
- **Replanning:** expected progress → `●` then next; out-of-order progress accepted silently; distance not decreasing → deviation alert, then the corrective action.
- **Tap** = recheck on the latest committed world; never a forced commit.
- Spatial core tiers: CORE-MIN (discrete diff, `source: spatial`, twin v2) and CORE-FULL (teardown, inspect, `requires_goal`, `/control/goal`), gate 23:30.

## 8. G2 experience (08; Even is primary)
- **What the judge experiences:** instruction → physical action → mistake → corrective instruction → correct sequence → `● VERIFIED` → **dark display**, then one beat of silence.
- **HUD:** one action (≤ 20 / 28 chars) + tiny map (rocket only) + status; 4 containers; event-driven, ≤ 4 Hz; dims while hands work; idle 8 s after VERIFIED.
- **Input:** tap = recheck / dismiss answer · double-tap at root = exit (`shutDownPageContainer(1)`) · contextual menu **(P1)**: 1 `WHY THIS STEP?` · 2 `WHERE DOES IT GO?` · 3 `CAN I SKIP?` · 4 `WHAT'S DONE?` · **5 `WHAT NEXT?`** → the same grounded answer engine. Voice: P2 only.
- **On uncertainty:** abstain (`CHECKING`, `ADJUST …`, `SHOW …`, dim hold). Never a confident physical instruction from unknown state.
- **Measured quiet:** HUD changes per run and % of time dark/dimmed (E-a). **No new G2 UI.** No sponsor code or whitelist change in the plugin.

## 9. Spatial phone experience (exactly seven MUST features)
1. Live CAD registered to reality. 2. Target ghost. 3. Current-vs-target spatial diff (arc + live `90°` readout). 4. Select/highlight. 5. One explode control. 6. Intelligent goal-specific teardown (`FIX MOTOR ASSEMBLY` → only the blocking path explodes, numbered). 7. Honesty/source labels (`TRACKED·OBJ`, `TRACKED·IMG`, `CAD·LAST SEEN`, `UNKNOWN`, `TARGET`, `AUTHORED RELATIONS`, `MANUAL OVERRIDE`). Commits (green ring, G2) come only from core.

## 10. Knowledge / manual
- **Structure from CAD, words from the manual.** LDraw → task graph + target + support dependencies (`cad_derived`). Claude Opus 5.5 → per-page StepRecords → evidence, validated against the CAD (`llm_vs_cad n/m`); mismatches use CAD-generated text, labelled. Human review stamp. Bundles are committed; the compiler never runs during a demo.
- **K1 red at 17:00** → authored evidence for the rocket and the rover sheet; extraction frozen.
- Rover evidence comes from a **team-authored one-page service sheet** (always labelled `TEAM-AUTHORED SERVICE SHEET`); rover relations are **authored demo metadata**.
- **Optional external proof:** iFixit 158506 saved as PDF → same `service_pdf` path, offline, D at 07:45–08:30; Devpost/README/one frame show components · steps · warnings · evidence, captioned **"COMPILED, NOT EXECUTED"** (CC BY-NC-SA). Dropped if K1 fired, the rover sheet didn't compile, it isn't validated by 08:30, or it needs a code change.

## 11. Sponsors
| | Even Realities — PRIMARY | Sentry — SECONDARY | Fetch.ai — CONDITIONAL SECONDARY |
|---|---|---|---|
| **Tech owns** | The user-facing guidance surface: next verified action, menu questions, silence when correct | Live observability: photon-to-HUD traces, instruction audit trail, abstention log | Remote physical-job supervision: intent → inspect → plan → approve → dispatch → status → verified report, all in ASI:One |
| **Build** | nothing new (E-a quiet metric, three judge answers) | `integrations/sentry_bridge/`: read-only tail → Tracing + Logs (+ Issues, + agent spans) | `integrations/fetch_agent/`: uAgent, mailbox, ACP, 7 tools, 4 cards, `GB_AGENT_ARMED=0` default, `GB_CORE_URL` **required** (fail fast: `GB_CORE_URL is required; point it at the GhostBuild Core host.`), "workcell offline" replies |
| **Qualify** | Beta `.ehpk` on physical G2; Devpost challenge + app name; G2 in video; README G2 install; name `GhostBuild` | ≥ 2 products beyond errors (Tracing + Logs); **enter only with ≥ 1 real FINDING + ≥ 1 real DECISION** in `docs/sentry_findings.md` (FINDING · EVIDENCE · DECISION · RESULT) | Agentverse registration; ACP; reachable in ASI:One; meaningful tools; approval before mutation; workflow complete in ASI:One; public repo; README badges + agent address; Submission Agent (all teammates join); 3–5 min video |
| **Kill** | none of its own (no loaner → Even effectively lost) | 23:00 live trace · 08:30 entry condition | F0 Fri · "no" from Fetch any time · F1 00:30 · Beta QA 06:45 · F2 07:45 · F3 08:15 · any forbidden post-04:00 change |
| **Demo emphasis** | glasses first; end on the dark display | same physical run, then the trace + abstention log + one real finding→decision | ASI:One supervisor intent first (only if F2 green) |
| **Line** | "It only spoke when you needed it." | "Every instruction on the glasses is a Sentry trace back to the camera frame that justified it." | "Most agents turn intent into API calls. This one turns intent into a verified physical outcome." |

**Isolation:** sponsor code lives only in `integrations/`; it never imports or modifies `core/`, `contracts/`, `perception/`, `g2/` or `spatial/`; its only writes are `/control/task|reset|goal`, ARMED-only and approval-gated; killing it leaves GhostBuild byte-for-byte unchanged.
**Isolated sponsor-client exception (the only post-04:00 change):** for `integrations/fetch_agent/` only if F1 green at 00:30 **and** D approves at 00:30 **and** tests green **and** isolated **and** frozen APIs only **and** separate process on B's machine **and** `GB_AGENT_ARMED=0` default **and** Even Beta QA green first **and** inert when not running. May: land, configure env, register Agentverse, ASI:One QA, client-local fixes. May not: touch interfaces/core/contracts/perception/planner/G2/Spatial or request a Beta rebuild → **Fetch dies**.
**Also:** Beyond the Digital (organizer track) · MLH Commit opt-in · Workday framing-only (09:00 gate 1, 10:30 gate 2). **Network (don't build):** Sentry, Fetch, Cognition, Even, Workday. Hardware Lab: borrow a spare Logitech webcam only.

## 12. Team ownership
| | Owns | Never |
|---|---|---|
| **A** | Captain; spatial app + rover rig + motor asset/training kick-off; rocket Studio model; demo, video (both exports), Devpost overall/Even/BtD/Commit/Workday | — |
| **B** | G2 plugin, network, Beta + QA; M10 2D supervisor; lands Sentry (22:00) and Fetch (06:45, after Beta QA); findings log; Sentry + Fetch Devpost/README; Submission Agent | Fetch before Even QA |
| **C** | P0 perception + rocket testbed; spatial adapter **only after G2 at 20:00**; rig bench; rough cut v1 (master edit) | sponsor work; the adapter if G2 is red |
| **D** | Contracts (12:45 lock), core, planner, arbiter, compiler, answer engine, rover bundle, CORE-MIN/FULL, eval; reads every gate; F1 + exception decision | sponsor work on the core path |
| **Devin** | `integrations/sentry_bridge/`, `integrations/fetch_agent/` only, per 19 Appendices A/B (strict scope, exact interfaces, test command, DoD, no-rescue kill) | anything else |

**Capacity warning:** demand ≈ 88 h vs supply ≈ 72 h (A ≈ 19.3, B ≈ 21.2, C ≈ 22.75, D ≈ 24.8 vs ≈ 18 each). The 17:00, 21:30 and 23:30 valves are **expected** to fire.

## 13. Hard gates (full list with owners: 21)
| Clock | Pass | Red → |
|---|---|---|
| Fri S0 / F0 | iOS 27 phone + Xcode 27 / example agent answers in ASI:One | A2 dead (or spatial dead → W4-lite) / Fetch dead |
| 12:45 | contract lock, all schemas + fixtures | whole lock moves |
| 13:45 S1 | training running, ETA ≤ 22:45 | motor card |
| 15:00 G0 | Beta reaches the laptop; survives lock | Funnel → own hotspot → all hands |
| 17:00 K1 | extraction ≥ 80% | authored evidence; extraction frozen; no generality proof |
| 17:30 S2 | app on device, base gizmo aligned | spatial dead → W4-lite |
| 19:30 S4 | card Gate A, 0 unsafe errors | spatial dead → W4-lite |
| **20:00 G2** | P0 perception green | C stays on P0; spatial visual-only; S6/S7 cancelled |
| 21:30 | G3 + rover bundle + WHY on fixture | answer engine limited; item 2 hidden |
| 23:00 | Sentry live trace | Sentry dead |
| 23:30 S5 / CORE-FULL | motor Gate A + B / CORE-FULL unit-green | motor card, can't lead / CORE-MIN only |
| 00:30 S6 / F1 | replay loop / Fetch PR + clarification + exception | visual-only / Fetch dead |
| 00:45 | core merge cutoff | no spatial core work, no schema change |
| **02:00** | P0 freeze (5 clean runs) | nothing merges into P0 |
| 02:45 | rocket footage on 2 drives + cloud | S7 waits |
| 03:30 S7 / 04:15 S8 | 0 wrong G2 instructions / 5 clean 90 s runs | visual add-on / rocket leads |
| **04:00** | product feature freeze | bugs + rehearsal only (Fetch exception only) |
| 06:45 / 07:45 / 08:15 | Even Beta QA / F2 / F3 | Fetch dead |
| 08:30 | GENERAL video · eval · Sentry entry condition · generality proof | rough cut · delete rows · no Sentry · drop proof |
| 10:30 / 11:00 / 12:00 | submissions complete / lead + final Beta / deadline | deselect incomplete sponsors / rocket wins ties |

**Rules:** not demonstrably green at the clock = red; "almost" = red; the action fires with no discussion; killed work is never reopened.

## 14. Fallback ladder
| Situation | Result |
|---|---|
| Spatial passes every lead gate | Spatial 90 s lead; rocket as instant fallback |
| Spatial partial (motor on a card, or S5 not markerless, but S6 + S7 green) | Rocket leads + 20 s spatial add-on with a G2 claim ("That card is how it tracks this part.") |
| Only S4 passed | Rocket + visual-only spatial, said out loud |
| Spatial dead early (S2/S4) | Rocket + W4-lite twin (23:00) or 2D supervisor; A owns Fetch 23:00–01:00 |
| Spatial dead late | Rocket + 2D supervisor (reduced richness, stated honestly) |
| G2: Beta can't reach laptop | Funnel rung → own hotspot → QR sideload on own LAN for judging (Beta still submitted; say so if asked) |
| No G2 loan | Simulator + through-lens recording; optimise for Overall |
| Every sponsor integration dead | GhostBuild unchanged; enter Even + Beyond the Digital + Commit |

## 15. Demo decision tree
- **11:00, D decides:** spatial leads only if P0 freeze + footage secured · S5 markerless Gate A + B · S6 + S7 (0 wrong instructions) · CORE-FULL merged by 00:45 · S8 5 clean runs · re-lock + reset < 40 s at the table · phone ≥ 30 fps, no thermal warning · rocket ready as fallback. Otherwise the rocket leads. **Ties go to the rocket.**
- Sponsor judges change the **emphasis** of the same run (§11), never the product. The general pitch never lists sponsors.

## 16. Final video plan (one master edit → two exports)
| | GENERAL (Devpost overall, Even, Beyond the Digital) | FETCH (Submission Agent) |
|---|---|---|
| Length | **2:50–2:58** | **3:10–3:30** |
| Content | rocket primary footage (02:00–02:45) + spatial footage if it passed (04:15–04:45) + G2 through-lens + dark display | the same edit + a 20–30 s ASI:One beat: intent → plan/state card → approval → physical job → VERIFIED card |
| Who / when | C rough cut v1 = master edit 05:45–07:15 (with a marked insert point) → A final narration/captions 07:45–08:30 → **export by 08:30** | B delivers the ASI:One clip by 08:15 (F3) → A inserts the beat 08:30–09:00 → **export by 09:00**; skipped if F3 red |
Insurance clip at M3 (19:30). Show only gated-in features; if spatial is visual-only, say "tracked CAD, not yet wired to the planner". The external guide appears at most as one "compiled, not executed" frame.

## 17. Final submission matrix
| | Even | Sentry | Fetch | Beyond the Digital | MLH Commit | Workday (opt.) |
|---|---|---|---|---|---|---|
| Enter if | always (G2 + Beta) | entry condition at 08:30 | F1–F3 green | always | always | gates 09:00 + 10:30 |
| Platform | Devpost + Even Hub Beta | Devpost | Devpost + **ASI:One Submission Agent** | Devpost | Devpost opt-in + form | Devpost |
| Video | GENERAL | — | **FETCH export** | GENERAL | — | — |
| Repo/README | G2 install/run, accounts, keys | `sentry_sdk` usage, no DSN | agent name + address, `innovationlab` + `hackathon` badges, run instructions | public | public | public |
| Owner | B (Beta), A (Devpost) | B | B (agent, Submission Agent), all join | A | A | A |
| Deadline | Beta pushed by 11:00; Sun 12:00 | 12:00 | 12:00 | 12:00 | per form | 12:00 |
**Not entered:** Cognition, StepFun, and all other tracks.

## 18. Claims
**Allowed:**
- "Every instruction is computed from the live observed state; do something unexpected and watch it replan."
- "It catches order violations and tells you why, citing the manual" (and *which* manual: ours / team-authored).
- "The task graph comes from the CAD; the step evidence was AI-extracted and validated n/m against the CAD" (only if K1 passed; otherwise "authored").
- "It abstains rather than guess"; "wrong instructions in our trials: n" (measured).
- "Installed 90° off its documented orientation, so the fix is a rotation" (motor Gate A passed).
- "No marker on that motor" (only if S5 passed markerlessly).
- "It stayed synchronised with reality and drove the plan" (only if S6 + S7 passed).
- "The display changed n times and was dark n% of the time" (only if measured).
- "The same compiler also compiled a real repair guide — compiled, not executed" (only if validated).

**Not allowed:** "the motor isn't broken" / "it diagnosed the motor" / "functional verification" · "AI reasoned about the physical world" (the deterministic planner did) · "CAD-derived blockers" (they're authored) · "manual evidence" without naming whose manual · "exact CAD" without "the model we built it from" · "first AI that verifies physical assembly" · "a VLM checks your work" · any number not measured with n · presenting replay, override or recorded video as live · Sentry stories that aren't in `sentry_findings.md`.

## 19. Saturday "DO NOT BUILD" list
Voice (unless every gate is green and the person is genuinely free — and it's never scheduled) · new G2 UI · the Mac three.js twin (unless spatial is killed at S2/S4) · VLM foreign-object label · hero tag · Mac AR ghost · live iFixit / guided mode / `ifixit.py` · YOLOE, Brickognize, SAM, FoundationPose, LiDAR state, depth models · phone-app extras: scan/identify, model lookup, CAD search, image-to-3D, component sheets, elaborate X-ray, in-phone Q&A, thumbnail browser, product recognition, teardown timeline · powered motor verification · StepFun · anything for Cognition · Fetch payments, a second agent, image cards, a new frontend, a duplicate planner · the Sentry JS SDK in the plugin · any sponsor code outside `integrations/` · any schema change outside the approval rule · anything after its gate went red.

## 20. The winning story
Every repair guide assumes you did the last step right; nothing checks what you actually did. GhostBuild reads the manual and the CAD, watches the real object, and keeps an explicit model of its physical state. A deterministic planner recomputes the one next verified action from wherever the work really is, and Even G2 shows only that action — then goes dark when the work matches the target. When you skip ahead, it catches you, tells you why, and cites the page; when it isn't sure, it says nothing rather than guess. AI does what it's good at (reading documents); explicit state and planning decide what you're told. The innovation is the closed loop: reality, not a script, drives every instruction.
