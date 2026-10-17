# 15 — Implementation Handoff (for Claude Sonnet 5.5 / Claude Code agents / Devin)

> **Final reconciliation (2026-10-16).** Read `20_FINAL_IMPLEMENTATION_BIBLE.md` first, then this doc, then **only** your vertical's spec plus 05_CONTRACTS. Anything marked **[verify]** must be checked against the live docs or repo before you write code that depends on it. **Never invent an API.**

## 1. What to build
GhostBuild — an AI copilot for physical work, on Even G2. The LEGO rigs are testbeds; the data model is generic (05 design rule).
- **P0 loop (rocket):** overhead USB webcam → `perception/` (ArUco grid, LAB cells, part fit, abstention, hand-aware freeze) → `core/` (world model, diff incl. `premature`, deterministic replanner, HUD arbiter) → `g2/` plugin HUD on G2 → verify/replan. Must run with every other component absent.
- **P1 (each behind a flag and a gate):**
  - `knowledge/` compiler: LDraw → task graph/target; Claude Opus 5.5 PDF extraction → evidence (gate K1 17:00).
  - `core/answers.py`: deterministic, cited answers via the **G2 contextual menu** (items 1–5; item 5 = `WHAT NEXT?`).
  - **Spatial (W8):** `spatial/` iOS RealityKit app (A) → `adapters/spatial_pose/` (C, only after G2 at 20:00) → core CORE-MIN / CORE-FULL (D) → planner → G2. Spec: 18 v3 (authoritative) + 18 v2 §5, §7, §8, §9.1, §10, §11.3.
  - 2D supervisor page (M10, B).
- **Isolated sponsor integrations (Devin-built, B lands):** `integrations/sentry_bridge/`, `integrations/fetch_agent/` (19 Appendices A and B, as amended).
- **P2 only after gates, never scheduled:** hold-to-ask voice, MANUAL_SAYS free-form QA, swipe `detail` view, spatial stretch (18 v2 §9.2).
- **Optional, offline, no code changes:** the generality proof (18 v3 §11).
- **Only if the spatial lane dies at S2/S4:** W4-lite three.js twin of the rocket (09 §C).

## 2. What NOT to build
- YOLOE, Brickognize, SAM, learned 6-DoF on GPU/cloud, LiDAR depth for state, depth models, reconstruction, local STT, handheld scanning, Technic, the VLM foreign-object label, the hero-tag float, the Mac AR ghost.
- Live iFixit, G2 guided mode, `knowledge/ifixit.py`, calling the compiler during a demo run.
- Native code anywhere except `spatial/` (and the optional Swift hands helper). On-phone ML other than ARKit image/object tracking.
- In the phone app: generic scan/identify, internet model lookup, CAD search, image-to-3D, generic component sheets, elaborate X-ray, in-phone chat/Q&A, manual thumbnail browser, generic product recognition, complex teardown timeline.
- A rich UI on the user's phone, audio output, continuous listening, partial transcripts on glass. More G2 UI.
- Powered motor functional verification. StepFun anything. Cognition-specific features. Fetch Payment Protocol, a second agent, a new frontend, a duplicate planner. The Sentry JS SDK in the plugin.
- **Any sponsor code in `core/`, `contracts/`, `perception/`, `g2/` or `spatial/`.**
- **Do not put LEGO terms in `core/` or `contracts/models.py` source code** (CI greps `*.py`/`*.ts` there for `lego|brick|stud|2x4|ldraw`; example payloads and fixtures are data and are exempt).

## 3. Repo layout (exact)
```
ghostbuild/
  CLAUDE.md                     # §9, ≤ 25 lines
  Makefile                      # all commands in §6
  .env.example                  # ANTHROPIC_API_KEY (core/knowledge); SENTRY_DSN, GB_CORE_URL, GB_AGENT_ARMED=0, AGENT_SEED (integrations only). Never commit .env
  contracts/        (D)  models.py · schema/ · ts/index.ts · examples/*.json (incl. pose_observation, twin_v2, control_goal, bundle_rover_excerpt, spatial_transforms) · tests/
  core/             (D)
    ghostbuild_core/
      server.py          # FastAPI app, /ws, REST /control/*, serves /twin
      world.py diff.py planner.py events.py   # pure functions (07)
      teardown.py                             # CORE-FULL (07 §S)
      hud_arbiter.py compose.py               # single HUD writer (07 §H)
      answers.py                              # deterministic answer engine (07 §A)
      voice/                                  # P2 only, flag-off by default
      log.py
    tests/
  adapters/         lego_grid/ (D: grid pose↔T, phrasing, LDraw mapping) · spatial_pose/ (C: classifier 18 v3 §3.1, params.yaml, tests/)
  knowledge/        (D)  compile.py · ldraw.py · pdf_extract.py · validate.py · review.html
                         fixtures/ (rocket_bundle.json, ifixit_158506.pdf (optional proof), pages/) · <task_id>/bundle.json
  perception/       (C)  ghostbuild_perception/{capture,aruco,rectify,classify,fit,temporal,calibrate,hands,record}.py
                         hands_helper/ (optional Swift Apple Vision CLI) · camera.json · calib.json · tests/fixtures/
  g2/               (B)  app.json · index.html · src/{main,bridge-queue,ws-ladder,render,minimap,input,menu,storage,phone-page}.ts
  twin/             (B)  2D supervisor page (served at /twin?mode=2d) · (A) W4-lite three.js only if spatial dies early
  spatial/          (A)  Xcode project: ARView, base lock, PoseFusion, sender/recorder, twin v2 receiver, 7 MUST features · Tests/
  testbed/          rocket/{rocket.io,rocket.ldr,instructions.pdf,golden_target.json} · rover/{rover.io,rover.mpd,component_frames.json,*.usdz,cards/,service_sheet.pdf} · markers.pdf · defect-card.pdf
  scenarios/        (D)  demo.yaml · premature.yaml · deviation.yaml · rover_*.yaml
  integrations/     (Devin → B) sentry_bridge/ · fetch_agent/   # never imported by anything else
  eval/             (D/A) configs/ · harness/ · RESULTS.md
  logs/                  # gitignored
  docs/                  # specs; docs/sentry_findings.md (B)
```

## 4. Even G2 work — use the official Claude Code integration
```
/plugin marketplace add even-realities/everything-evenhub
/plugin install everything-evenhub@everything-evenhub
```
(The docs show `/plugin install everything-evenhub`; use it if the README form fails.)

| Need | Skill |
|---|---|
| Scaffold | `template` (`minimal`) |
| Containers/lifecycle | `glasses-ui` |
| Input, exit, contextual menu | `handle-input` |
| Storage (mic only if P2 voice ships) | `device-features` |
| Simulator | `test-with-simulator`, `simulator-automation` |
| API lookup | `sdk-reference` |
| Fit text | `font-measurement` |
| Design | `design-guidelines` |
| Pack | `build-and-deploy`, `cli-reference` |
| **Don't use** | `background-state` (its APIs aren't in SDK 0.0.16) |

**Rules:**
- Skills on `main` target SDK 0.0.12. For `textColor`, the contextual menu and lifecycle, **hub.evenrealities.com/docs wins** (pages: display, device-apis, contextual-menu, page-lifecycle, networking).
- SDK `@evenrealities/even_hub_sdk@0.0.16` (Even App ≥ 2.2.10) [V].
- `CLICK_EVENT=0` can arrive `undefined`: copy the asr template's `eventTypeOf()`. Check `DOUBLE_CLICK_EVENT` before click. Root double-tap → `shutDownPageContainer(1)`.
- `createStartUpPageContainer` creates **4** containers.

## 5. Dependencies (pin in lockfiles)
| Area | Package | Notes |
|---|---|---|
| Python | python 3.11 via `uv` | |
| core | `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `websockets`, `pyyaml`, `orjson`, `pytest` | (`anthropic` only in `knowledge/`; Deepgram only if P2 voice ships) |
| perception | `opencv-contrib-python==4.14.0.94` [V on PyPI], `numpy`, `mediapipe` **[verify arm64 wheel]** | Swift `hands_helper` only if mediapipe fails |
| knowledge | `pymupdf` (AGPL-3.0), `anthropic` | Studio LDraw export **[verify `0 STEP`]**; LeoCAD fallback |
| spatial | Xcode 27, iOS 27 device, RealityKit/ARKit; Create ML CLI on the trainer Mac | **[verify]** list in §16 |
| twin (2D; W4-lite only if needed) | `vite`, `typescript` (+ `three` / `LDrawLoader` **[verify path]** for W4-lite) | |
| g2 | `@evenrealities/even_hub_sdk@0.0.16`, `vite`, `typescript`; global `@evenrealities/evenhub-cli`, `@evenrealities/evenhub-simulator` | |
| integrations | `sentry-sdk>=2.35.0` (Logs) **[verify explicit span timestamps]**; `uagents==0.25.5` + `chat_protocol_spec` | separate `uv` projects; never imported by core |
| contracts | `json-schema-to-typescript` | |

**Claude API facts (from the bundled claude-api skill, cached 2026-10-06):**
- **Models:** `claude-opus-5-5` (extraction). Never append date suffixes. (`claude-haiku-5-5` only for P2 voice intent.)
- **Structured outputs:** `output_config: {format: {type: "json_schema", schema}}`. Schemas must be flat, set `additionalProperties:false`, and use no recursion.
- **Forced `tool_choice` any/tool returns 400** on Opus 5.5 / Sonnet 5.5. Use structured outputs.
- **No assistant prefill.**
- **Opus 5.5 thinking can't be disabled.** Effort defaults to `medium`; set it explicitly (`low` for extraction speed; test quality).
- **Citations:** `search_result` content blocks with `citations: {enabled: true}` → `search_result_location`. **Incompatible with `output_config.format`.**
- **PDF native citations** need extractable text, which diagram pages lack. That is why we synthesise evidence text.
- **Prompt caching:** `cache_control: {type: "ephemeral"}`.
- Use the official `anthropic` Python SDK only, with typed errors. Read `python/claude-api/README.md` in the claude-api skill before writing any call.

## 6. Commands (Makefile)
| Command | Does |
|---|---|
| `make setup` | `uv sync` (core, perception, knowledge, adapters); `npm ci` in g2/, twin/, contracts/ts |
| `make contracts` | export JSON Schema + TS; validate every example incl. spatial fixtures |
| `make core` / `make core-mock` | core :8787 / with `--mock-vision scenarios/demo.yaml --bundle knowledge/fixtures/rocket_bundle.json` |
| `make perception` | `python -m ghostbuild_perception --camera 0 --core ws://localhost:8787/ws?role=vision [--hands]` (runs on Mac 1 next to core) |
| `make spatial-adapter` | `python -m adapters.spatial_pose --listen :8790 --core ws://localhost:8787/ws?role=vision` (Mac 1; only with `--spatial`) |
| `make compile TASK=rocket` / `TASK=rover` | `python -m knowledge.compile ...` → `knowledge/<task>-v1/` (build time) |
| `make compile-proof` | offline generality proof: `python -m knowledge.compile --pdf knowledge/fixtures/ifixit_158506.pdf --kind service_pdf --out knowledge/ifixit-158506/` (optional; no code changes allowed) |
| `make twin` | 2D supervisor (Mac 2 opens `http://<mac1>:8787/twin?mode=2d`) |
| `make g2-dev` / `g2-sim` | Vite :5173 (host true) / `evenhub-simulator -g http://localhost:5173` |
| `make g2-qr` | `evenhub qr --url "http://$(ipconfig getifaddr en0):5173"` |
| `make g2-pack` | `npm run build && evenhub pack app.json dist -o ghostbuild.ehpk --sdk-ver 0.0.16 -c` |
| `make demo` | core + perception (Mac 1) with the gated-in flags from `demo.flags` |
| `make sentry-bridge` | `cd integrations/sentry_bridge && uv run python -m sentry_bridge` (Mac 1, `nice -n 19`; needs `SENTRY_DSN`) |
| `make fetch-agent` | `cd integrations/fetch_agent && uv run python -m fetch_agent` (**B's laptop**; requires `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`; `GB_AGENT_ARMED=0` unless demoing) |
| `make test` | core-test, perception-test, knowledge-test, contracts-test, adapter-test, g2/twin typecheck + vitest, `lint-generic` (grep rule §2), `lint-arkit` (§16 grep rule) |
| `make eval-*` | 10_EVAL_PLAN |

## 7. Tests that must exist (demo-critical)
1. **Planner:** golden cases incl. **premature cap**, LIFT-first, obstruction, out-of-order acceptance; BFS optimality on ≤ 2-defect states; never acts on `unknown` except the inspect action; tap never changes the world; rocket HUD snapshots byte-identical with `--spatial` on/off.
2. **Arbiter:** priority and TTL; one writer; ≤ 4 Hz; glyph/length limits.
3. **Answers:** golden output for every intent and menu items 1–5 on `scenarios/*` snapshots; evidence tags only from node evidence.
4. **Knowledge:** compiled rocket graph == `golden_target.json`; validator rejects cycles and missing evidence.
5. **Perception:** fixtures for each defect and hands-over-board; `--no-learned` output byte-identical to P0 on recorded fixtures.
6. **Spatial adapter:** 18 v3 §3.4 tests T1–T14; §3.3 invariants incl. the 10,000-sample fuzz; `params.yaml` load-time invariants; replay over A's recordings.
7. **Spatial app (Swift):** transform tests from `spatial_transforms.json` (cases 1–7); serialisation row-major.
8. **Teardown:** `access_path` for every component, absent blockers skipped, deterministic, acyclic.
9. **G2:** simulator automation run of `?mock=1` (screenshots per mode); menu items 1–5 → `g2_input`; double-tap exit.
10. **Contracts:** examples validate in Python and TS.
11. **Integrations:** each `integrations/*` has `pytest -q` green against `core --mock-vision`; the Fetch agent fails fast without `GB_CORE_URL`.

## 8. Gates and cut rules (summary; full table 03 §Gates, clocks 21)
**Rule:** at each clock, anything not demonstrably green is red; the action fires automatically; a killed component is turned off by flag and **never reopened**. Agents must not spend more than the gate budget on any single dependency.

| Clock | Gate |
|---|---|
| Fri | S0 tooling · F0 Fetch example |
| Sat 12:45 | **contract lock (one lock, all schemas + fixtures)** |
| 13:45 | S1 motor training ETA ≤ 22:45 |
| 15:00 | G0 transport |
| 16:00 | V2 hands |
| 17:00 | K1 extraction |
| 17:30 | S2 kill (app on device) |
| 18:15 | S3 rig |
| 19:30 | S4 cards · M3 |
| **20:00** | **G2 perception** |
| 21:00 / 21:30 | G3 compile / D valve · M10 |
| 22:45 | motor training done |
| 23:00 | Sentry live trace · W4-lite (if built) |
| **23:30** | **S5 motor · CORE-FULL** |
| Sun 00:30 | S6 replay · F1 |
| **00:45** | **core merge cutoff; no schema changes after** |
| **02:00** | **P0 freeze** |
| 02:45 | footage secured |
| 03:30 / 04:15 | S7 / S8 |
| **04:00** | **product feature freeze** (isolated Fetch client exception only) |
| 06:45 / 07:45 / 08:15 | Even Beta QA / F2 / F3 |
| 08:30 | video (GENERAL export) · eval · Sentry entry condition · generality proof |
| 10:30 | submissions complete |
| 11:00 | lead + final Beta |

## 9. Proposed always-on `CLAUDE.md`
```markdown
# GhostBuild — project rules
24 h hackathon. Live-demo reliability > features. Read docs/20_FINAL_IMPLEMENTATION_BIBLE.md, docs/15_SONNET_HANDOFF.md, docs/05_CONTRACTS.md, then only your vertical's doc.
- Scope: only P0/P1 items in docs/03_MVP_SCOPE.md; P2 only after its gate; never build CUT items.
- Physical state is committed only by the P0 grid path (rocket) or adapters/spatial_pose (rover). No AI model commits state. Unknown state never yields a confident physical instruction.
- core/ and contracts/ are domain-agnostic: no LEGO terms (make lint-generic).
- Contracts: one lock Sat 12:45; shared-schema changes need D + every consuming owner; none after Sun 00:45. Run `make contracts`.
- One HUD writer: core/hud_arbiter.py. Answers are pure functions of an immutable snapshot. A G2 tap is a recheck, never a commit.
- Spatial: separate process, flag-guarded core additions, rocket snapshots byte-identical; never .resetTracking/.removeExistingAnchors after the first run.
- Sponsor code lives only in integrations/; never import it; never touch core/contracts/perception/g2/spatial from there.
- Honesty: label sources (TRACKED, MEASURED LIVE, CAD, TARGET, DETERMINISTIC, AI-EXTRACTED, AUTHORED DEMO METADATA, MANUAL EVIDENCE + origin, LAST SEEN, MANUAL OVERRIDE).
- Even G2: verify every SDK call via the everything-evenhub skills + hub.evenrealities.com/docs (SDK 0.0.16). No API keys in g2/.
- Claude API: official `anthropic` SDK + the claude-api skill; claude-opus-5-5; structured outputs, not forced tool_choice.
- `make test` before merging; every feature behind its flag. P0 freeze 02:00; product feature freeze 04:00.
```

## 10. Where context lives
| Location | Contents |
|---|---|
| `CLAUDE.md` | §9 only |
| `g2/CLAUDE.md` | 08 §0–§9b digest; QA checklist pointer; skills list |
| `perception/CLAUDE.md` | 06 pipeline + abstention + fixture commands |
| `core/CLAUDE.md` | 07 priority rules, premature rule, inspect action, arbiter, answer rules, §S tiers, test list |
| `adapters/spatial_pose/CLAUDE.md` | 18 v3 §3 (pseudocode, state table, invariants, tests) + §6.4 thresholds |
| `spatial/CLAUDE.md` | 18 v2 §5 frames/formulas, §9.1 MUST list; 18 v3 §5 base lock + grep rule |
| `knowledge/CLAUDE.md` | 07 §K pipeline + structured-output schema rules + validator |
| `integrations/*/CLAUDE.md` | the matching 19 appendix brief, verbatim |
| `docs/` | full specs, read on demand; never pasted into CLAUDE.md |

## 11. Fallback flags (not code forks)
| Flag | Effect |
|---|---|
| `core --mock-vision <yaml>` | Scripted observations (`source: mock`) |
| `core --replay <jsonl>` | Replay (`replay`) |
| `core --bundle <file>` | Choose a bundle (fixture / compiled / golden) |
| `core --spatial` | Enable CORE-MIN/CORE-FULL paths and `/control/goal` (off → 404) |
| `perception --no-learned` | Pure P0 |
| `perception --tags` | Plan B AprilTag part ID |
| `twin ?mode=2d` | 2D supervisor |
| `g2 ?mock=1` | Canned HUD frames |
| `g2 VITE_TEXT_ONLY=1` | No minimap |
| `GB_AGENT_ARMED=0` | Fetch agent cannot mutate (default) |
| Operator `O` | Manual override (bannered) |

## 12. External resources (fetch before the event; cache in repo or `~/ghostbuild-cache`)
- LDraw parts library zip **[verify URL]**; three.js npm package (W4-lite only).
- A saved PDF print of iFixit guide 158506 (optional offline proof; CC BY-NC-SA attribution).
- Even docs (`hub.evenrealities.com/docs`) and templates (`npx degit even-realities/evenhub-templates/minimal g2`) [V].
- Mediapipe hand model `.task` **[verify]**.
- Fetch ASI-compatible uAgents example; Sentry Python Logs/Tracing docs (19 Sources).

## 13. Hardware assumptions
- **Mac 1** (perception + core + spatial adapter + Sentry bridge): M-series, USB webcam on a clamp arm ~40 cm overhead, LED panel; spare Hardware Lab Logitech webcam.
- **Mac 2:** phone mirror (QuickTime) + 2D supervisor + recording.
- **A's Mac:** Xcode 27 + device builds. **Trainer Mac:** borrowed or D's laptop (never Mac 1 or A's Mac).
- **B's laptop:** G2 dev; runs the Fetch agent.
- **iPhone 1:** Even app + Beta build (auto-lock off during judging), also the hotspot if there's no travel router. **Spatial iPhone:** iOS 27, on a gooseneck.
- **Even G2 loaner** (one device: only B handles it; everyone else uses the simulator).

## 14. Authoritative documents (priority)
1. Official Even / Apple / Fetch / Sentry docs (platform behaviour).
2. `20_FINAL_IMPLEMENTATION_BIBLE.md` (operational summary) and 05_CONTRACTS (interfaces).
3. `18_SPATIAL_TWIN_PASS_V3.md` (spatial; V2 sections it keeps in force) and `19_SPONSOR_AND_TRACK_STRATEGY.md` with its final amendments (sponsors).
4. Vertical spec: 06 perception / 07 core-knowledge-answers / 08 G2 / 09 supervisor + phone twin.
5. 03_MVP_SCOPE (scope + gates) and 21_HACKATHON_CHECKLIST (clocks).
6. 17_AMBITION_PASS and 16_DECISIONS (why).

If they conflict, ask Person D.

## 15. Definition of done (per PR)
- Tests pass and the feature works against mocks; behind its flag.
- No new dependency without the owner's OK; no scope beyond 03; no secrets committed.
- Structured JSON logs; honest source labels.
- Sponsor PRs touch only their own `integrations/*` directory.

## 16. [verify] at hack time (spatial)
1. After phase 2, the `gb_base` anchor is still in `frame.anchors` with the same identifier (documented [V]; confirm at S2; fallback B2-continuous).
2. Image detection + `trackingObjects` coexist at ≥ 30 fps.
3. The Create ML **Upright** viewing-angle flag name (`xcrun createml objecttracker -h`).
4. USD up-axis handling in RealityKit (gear on the correct side, motor upright).
5. Image-anchor axes (axis gizmo at S2).
6. Xcode 27 macOS floor.
7. **Grep rule:** `.resetTracking` and `.removeExistingAnchors` may appear only in the first-run path (`make lint-arkit`).

## 17. Devin assignments (19 Appendices A and B are the briefs)
Every Devin task has: strict directory scope (`integrations/sentry_bridge/` or `integrations/fetch_agent/` only); exact interfaces (05 §12–13 and the 18 v3 §4.1 lock); a test command; a definition of done; and a no-human-rescue kill rule. If a Devin PR is red at its gate, that sponsor feature dies; no core team member is moved onto rescue (only A, after a spatial kill). The Fetch agent's `GB_CORE_URL` is required with no localhost default.
