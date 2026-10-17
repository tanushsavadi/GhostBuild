# 07 — World Model, Diff, Replanner, Knowledge Compiler & Answer Engine

**Owner:** Person D (§1–§13, §K, §A). Person C owns the voice server (§V). **Inputs:** `world` (stable), the `KnowledgeBundle` (task graph + target + evidence), and the component library. **Outputs:** `diff`, `plan`, `turn`, and `hud` via the arbiter (§H). Planner, diff and answers are pure functions over an immutable snapshot, with no I/O; 100% unit-testable.

**Ambition-pass changes:**
- Targets and `requires` now come from the compiled task graph (§K).
- New diff kinds `premature` and `unconfirmed`.
- New answer engine (§A), voice server (§V) and HUD arbiter (§H).
- Core code stays domain-agnostic. LEGO phrasing and grid geometry live in `adapters/lego_grid`.

> **Final reconciliation (2026-10-16).**
> - **Spatial additions (§S below)** are additive and flag-guarded: **CORE-MIN** (discrete-pose diff, `source: spatial`, `twin` v2 emit) and **CORE-FULL** (`core/teardown.py`, the inspect action, `requires_goal`, `/control/goal`). CORE-FULL must be unit-green by **23:30** or D merges CORE-MIN only. Spatial core merge cutoff **00:45**.
> - The spatial **classifier** (18 v3 §3.1) is the spec of `adapters/spatial_pose`, which lives **outside** core and emits ordinary `observation`s.
> - Menu item 5 is `WHAT NEXT?` and routes to the existing `WHAT_NEXT` intent. REPEAT is voice-only.
> - Voice (§V) is **P2 opportunistic**, never scheduled. The iFixit JSON / guided path in §K is **superseded** by the optional offline generality proof (18 v3 §11).
> - **What "generic" means:** the planner skeleton and data model are domain-agnostic; covering, sites, rotation equivalence, blockers and phrasing are adapter-supplied (05 design rule). Do not claim domain-free physical reasoning.

## Objective
From **any** observed state, compute what is wrong and the next valid physical action, recomputed from scratch on every committed state. That gives genuine replanning (and order independence) without a fixed step sequence.

## Non-goals
A*, PDDL, constraint solvers, learned policies, multi-user, undo history, partial-credit scoring.

## Why not A*/constraint search (decision)
The action space is tiny, actions have uniform cost, and the only coupling is support/covering (layer 2 over layer 1). A deterministic priority planner with a dependency check achieves the obvious lower bound on number of actions for this domain. We **verify** that with a brute-force BFS over all 1- and 2-defect states of the demo target in tests (§8), so the "optimal" claim is checked, not asserted.

## 1. Correctness of a part
Target part `t` vs world part `w`:
- `correct` ⇔ `w.status = present` ∧ `w.anchor = t.anchor` ∧ rotation matches (`oriented`: equal; non-oriented 2×2: any; non-oriented 2×4: equal mod 180). When `Pose.discrete` is present (spatial), `correct` ⇔ `present` ∧ `site = target.site` ∧ `rot_cw = target.rot_cw`.
- `unknown` world parts are **never** classified; they block planning (§4 step 0).
- **Premature rule:** a node whose predicate holds but whose `requires` are not all satisfied is **`premature`**, not satisfied. Example: the cap is back on while green is missing underneath. It counts toward `distance`, and its fix is to undo it (`LIFT`).

## 2. Diff (`diff(world, target) → Diff`)
For each target part:
- absent → `missing`
- present, anchor ≠ target → `misplaced` (carry `current` and `target`)
- present, anchor = target, rot wrong → `misoriented`
For each present world part not in target (library parts not used by this target) → `extra`.
For each unknown region → `unknown`.
For each node satisfied out of dependency order → `premature` (see §1).
For each `user_confirm` node not yet confirmed → `unconfirmed` (reserved; guided mode is cut, so no bundle has such nodes).
Annotate `blocked` on any non-correct layer-1 part whose footprint is overlapped by a **present** layer-2 part (rocket covering rule, adapter-supplied). When the bundle has `relations`, also annotate `blocked` on any non-correct component with a present `blocked_by` entry (rover).
`distance = (# target parts not correct) + (# extra) + (# unknown regions)`.

## 3. Obstruction
A target footprint is **obstructed** if any present part (other than the one being placed) occupies one of its cells at the same layer. The obstructing part's own fix (remove/move) is ordered first.

## 4. Planner (`plan(world, target, prev_plan) → Plan`)
0. If the bundle has `requires_goal` and no goal is set → status `awaiting_goal`, HUD idle. If `occluded` → status `occluded`, keep previous head action (HUD dims). If `board_visible: false` (incl. spatial NO_COMMIT) → status `no_board`. If any `unknown` part/region → **never plan through unknowns**:
   - spatial `unknown(reason=hidden, occluder=X)` with X committed present and stable → head = the **inspect action** `LIFT X` / `TO CHECK <c>` (verb `LIFT`, reason `inspect`), status `in_progress`. It is the only action allowed while anything is unknown (reversible, needed for verification);
   - `unknown(ambiguous_seat|ambiguous_yaw)` → `WAIT` `ADJUST <C>` / `SEAT IT SQUARE`; rocket unknown part → `WAIT` `ADJUST BRICK` / `PRESS IT FLAT`; unknown region → `CLEAR` `CLEAR UNKNOWN ITEM`; `unknown(lost)` → `WAIT` `SHOW <C>` / `TO THE CAMERA`; status `uncertain`;
   - `out_of_view` / `never_seen` with no inspect action → status `uncertain`, no physical instruction (HUD `CHECKING`).
1. If `distance = 0` → status `verified`, head = `DONE`.
2. Generate candidates:
   - `LIFT c` for every present layer-2 part `c` that covers a non-correct layer-1 part, **or that is `premature`**. Lifting makes `c` missing; it is re-placed later automatically.
   - `LIFT b` / `REMOVE b` for a present `blocked_by` entry `b` of a non-correct component (rover relations).
   - ~~`CONFIRM n`~~ reserved for guided mode, which is cut; never generated.
   - `REMOVE x` for every `extra` (not blocked).
   - `MOVE p → target` for every `misplaced` (not blocked, target footprint not obstructed).
   - `ROTATE p` for every `misoriented` (not blocked).
   - `PLACE p` for every `missing` whose `requires` are all correct and footprint not obstructed.
3. Priority: `LIFT` > `REMOVE` > `MOVE` > `ROTATE` > `PLACE` (> `CONFIRM`, reserved and never generated); tie-break by layer (1 first), or by CAD top-z descending for `blocked_by` chains, then by distance of the target from the user (nearest first), then `component_id`.
4. **Stickiness:** if `prev_plan.head` is still a valid candidate, keep it as head (prevents instruction flapping when an unrelated part changes).
5. Full plan: repeatedly apply the head action to a simulated copy of the world and re-plan until `DONE` or 20 steps. This gives the ordered list for the twin and `status: 6/9`.
6. Termination argument (for judges): every action strictly decreases the lexicographic potential `(# covered non-correct parts, distance)`; `LIFT` decreases the first term, every other action decreases the second; so the plan always reaches the target in finitely many steps if actions succeed.

## 5. Replanning & deviation classification (the demo's key moment)
On each new committed world `W'` (previous `W`, previous head action `a`):
- `W' = apply(a, W)` → `progress` → HUD briefly shows `●` then the next action.
- `distance(W') < distance(W)` but `W' ≠ apply(a, W)` → **`progress_out_of_order`** → accepted silently; twin log: "Out-of-order progress accepted". (A step-tracker would flag this as an error.)
- New `premature` item (a dependency violated) → **`deviation`** with the HUD alert `X CAP TOO EARLY` / `LIFT IT` (the demo's centrepiece).
- `distance(W') ≥ distance(W)` and `W' ≠ W` → **`deviation`** → `alert: true`, HUD `X WRONG SPOT` / `X NOT THAT ONE` for 3 s, then the corrective head action. Twin log: "<part> placed 2 left of target — replanned".
- Change that touches only unknown regions → `external_change`.
- **A G2 tap is a recheck request, not an observation.** It re-runs `plan` + `compose_hud` on the latest committed world and re-sends the HUD. It never forces a commit and never bypasses the vision/adapter temporal-stability vote.

## 6. HUD composer (`compose(plan, world, diff) → hud`)
Text lexicon (≤ 20 / ≤ 28 chars):
| Verb | line1 | line2 |
|---|---|---|
| LIFT | `LIFT BLACK 2x4` | `OFF THE TOP FIRST` |
| REMOVE | `REMOVE GREEN 2x2` | `NOT IN THIS BUILD` |
| MOVE | `MOVE BLUE 2x2` | `1 RIGHT · 2 TOWARD YOU` |
| ROTATE | `TURN RED 2x4` | `DOT AWAY · 180°` (or `QUARTER TURN →`) |
| PLACE | `ADD YELLOW 2x4` | `DOT AWAY · SEE MAP` |
| CLEAR | `CLEAR UNKNOWN ITEM` (no VLM label; cut) | `FROM THE BOARD` |
| WAIT (unknown part) | `ADJUST BRICK` | `PRESS IT FLAT` |
| DONE | `● VERIFIED` | `MATCHES TARGET` |
| (deviation prefix) | `X WRONG SPOT` | corrective line |
| (premature) | `X CAP TOO EARLY` | `LIFT IT · GREEN FIRST` |
| PLACE (a part removed earlier this session) | `PUT BACK BLACK 2x4` / `PUT BACK YELLOW BAR` / `PUT BACK DECK` | — |
| *Rover (18 v3):* inspect | `LIFT DECK` | `TO CHECK MOTOR` |
| *Rover:* REMOVE blocker | `REMOVE YELLOW BAR` | `IT LOCKS THE MOTOR` |
| *Rover:* ROTATE | `TURN MOTOR 90° →` | `GEAR TO THE RIGHT` (the gear is on +X at the target pose = the judge's right; never give directions from the mirror) |
| *Rover:* premature | `X DECK TOO EARLY` | `LIFT IT · BAR FIRST` |
| *Rover:* AMBIGUOUS / LOST | `ADJUST MOTOR` / `SHOW MOTOR` | `SEAT IT SQUARE` / `TO THE CAMERA` |
Direction words are in the user's frame (§05.1). Glyph set limited to the Even font (08 §4); the composer has a whitelist and a fallback. `✓` (U+2713) is **not confirmed** in the firmware font — the composer emits `●` (U+25CF, confirmed) unless the hardware glyph test (08 §4) shows `✓` renders. `→ · ° ×` are confirmed.

Map: `board[r][c]` 0/1/2 + `highlight` = target footprint (PLACE/MOVE/ROTATE) or current footprint (REMOVE/LIFT).

Emission rules (Quiet by Design): send `hud` **only when** head action, mode, alert, or progress changes. While `occluded`: same text, `brightness 2`. After `DONE` for 8 s → `mode: idle` (blank except a faint `●`).

## 7. API
```python
def diff(world: World, target: Target, lib: Library) -> Diff
def plan(world: World, target: Target, lib: Library, prev: Plan | None) -> Plan
def classify_event(prev_world: World, prev_plan: Plan, new_world: World) -> Event
def compose_hud(plan: Plan, world: World, diff: Diff, last_hud: Hud | None) -> Hud | None  # None = no change
def access_path(goal: str, bundle: Bundle, world: World) -> list[str]   # core/teardown.py (CORE-FULL)
```

## 8. Tests (`make core-test`, TDD from minute one)
- Golden cases: each defect type alone; all three demo defects; cap covering a misoriented brick → `LIFT` first; obstruction (misplaced part sitting on another's target).
- Deviation cases: correct action; out-of-order correct action; wrong placement; removal of a correct part.
- **BFS optimality check:** for the demo target, enumerate all states reachable by ≤ 2 defect operations; assert planner plan length == BFS shortest path length.
- Property: planner always terminates ≤ 20 steps; never emits an action on an `unknown` part.
- Composer: every string ≤ limits and only whitelisted glyphs.
- Tap: a `g2_input: tap` never changes `world` and never produces a commit.
- Menu: golden answers for items 1–5 (item 5 = WHAT_NEXT) on scenario snapshots.
- **Spatial (only with `--spatial` / a bundle with `relations`):** rocket HUD snapshots byte-identical with the flag on and off; 18 v3 §3.3 invariants (no ROTATE/MOVE/PLACE on SETTLING/HOLD/AMBIGUOUS/LOST/OUT_OF_VIEW/NEVER_SEEN/HIDDEN_UNVERIFIED; only the inspect action while unknown); `access_path` for every component, absent blockers skipped, determinism under input order, no cycles; `requires_goal` → `awaiting_goal`.

## 9. Mocked path
`core --mock-vision scenarios/demo.yaml` replays scripted `observation`s (defects → judge fixes → judge mistake → fix → verified) with timings. This is the integration test for G2 and twin from hour 1.

## 10. Definition of done
All tests green; `scenarios/demo.yaml` produces exactly the expected HUD sequence (snapshot test); p99 planner time < 5 ms.

## 11. Risks
Flapping instructions (stickiness + vision hysteresis); ambiguous "user frame" directions (pilot with teammates; fall back to map-only line2 `SEE MAP`); over-eager deviation alerts while a judge is mid-action (only classify on committed states after the quiet period).


---

## §S Spatial core additions (Person D; additive, flag-guarded; 18 v2 §10.4 as amended by 18 v3)

| Tier | Contents | Clock |
|---|---|---|
| **CORE-MIN** | diff over `Pose.discrete`; accept `observation.source: spatial` and the spatial component fields (05 §3); emit `twin` v2 (05 §11) | merged by 00:45 |
| **CORE-FULL** | `core/teardown.py` (`access_path` = DFS over present `blocked_by`, sorted by CAD top-z desc; `reassembly` = reverse minus goal; explode offsets from CAD bbox); the inspect action (§4 step 0); `blocked_by` from relations (§2); `requires_goal` / `awaiting_goal`; `POST /control/goal` → `{goal, path}` | unit-green by **23:30**, else CORE-MIN only; merged by 00:45 |

Goal semantics: `/control/goal {c_motor}` = **access, inspect and correct the installation**. The plan then runs from world state as usual: teardown from the inspect/blocked rules, the fix from the diff (a `ROTATE` when the motor is measured 90° off). Never "replace", never a functional claim.

## §K Knowledge compiler (`knowledge/`, Person D) — build time, cached, never called at demo runtime

**Objective:** turn documentation into a validated `KnowledgeBundle` (05 §2). **Structure comes from CAD; words come from the manual.**

**Inputs:**
- `testbed/rocket/rocket.ldr` (Studio → File > Export As LDraw [V]; confirm `0 STEP` lines at hack time, LeoCAD/LPub3D as fallback)
- `testbed/rocket/instructions.pdf`
- `testbed/rover/service_sheet.pdf` (the team-authored one-page rover service sheet; `kind: service_pdf, origin: team_authored`)
- optional, offline only: `knowledge/fixtures/ifixit_158506.pdf` (a saved print of iFixit guide 158506; `kind: service_pdf, origin: external`; CC BY-NC-SA attribution)

**Pipeline:**
1. **LDraw parse (deterministic).**
   - Read line-type-1 records `1 <colour> x y z a b c d e f g h i <part>.dat` and `0 STEP`.
   - LDraw units [V]: 1 LDU ≈ 0.4 mm, stud pitch 20 LDU, brick height 24 LDU, −Y is up.
   - Map each part → `Component` (adapter_ref ldraw/colour/w/h) and → grid pose (anchor, rot, layer) via the adapter.
   - **Support graph:** B requires A if A is directly below B (layer difference 1) and their footprints overlap.
   - **Target** = all nodes `placed(component, pose)`, with `source: cad_derived`.
2. **PDF render.** PyMuPDF renders each page at ~2000 px long edge.
3. **LLM page extraction (REAL AI, gate K1).**
   - Claude Opus 5.5 (`claude-opus-5-5`), one request per page in parallel, structured output via `output_config.format` json_schema.
   - Output: `StepRecord {step_no, page, parts:[{shape, colour, qty}], placement_text, panel_bbox}`.
   - Schema rules [V]: flat, `additionalProperties:false`, no recursion. Forced `tool_choice` is a 400 on Opus 5.5; use structured outputs.
4. **Validate (deterministic):**
   - schema ✓, acyclic ✓, every node has a verifier the adapter supports ✓, every node has ≥ 1 evidence record ✓
   - **per-step part multiset: LLM vs LDraw** → `llm_vs_cad_step_match: "n/m"`
   - Mismatched steps use CAD-generated text for their evidence (`modality: "cad_generated"`), and the UI says so.
5. **Evidence records:** one per step: `{doc, page, section: "Step k", text: placement_text, modality}`.
6. **Human review:** D opens `knowledge/<task>/review.html` (static JSON viewer), checks, and stamps `reviewed_by`.
7. **Write** `knowledge/<task>/bundle.json`. It is committed to git; CI diffs the task graph against `testbed/rocket/golden_target.json` (the hand-authored P0 target), which must match.

**iFixit JSON path — SUPERSEDED (final).** Not built. The generality proof instead runs the saved guide PDF through the same `service_pdf` extraction and validator, offline, at 07:45–08:30 (18 v3 §11); output `knowledge/ifixit-158506/bundle.json`, shown only in Devpost/README/one video frame as "compiled, not executed". It is dropped if K1 fired, the rover sheet didn't compile, it isn't validated by 08:30, or it needs any code change. History of the old plan:
- Map `steps[].lines[].text_raw` → Steps, `tools`, `parts`, and evidence `{doc: ifixit_158506, section: "Step k"}`.
- Default edges follow the written order.
- Opus may propose only `reorderable` pairs and `warnings`, and each proposal must quote its justifying line. The validator rejects proposals without a matching quote.
- All nodes use `verifier: user_confirm` → `adapters/guided`.
- Display the CC BY-NC-SA attribution.

**Gate K1 (Sat 17:00):** part multiset correct on ≥ 80% of steps; 100% schema-valid and acyclic. **Fail:** evidence for the rocket **and** the rover sheet comes from CAD-generated descriptions + hand-typed page numbers, labelled `authored`; extraction code is frozen and not debugged; the generality proof is cancelled. The task graph is unaffected because it always comes from CAD (rover relations are authored either way).

**Gate G3 (Sat 21:00):** compiled target == golden target (unit test); every step maps to a PDF page.

**Mock path:** `knowledge/fixtures/` contains a pre-made bundle so core, twin and the answer engine never wait for the compiler.

## §A Answer engine (`core/answers.py`, Person D) — deterministic, cited

**Input:** `{intent, slots}` + immutable snapshot (world, diff, plan, task graph, evidence, turn history). **Output:** `turn` (05 §9) with ≤ 2 answer lines + an evidence tag.

| Intent | Rendered from | Example (line1 / line2) |
|---|---|---|
| WHY (the current head action, or `slots.component`) | `plan.actions[0].why` + node evidence | `RED UNDER IT IS FLIPPED` / `[MANUAL STEP 6]` |
| WHERE (`component`) | target pose vs current → relative direction (adapter) | `2 LEFT OF RED` / `SEE MAP` |
| CAN_I (`action`, `component`) | simulate the action on a snapshot copy → is it valid now? If not, name the first unmet `requires` | `NOT YET` / `GREEN FIRST` |
| WHAT_NEXT (menu item 5) | `plan.actions[0].hud` | (same as HUD) |
| WHAT_DONE | satisfied nodes + count | `6 OF 9 DONE` / `NEXT: ADD GREEN` |
| REPEAT (voice only, P2) | last answer | — |
| MANUAL_SAYS (P2, voice only) | Haiku 5.5 over evidence as `search_result` blocks, citations enabled; answer ≤ 90 chars; no citation → `MANUAL DOESN'T SAY` | `USE 2 STUD GAP` / `[MANUAL P7]` |
| UNKNOWN | — | `? SAY AGAIN` |

**Rules:**
- Answers never change state.
- Evidence tags come only from node evidence IDs. They are never generated text.
- If the snapshot is `uncertain`/`occluded`, answers are prefixed `CHECKING —`.

- Rover example: WHY on `REMOVE YELLOW BAR` → `BAR LOCKS MOTOR` / `[SERVICE P.2]`, citation chip `TEAM-AUTHORED SERVICE SHEET` (or `AI-EXTRACTED · VALIDATED` if K1 passed).
- **21:30 D valve:** if G3, the rover bundle or WHY-on-fixture is red, the engine is limited to WHY, WHAT_NEXT, CAN_I, WHAT_DONE and menu item 2 (`WHERE`) is hidden.

**Tests:** golden answers for every intent on the demo scenario snapshots.

## §V Voice server — **P2 OPPORTUNISTIC, NEVER SCHEDULED** (18 v3 §8). Kept as the documented architecture only.
It may start only if every gate up to that clock is green and the person starting it has no assigned task in that slot; it must pass G1 and G5 and be merged flag-off by default before 00:45. Otherwise it is dropped. C never starts it before G2 perception is green.

**Flow:**
1. `ptt start` → open or reuse a Deepgram Flux WS: `wss://api.deepgram.com/v2/listen?model=flux-general-en&encoding=linear16&sample_rate=16000` [V], with `eot_threshold` high so turns are manual. Verify parameter names and keyterm prompting (LEGO, brick, cap, green, red, flipped) at hack time.
2. Re-chunk PCM to 80 ms.
3. `ptt end` → `{"type":"ForceEndTurn"}` [V] → final transcript.
4. **Fast path:** regex for `why|where|can i|what next|what('s| is) done|repeat`.
5. Otherwise **Claude Haiku 5.5** (`claude-haiku-5-5`): structured output `{intent, component?, action?, confidence}`, with the system prompt + component list under a cache breakpoint. Thinking: leave adaptive at effort `low` (verify latency); disabled is allowed only at effort ≤ high.
6. confidence < 0.6 → `UNKNOWN`. Then → answer engine → arbiter.

**Keys:** stay on the laptop.

**Gate G5 (Sat 23:30):** 20 hall utterances from the G2 mic, ≥ 17 correct intents, p90 release→HUD < 2.0 s. **Fail:** voice leaves the script; the menu remains.

## §H HUD arbiter (`core/hud_arbiter.py`, Person D) — the only writer of `hud`
- **Priority:** `alert` (deviation/premature) > `verified` > `answer` (TTL 8 s, dismissed by a tap) > `instruct` > `hold`/`idle`.
- (P2, only if voice ships) While voice is `listening`/`thinking`: suppress non-critical `instruct` changes (BLE contention). Show the voice glyph in `status`.
- Emits only on change, ≤ 4 Hz. Composer limits are enforced here.
