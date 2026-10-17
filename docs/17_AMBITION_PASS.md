# 17 — Ambition Pass

**Research date:** 2026-10-16.
**Inputs:** six research agents (spatial/3D + LiDAR, learned vision, manual intelligence, voice on G2, embodied prior art, execution red team), plus benchmarks run on our hardware. The lead owns every decision; opinions were not averaged.

**Tags:** **[V]** verified source (URLs in §5 and 16) · **[M]** measured by us on an M3 Pro · **[I]** inference · **[D]** decision.

> **⚑ Final reconciliation (2026-10-16): partly superseded.** Still valid: §1's AI-vs-explicit-state reasoning, §2, §3 (except the twin and iFixit rows), §6 LiDAR, §7's learned-perception reasoning, §8 manual/RAG, §11 generic architecture (with the 05 clarification that action semantics are adapter-supplied). **Superseded:** voice as P1 (→ P2 per 18 v3 §8), the Mac three.js twin as P1 (→ phone RealityKit twin, 18 v3; W4-lite only if spatial dies early), the VLM foreign-object label (→ cut), iFixit live/G7 (→ offline proof per 18 v3 §11), StepFun as a target (→ dropped; targets in 19), the §15 gate table (→ 03 §Gates / 21), the hero tag (→ cut). Read `20_FINAL_IMPLEMENTATION_BIBLE.md` for what is built.

**Team hardware (confirmed):**
- Apple Silicon Macs only; no CUDA, no cloud GPU.
- Cloud AI APIs available.
- iPhone Pro with LiDAR; 2+ iPhones.
- Skills: native iOS/ARKit, PyTorch CV, three.js, LLM/RAG.

---

## 1. Executive decision

| | Quality-weighted /100 | Red-team P(win) estimate* |
|---|---|---|
| Current constrained GhostBuild (docs 00–16 before this pass) | **72** | 30 |
| Full upgrade as first proposed (everything ambitious at once) | 70 | 27 |
| **Trimmed upgrade (this decision)** | **84** | **41** |

*P(win) ≈ P(core demo works at the table) × P(win if it works), against ~20 teams for Even 1st or a top Overall placement. These are judgment estimates, not data.

Two findings drive the decision:
- **The constrained plan is reliable but generic.** At an AI hackathon its judge-facing AI story reduces to "colour thresholds + rules + glasses", and it lacks a judge-initiated G2 moment.
- **The full upgrade raises the ceiling but sinks P0.** It adds ~70 h of demand against ~80 h of total supply, overloads the two people on the critical path, and its weakest pieces (YOLOE on LEGO, LiDAR layers, jittery 6-DoF) have P(works) between 0.15 and 0.40.

### Verdict: **UPGRADE TO the "Manual-Compiled, Perception-Verified Copilot" — trimmed.**
- **P0 is untouched** and remains the authority for physical state.
- **Four P1 layers are added, each behind a gate and a flag:**
  1. **Cited answer engine** — deterministic answers from the world model, with menu input first and G2 push-to-talk voice second *(final: voice P2 per 18 v3 §8)*.
  2. **Manual compiler** — LDraw CAD gives a deterministic task graph and target; Claude extracts per-step evidence from the instruction PDF, which is checked against the CAD.
  3. **Live CAD digital twin** — known LEGO geometry placed at inferred poses, with target ghost and diff arrows *(final: the phone RealityKit twin of the rover, 18 v3)*.
  4. **Hand-aware perception** (Apple Vision) as P0 hardening, plus **VLM naming of foreign objects** on the board *(final: VLM label cut)*.
- Everything else is P2-after-gate or cut.

### What does AI enable here that classical logic alone would not?
1. **Reading the manual.** Claude Opus 5.5 turns instruction pages into per-step evidence records (parts, placement, page) that every answer cites. For a text repair guide (iFixit) it proposes tools, warnings and which steps can be reordered, each backed by a quoted line. Without this, every citation and step description would be hand-typed.
2. **Understanding the user.** Speech → text (Deepgram Flux), then free-form question → intent and slots (Claude Haiku 5.5), while the user's hands are busy. Example: "can I put the black one back yet?"
3. **Open-world perception where the closed grid is blind.** Hand landmarks (Apple Vision ML) decide when the board may be read; a VLM names objects that aren't in the build ("REMOVE PEN").

### What does explicit state and planning enable that a VLM alone would not?
1. **Correctness on fine physical state.** VLMs are weak here:
   - LEGO Co-builder: ~40% F1 for GPT-4o on LEGO state [V].
   - RealityBench (Oct 2026): best F1 0.61; 75% of upright tape measures called tilted [V].
   - WorkBenchMark (RoboCup 2026): a structured perception → symbolic → planner pipeline reached 77.5% success, against 42.5% for a fine-tuned end-to-end VLA [V].
2. **A guarantee.** The HUD can only show actions the planner validated against observed state (the LLM-Modulo pattern [V]). Answers to WHY / CAN_I / WHERE / WHAT_DONE are rendered from planner data, so they cannot be hallucinated.
3. **Replanning from any state:** dependency catches ("NOT YET · GREEN FIRST"), out-of-order acceptance, and an inspectable history.
4. **About 1 s deterministic state updates**, against 1–5 s variable VLM calls.

---

## 2. What the previous design got right (all kept)
- **The P0 loop:** fixed overhead camera → ArUco → per-cell LAB → part fit → abstention + 5-frame vote → world state → typed diff → BFS-verified replanner → quiet HUD → verify.
- **"Abstain over guess".** One wrong instruction loses the demo.
- **Own network and connection ladder.** The Beta QA checklist, and all verified G2 platform facts.
- **Contracts-first, mock-first parallelism.** Session logs serve as the eval source.
- **Honesty map,** the labelled manual override, and eval numbers reported with real n.
- **Prior-art discipline,** and the Quiet-by-Design emission rules.

## 3. What was over-constrained
| Previous decision | Cost | Now |
|---|---|---|
| Target hand-authored as JSON | Looked scripted; "you hand-wrote the plan" attack | Target + dependencies **derived from CAD**; step evidence **extracted from the manual by Claude**; provenance shown |
| Voice cut | Missed the most natural hands-busy interaction and the strongest intelligence moment | Menu-first answer engine (P1); voice P2 per 18 v3 §8 |
| 3D twin as late stretch | Lost the visual wow, even though known-model rendering is honest and cheap | CAD twin (final: phone RealityKit, 18 v3) |
| LEGO-specific contracts | Invited "so you built a LEGO assistant" | Generic core entities; LEGO in an adapter |
| No generality proof | Capped the Product & Impact score | One real repair guide through the same compiler, offline proof per 18 v3 §11 ("compiled, not executed") |
| Learned perception rejected wholesale | Thin AI story | ML where it adds capability (hands, open-world naming, speech, language); the grid stays the authority where it is better |

## 4. New system architecture

```
 INGEST (build time, cached; shown as PRECOMPUTED with provenance)
 Studio model ──► rocket.ldr ──► LDraw parser ─► support graph + target poses     [DETERMINISTIC]
            └──► instructions.pdf ─► PyMuPDF ─► Claude Opus 5.5 page extraction   [REAL AI]
                                               └► StepRecords (parts, placement, page)
 iFixit 158506 JSON ─► mapper + Opus proposals (tools, warnings, reorderable) [REAL AI, P1-late]
          └──► validator: schema · acyclic · observable · LLM-vs-CAD step match  [DETERMINISTIC]
                └──► KnowledgeBundle (task graph, target, evidence, provenance) + review stamp [HUMAN]

 LIVE (Mac 1: perception + core)                        (Mac 2: twin + recording)
 webcam ─► P0 grid perception                      [CLASSICAL CV]
        ├► hand landmarks (Apple Vision) → freeze cells under hands      [REAL ML]
        ├► foreign-object crop → VLM label (async, never blocking)     [REAL AI]
        └► fusion: grid authority; learned may only veto        [DETERMINISTIC]
 core: WorldModel → Diff (incl. premature) → Planner (verifier) → HUD ARBITER [DETERMINISTIC]
       Answer engine: intent+slots → answer rendered from planner/world + evidence tag [DET]
         ▲ intents from: contextual menu (P1 first) │ PTT audio → Deepgram Flux → Haiku 5.5 [AI]
 g2 plugin: HUD · menu · push-to-talk                            [HUMAN INTERACTION]
 twin: LDraw CAD at inferred poses · target ghost · diff arrows · provenance · turns [VISUALIZATION]
```

| Component | Label | Owner | Tier |
|---|---|---|---|
| P0 grid perception | CLASSICAL CV | C | P0 |
| Hand landmarks → commit freeze | REAL ML | C | P0-hardening |
| World model, diff, planner, HUD arbiter | DETERMINISTIC | D | P0 |
| G2 HUD plugin + Beta | HUMAN INTERACTION | B | P0 |
| Answer engine (deterministic, cited) + menu | DETERMINISTIC + DOC RETRIEVAL | D (engine), B (menu) | P1 |
| LDraw → task graph / target | DETERMINISTIC | D | P1 |
| PDF page extraction → evidence | REAL AI | D | P1 (gate K1) |
| Push-to-talk audio capture | HUMAN INTERACTION | B | ~~P1~~ **P2 opportunistic (final)** |
| STT + intent server | REAL ML + REAL AI | C | ~~P1~~ **P2 opportunistic (final)** |
| CAD twin | VISUALIZATION (known model + inferred pose) | A | **final: phone RealityKit twin (W8, 18 v3); Mac W4-lite only if spatial dies early** |
| Foreign-object VLM label | REAL AI | C | **CUT (final)** |
| iFixit compile + cited answer | REAL AI | D | **final: optional offline proof, no answer (18 v3 §11)** |
| Hero-tag 6-DoF float | CLASSICAL CV | C/A | **CUT (final)** |
| MANUAL_SAYS free-form cited QA | REAL AI + DOC RETRIEVAL | D | P2 |
| AR ghost on camera feed | VISUALIZATION | A | **CUT (final)** |

## 5. Open-source / research leverage (final recommendations)

| Name | URL | Purpose | Hardware / compat | Setup | Latency | License | Integration | Rec. |
|---|---|---|---|---|---|---|---|---|
| OpenCV ArUco / solvePnP | github.com/opencv/opencv | Board registration; tag pose | CPU, Mac ✓ | trivial | ms | Apache-2.0 | in P0 | **USE** |
| Apple Vision hand pose | developer.apple.com/documentation/vision | Freeze commits under hands | macOS ✓ **[M] ~7 ms** | Swift helper | 7 ms | OS | 2 h | **USE (P0-hardening)** |
| MediaPipe Hand Landmarker | developers.google.com/edge/mediapipe | Python alternative | Mac (verify wheel) | pip | — | Apache-2.0 | 1 h | FALLBACK |
| Claude Opus 5.5 (`claude-opus-5-5`) | platform.claude.com | PDF page → StepRecords (structured outputs `output_config.format`) | hosted | key | ~1–2 min/manual in parallel [I], ≈$1.40/40 pp [I] | API ToS | 3–4 h | **USE (K1)** |
| Claude Haiku 5.5 (`claude-haiku-5-5`) | platform.claude.com | Intent + slots; P2 cited answers via `search_result` blocks | hosted | key | <1 s warm [I] | API ToS | 2 h | **USE** |
| Deepgram Flux (`flux-general-en`, `/v2/listen`) | developers.deepgram.com/docs/flux | Streaming STT; `ForceEndTurn` on release | hosted; linear16 16 kHz [V] | key | ~260 ms EOT (vendor) | API ToS | 2–3 h | **USE (G5)** |
| PyMuPDF | pymupdf.readthedocs.io | Render PDF pages | Mac ✓ | pip | ms | AGPL-3.0 | 15 min | **USE** |
| LDraw library + three.js LDrawLoader | ldraw.org · github.com/mrdoob/three.js (examples/jsm/loaders/LDrawLoader.js) | CAD geometry: support graph + twin rendering | browser / Python parser | `packLDrawModel.mjs` [V] | <50 ms update | CC BY 2.0/4.0 · MIT | 5 h (D) + 9 h (A) | **USE** |
| BrickLink Studio | bricklink.com/v3/studio | Design build; export instruction PDF + LDraw | Mac ✓ [I] | free | — | free | 2–3 h authoring | **USE** (see §16 rules note) |
| LeoCAD / LPub3D | leocad.org · github.com/trevorsandy/lpub3d | Fallback LDraw + PDF authoring with `0 STEP` | Mac ✓ [V] | dmg | — | GPL | 2 h | FALLBACK |
| iFixit 158506 | ifixit.com/api/2.0/guides/158506 | Real repair procedure (generality) | hosted, no key [V] | save as PDF | — | CC BY-NC-SA 3.0 | ~15 min review | **OPTIONAL offline proof** (18 v3 §11) |
| Gemini Flash / StepFun step-5-preview | ai.google.dev · StepFun docs | Foreign-object label | hosted | key | 1.5–4 s [I] | API ToS | 1–2 h | **CUT (final)** |
| Docling | github.com/docling-project/docling | Text service manuals with page provenance | Mac ✓ | `pip install docling` [V] | s/page | MIT | 1 h | FALLBACK (future text PDFs) |
| YOLOE-11s-seg | github.com/THU-MIG/yoloe | Open-vocab masks | MPS **[M] 50 fps generic**; LEGO untested | pip | 20 ms | AGPL-3.0 | 6 h | **CUT** (P=0.35, impact 1; closed known part set doesn't need open vocabulary) |
| Brickognize | api.brickognize.com | In-hand part ID | hosted **[M] 0.45–0.8 s** | curl | 0.6 s | ToS? | 3 h | **CUT** (known closed set; little judge value) |
| SAM 3 / SAM 2.1 / EdgeTAM | github.com/facebookresearch/sam3 | Segmentation | CUDA / Mac ~2 s per frame [V] / 157 ms [M] | heavy | — | SAM Lic. / Apache | — | **CUT** |
| FoundationPose, MegaPose, SAM-6D, Any6D, GigaPose | github.com/NVlabs/FoundationPose etc. | Learned 6-DoF | CUDA (+depth) [V] | — | — | various | — | **REJECT** (still; on-device ARKit object tracking replaces it for one module, see 18 v3) |
| ARKit sceneDepth / Stray Scanner / Record3D | developer.apple.com/documentation/arkit · github.com/strayrobots/scanner | LiDAR layer vote | iPhone Pro | Xcode | — | Apple / MIT / LGPL | 8 h | **CUT** for state (P≈0.15: ~1 cm noise vs a 9.6 mm step). ARKit image/object tracking **is** used by the spatial lane (18 v3) |
| Prompt Depth Anything, Depth Anything 3, VGGT, DUSt3R/MASt3R, MoGe, Depth Pro | various | Depth / reconstruction | CUDA-centric; cm-level error | — | — | mixed (some NC) | — | **REJECT** (don't help a known-object twin; blur the honesty claim) |
| parakeet-mlx | github.com/EliFuzz/parakeet-mlx | Local STT | MLX | pip | — | — | 3 h | **CUT** (the menu is the fallback) |

## 6. LiDAR decision
**CUT from the hackathon build. Documented as future work.** The decision is evidence-based, not taken for simplicity:
1. Published iPhone LiDAR accuracy is about ±1 cm on objects larger than 10 cm, and noise peaks at edges. The only bit LiDAR could add (layer 1 vs 2, a 9.6 mm step) sits at the noise floor [V/I].
2. A 2×4 brick spans ~16×8 depth pixels at 35 cm, and Apple RGB-guided fill blurs those [I].
3. The team has no CUDA, so Prompt Depth Anything's dense refinement is untested on MPS and ≥ 0.5 s per frame [I].
4. Layer is already known from the target prior plus colour. The demo never depends on height.

Red team: P(works) 0.15 for 8 h. If an idle hour appears **before Sat 20:00**, the zero-code Stray Scanner + Open3D height test (§06 history) may run for the Devpost "what we tried" section only.

## 7. Learned perception decision
- **Used:**
  - **Apple Vision hand landmarks** freeze commits for any footprint under a hand. This is ML that protects P0 and replaces the motion heuristic as the primary occlusion gate.
  - **A VLM labels foreign objects** in P0's existing unknown regions ("REMOVE PEN"), asynchronously.
- **Not used:** YOLOE, Brickognize and SAM. Their capability (open vocabulary over a closed, known part set) adds little; their risk (untested LEGO accuracy, GPU contention, API latency) lands on the critical-path person.
- **Rule:** learned evidence can veto for at most 1.5 s, behind a kill switch, and never commits placement.

## 8. Manual / RAG decision
- **No vector database.** A manual fits in context with prompt caching.
- **Structure from CAD, words from the manual:**
  - **LDraw → task graph, target and support dependencies** (deterministic, `source: cad_derived`).
  - **Claude Opus 5.5 → per-page StepRecords** (structured output) → evidence records with page and step.
  - Validator shows "LLM extraction vs CAD: n/m steps match". Mismatched steps fall back to CAD-generated descriptions, labelled as such.
- **Answers:** WHY / WHERE / CAN_I / WHAT_NEXT / WHAT_DONE render from planner data and attach the node's evidence tag (`[MANUAL STEP 6]`). That makes citations valid by construction.
- **P2 MANUAL_SAYS:** Haiku over `search_result` blocks with citations enabled. Citations can't be combined with structured outputs, and diagram-only PDF pages aren't natively citable [V]; synthesised evidence text solves both.

## 9. Voice / conversation decision — AMENDED: voice is P2 opportunistic per 18 v3 §8; the menu (items 1–5, item 5 = WHAT NEXT?) is the P1 path
- **One answer engine with three inputs, built in this order:**
  1. Contextual menu (P1, built first, ~20 min, no audio).
  2. Phone-page text box (testing).
  3. **G2 hold-to-ask:**
     - Plugin: `LONG_PRESS_EVENT` → `audioControl(true, Glasses)` → PCM over the `/ws/audio` socket → `LONG_PRESS_RELEASE_EVENT` + 250 ms tail → `ptt end`.
     - Core: Deepgram Flux, `ForceEndTurn` → Haiku 5.5 intent/slots → answer engine → HUD ANSWER slot (8 s TTL).
- `? SAY AGAIN` on low confidence. No partial transcripts on glass; no audio output (G2 has no speaker [V]).
- **Gates:** G1 mic (Sat 18:00) and G5 voice (Sat 23:30, ≥ 17/20 intents, p90 < 2.0 s). If either fails, voice leaves the script and the menu remains.

## 10. Digital-twin decision — SUPERSEDED (→ 18 v3 phone twin; W4-lite only if spatial dies early)
- **P1:** three.js + LDrawLoader on Mac 2, rendering the Studio model's exact parts.
- **Poses:** on-grid poses from the world model; translucent target ghost; arrow for MOVE, arc for ROTATE; dashed wireframe when uncertain.
- **Banner:** "Exact LEGO CAD (LDraw) at vision-estimated poses — not a 3D scan."
- **Fallback:** 2D supervisor view.
- **P2 (gated, physically removable):**
  - Hero-tag 6-DoF float (separate ArUco ID range, tag quad masked before cell sampling).
  - AR ghost on the camera panel.

## 11. Generic product architecture
- **Core entities:** `Task, DocumentSource, Evidence, Component, Tool, Warning, Step, TaskGraph(Node{predicate, verifier, requires, evidence, source}), TargetState, Pose, Observation, WorldState, PhysicalDiff, Action, ConversationTurn`.
- **Predicates:** `placed`, `absent`, `removed`, `connected`, `disconnected`, `user_confirmed`.
- **Verifiers:** `grid_cv`, `tag_pose`, `vlm_keyframe`, `user_confirm`.
- **Adapters:** `adapters/lego_grid` (perception → predicates, LEGO phrasing, LDraw); `adapters/guided` (user-confirm, used by iFixit).
- **Rule:** `core/` and `contracts/` never contain LEGO terms; CI greps for them (15 §7).

## 12. Generality proof — SUPERSEDED (→ offline proof per 18 v3 §11; no live answer, no G2 flow)
**Same compiler, a real repair manual.** Ingest iFixit 158506 (DeLonghi EC220 pump replacement: 11 steps, tools, ULKA pump), then:
- The supervisor screen shows the compiled task graph with step citations.
- A menu or voice question "What tools do I need?" → G2 answer slot `TORX T20 · PH1 / [IFIXIT STEP 1]`.

**Cost and fallback:** ~2–3 h for D, gate G7 at Sun 04:00. If the gate fails it appears in the video and Devpost only. Live G2 guided mode is P2.

## 13. Prize strategy — SUPERSEDED / HISTORICAL (→ 19: Even primary, Sentry secondary, Fetch conditional, Beyond the Digital; StepFun dropped)
1. **Even Realities.** A judge-initiated question answered with a reason on the glasses, then silence, hits "Made for G2" and "Quiet by Design" directly.
2. **Overall via "Beyond the Digital".** AI does real work (compiler, speech/intent, perception guards), with explicit state as the safety layer.
3. **StepFun (conditional).** `step-5-preview` as the foreign-object labeller, if the prize exists and the API supports images in < 4 s. Otherwise no third target.

## 14. Demo (final scripts in 11_DEMO_RUNBOOK; questions via the menu, not voice)
**Build redesign:** the black cap bridges **red and green**. That turns the dependency catch into the centerpiece.

**90-second arc:**
1. Compiled manual with provenance on screen.
2. HUD: `LIFT BLACK 2x4`.
3. "Why?" → `RED UNDER IT IS FLIPPED / [MANUAL STEP 6]`.
4. The judge turns red → `ADD GREEN 2x2`.
5. "Can I put the black back?" → `NOT YET / GREEN FIRST`.
6. They do it anyway → `X CAP TOO EARLY / LIFT IT` → replan.
7. Green, then cap → `● VERIFIED` → HUD goes dark.

**The unforgettable moment:** the judge tries to cut the order and the glasses stop them, with a reason.

## 15. Feasibility gates — SUPERSEDED / HISTORICAL (→ 03 §Gates and 21; G1/G5 only if voice starts; G4/G6/G7 retired)
| Gate | Deadline |
|---|---|
| G0 transport | Sat 15:00 |
| K1 manual extraction | Sat 17:00 |
| G1 mic | Sat 18:00 |
| G2 perception | Sat 20:00 |
| G3 compile | Sat 21:00 |
| G4 twin | Sat 22:00 |
| G5 voice | Sat 23:30 |
| G6 hero tag (P2) | Sun 01:00 |
| **P0 FREEZE** | **Sun 02:00** |
| G7 iFixit live | Sun 04:00 |
| Feature freeze | Sun 04:00 |

## 16. Red team: why this could still lose
1. **P0 perception is flaky at the table.** C must not touch anything else before G2. Own lamp, locked white balance, one-key recalibration, 50-trial bench test.
2. **Transport or Beta fails.** That means no Even prize. G0 is first; try both rungs; bring our own router; run QA Saturday night.
3. **A 4 AM integration breaks P0.** P0 freeze tag at 02:00; flags; isolation rules (04 §8).
4. **The HUD is unreadable, or the demo runs long.** 90 s script, 10 rehearsals, fit checklist, HUD mirror.
5. **Voice fails live** (`? SAY AGAIN` twice). Menu first; a phrase card for the judge; Deepgram keyterms.
6. **Video or Devpost late.** A's video work starts Sun 04:00 and doesn't move.
7. **"LLM wrapper + eye candy" perception.** Lead with closed-loop verification and deterministic cited answers. Say "CAD ground truth, LLM-extracted evidence, validated."
8. **Cloud outage.** The demo path works offline: precompiled bundle, deterministic answers, menu input.
9. **Rules risk:** authoring the Studio model and instruction PDF *before* hacking starts could be judged prior work. Do it **after 12:00 Sat** (≈2 h, C/A), or ask organizers at check-in whether a pre-designed physical testbed is allowed (it isn't code, but confirm).

## 17. Final build recommendation — SUPERSEDED (→ 20_FINAL_IMPLEMENTATION_BIBLE §2)
Build P0 exactly as specified, with hand gating added. In parallel, build the four P1 layers, each behind its gate:
1. answer engine (menu → voice)
2. CAD-grounded manual compiler with LLM evidence extraction
3. CAD twin
4. foreign-object VLM label

Freeze P0 at 02:00. Ship the 90-second demo whose centerpiece is the dependency catch with a cited reason. Everything else is P2 or cut.

### Self-critique
| Question | Answer |
|---|---|
| Looks like an AI hackathon winner? | Yes. A closed loop, an AI-read manual, spoken questions with cited answers, and a physical catch. |
| AI central or decorative? | Central to reading documents and understanding the user. Deliberately *not* trusted for fine physical state, which is the insight. |
| G2 essential? | Yes. Hands busy, eyes on the work; a hold-to-ask temple gesture; silence when correct. |
| Understood in < 15 s? | "It reads the manual, watches your hands, and tells you only what to do next." |
| LEGO only the rig? | Generic core plus the iFixit proof; LEGO lives in an adapter. |
| Believable real-world use? | Repair and assembly with a manual: the coffee-machine pump guide. |
| Can four people execute it? | Rebalanced to ~20 h each (13_TEAM_PLAN). |
| Do ambitious parts fail independently? | Yes. Flags, gates, P0 freeze, one HUD arbiter. |
| Does P0 survive if P1 fails? | Yes. The demo still runs with menu or no questions and the 2D view. |
| Using research intelligently? | Yes: LDraw/three.js, Apple Vision, Claude structured outputs, Deepgram Flux, iFixit. CUDA research repos are rejected with evidence. |
| One unforgettable moment? | "Can I put it back?" → "NOT YET · GREEN FIRST" → the judge tries anyway → caught → fixed → VERIFIED → darkness. |

UPGRADE GHOSTBUILD: keep the grid-verified P0 loop as the sole authority on physical state, and layer on a CAD-grounded LLM manual compiler, a deterministic cited answer engine reached by G2 menu and push-to-talk voice, and a live CAD digital twin — each behind its own gate.
