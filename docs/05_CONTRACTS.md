# 05 — Shared Contracts — LOCK SAT 12:45 — ONE LOCK

**Owner:** Person D (contracts owner).
**Source of truth:** `contracts/models.py` (pydantic v2). `make contracts` exports JSON Schema → `contracts/schema/*.json` → TS types `contracts/ts/index.ts` (json-schema-to-typescript). Canonical payloads live in `contracts/examples/*.json` and are validated by Python and TS tests.

> **Final reconciliation (2026-10-16).** One lock at **Sat 12:45** covering every core **and** spatial schema and fixture (18 v3 §4). There is no 12:30 lock and no later spatial contract slot. If the lock is not complete at 12:45, the whole lock moves and D announces the new time; **the lock is never partial**; nobody codes against a partial schema. No consumer needs a contract before 13:15.
>
> **AFTER CONTRACT LOCK, ADDITIVE IMPLEMENTATION MAY CHANGE; SHARED SCHEMA MAY NOT CHANGE WITHOUT D + ALL CONSUMER OWNERS APPROVING IT.**
>
> **After Sun 00:45 no contract or schema change of any kind** (core or spatial).

**May change after the lock without approval (implementation):** adapter logic and `params.yaml` thresholds; planner internals; phone and 2D UI; new recordings, scenarios and fixture *instances* that validate against the locked schema; new tests; producer `debug` fields.

**Shared schema (needs approval):** any field name, type, enum value, unit, frame, matrix order, message type, endpoint path or body, or menu ID. The approval is posted in team chat; D merges and runs `make contracts`.

| Schema | Producer | Consumers who must approve a change |
|---|---|---|
| Conventions (§1) | D | A, B, C |
| `pose_observation` (§3b) | A | C, D |
| `observation` spatial fields (§3) | C (adapter) | D |
| `twin` v2 (§11) | D | A, B |
| `/control/goal` (§12) | D | A, B |
| Bundle `relations`, `occludes`, `task_flags` (§2) | D | C |
| `spatial_transforms.json` fixture (§14) | D | A, C |
| Menu IDs (§8) | B | D |
| Endpoints used by `integrations/*` (§12–13) | D | B (integration lander) |

**Design rule — what "generic" means here.** The data model is domain-agnostic: components, predicates, verifiers, poses, observations, diffs, actions, turns. Nothing in `contracts/` or `core/` source may mention LEGO, studs, colours or part numbers (CI lint). **Action semantics are adapter-specific inputs, not generic intelligence:** what counts as "covering" (the rocket's layer-2 rule), "site" and rotation equivalence (`Pose.grid` / `Pose.discrete`), blockers and removal axes (the rover's authored `relations`), and all phrasing come from `adapters/lego_grid`, `adapters/spatial_pose` and the bundle. We claim a generic data model and planner skeleton, not domain-free physical reasoning.

Every wire message is JSON with `type`, a per-producer monotonically increasing `seq`, and `ts_ms` (producer wall clock). Audio is the only binary payload (§10, P2 only).

---

## 1. Conventions, frames & poses (lock item 1)
- **Frames.** `board` is the rocket's registered work surface; `base` is the rover's canonical frame (origin at the baseplate's near-left top corner). Both use the same axes: **X right (the user's left → right), Y away from the user, Z up.**
- **Naming rule:** `T_A_B` maps coordinates in frame B to frame A: `p_A = T_A_B · p_B`. Compose inner indices (`T_A_C = T_A_B · T_B_C`); inverse swaps them.
- **Units:** **mm on the wire; metres inside the iOS app.** Matrices are **16 floats, row-major** (`simd_float4x4` is column-major; serialise explicitly).
- **Yaw** is counter-clockwise-positive about +Z (right-hand rule). The discrete clockwise rotation is `rot_cw = (−yaw) mod 360`.
- **`Pose`** = `{ "frame": "board"|"base", "T": [16], "grid"?: {...}, "discrete"?: {...} }`. **`T` is `T_frame_component`**: the component frame's origin is the **bottom centre of the footprint on its seating plane**, and its axes equal the frame axes when the component is at rotation 0 / its target orientation.
- **LEGO grid adapter pose** (`Pose.grid`, rocket): `{ "anchor": [row, col], "rot": 0|90|180|270, "layer": 1|2 }`.
  - Row 0 is the row farthest from the user; col 0 is the user's left. The **anchor** is the footprint's min-row/min-col cell. `rot` is clockwise from above; at rot 0 the long axis runs far→near with the dot at the far end. Stud pitch 8 mm, brick height 9.6 mm, 16×16 board.
  - Let `nr × nc` be the footprint's rows × cols **after** rotation (a 2×4 is 4 × 2 at rot 0 and 180, 2 × 4 at 90 and 270). The adapter computes **`T = translate((col + nc/2)·8, (16 − row − nr/2)·8, (layer − 1)·9.6) · Rz(−rot)`** (mm). *(This replaces the earlier "translate(col·8, (15−row)·8, …)·Rz(rot), relative to the footprint centre", which mixed the anchor corner with the centre and used the wrong rotation sign.)*
- **Spatial discrete pose** (`Pose.discrete`, rover): `{ "site": "<site id>" | "zone", "rot_cw": 0|90|180|270 }`. The diff compares `discrete` when present.

## 2. Knowledge — `KnowledgeBundle` (file: `knowledge/<task_id>/bundle.json`; `GET /knowledge/<task_id>`)
Produced at build time by `knowledge/` (07 §K). Flat and ID-referenced, because structured outputs disallow recursion.

```json
{
  "type": "knowledge_bundle",
  "task_id": "rocket-v1",
  "product": { "id": "rocket-v1", "name": "GhostBuild Rocket", "model_no": null, "sources": ["doc_1", "cad_1"] },
  "documents": [
    { "id": "doc_1", "kind": "instruction_pdf", "origin": "team_authored", "uri": "testbed/rocket/instructions.pdf", "sha256": "…", "pages": 14, "license": "own" },
    { "id": "cad_1", "kind": "ldraw", "origin": "team_authored", "uri": "testbed/rocket/rocket.ldr", "sha256": "…" }
  ],
  "components": [
    { "id": "c_red24", "kind": "part", "name": "RED 2x4", "adapter_ref": { "ldraw": "3001.dat", "color": 4, "w": 2, "h": 4, "oriented": true }, "qty": 1 }
  ],
  "tools": [],
  "warnings": [],
  "steps": [
    { "id": "s_6", "order": 6, "instruction": "Add red 2x4, dot away, centre-left", "components": ["c_red24"], "evidence": ["ev_6"] }
  ],
  "task_graph": {
    "nodes": [
      { "id": "n_red24", "predicate": { "kind": "placed", "component": "c_red24", "pose": { "frame": "board", "T": ["…"], "grid": { "anchor": [3, 6], "rot": 0, "layer": 1 } } },
        "verifier": "grid_cv", "requires": [], "evidence": ["ev_6"], "source": "cad_derived", "confidence": 1.0 },
      { "id": "n_cap", "predicate": { "kind": "placed", "component": "c_black24cap", "pose": { "…": "…" } },
        "verifier": "grid_cv", "requires": ["n_red24", "n_green22"], "evidence": ["ev_9"], "source": "cad_derived", "confidence": 1.0 }
    ],
    "goal": ["n_red24", "n_cap", "…"]
  },
  "evidence": [
    { "id": "ev_6", "doc": "doc_1", "page": 7, "section": "Step 6", "bbox": [0, 0, 0, 0], "bbox_units": "pdf_pt", "modality": "diagram",
      "text": "Step 6: add one red 2x4 brick (dot away) on the left of the blue 2x2." }
  ],
  "provenance": {
    "extracted_by": "claude-opus-5-5", "extracted_at": "…",
    "graph_source": "cad_derived|llm_extracted|authored",
    "validation": { "schema": true, "acyclic": true, "observable": true, "llm_vs_cad_step_match": "11/12" },
    "reviewed_by": "D", "reviewed_at": "…"
  }
}
```
*(The cap bridges red 2×4 and green 2×2 (06 §2, D-25), so `n_cap.requires = [n_red24, n_green22]`; its state is read by the grid path, so `verifier: grid_cv`.)*

**Rover additions (lock item 7; `knowledge/rover-v1/bundle.json`; full excerpt in 18 v2 §10.2):**
```json
"relations": [
  { "component": "c_motor", "blocked_by": ["c_bar", "c_deck"], "removal_axis": [0, 0, 1], "source": "authored_demo_metadata" },
  { "component": "c_bar",   "blocked_by": ["c_deck"],          "removal_axis": [0, 0, 1], "source": "authored_demo_metadata" },
  { "component": "c_deck",  "blocked_by": [],                  "removal_axis": [0, 0, 1], "source": "authored_demo_metadata" } ],
"occludes": { "c_deck": ["c_motor", "c_bar", "c_battery"], "c_bar": ["c_motor"] },
"task_flags": { "requires_goal": true }
```
Rover nodes use `pose.frame: "base"`, `pose.discrete`, `verifier: "object_pose"`; `n_bar.requires = [n_motor]`, `n_deck.requires = [n_bar]` (authored, matches the service sheet).

**Enumerations**
- `predicate.kind ∈ {placed, absent, removed, connected, disconnected, user_confirmed}`.
- `verifier ∈ {grid_cv, object_pose, user_confirm}`. `object_pose` = verified by the spatial adapter's committed state. `user_confirm` is reserved (guided mode is cut). *(Removed: `tag_pose` (hero tag cut; Plan B tags still verify through the grid path) and `vlm_keyframe` (a VLM never decides state).)*
- `node.source ∈ {cad_derived, llm_extracted, authored, authored_demo_metadata}`. The UI **must** display it. Never label authored relations `cad_derived`.
- `document.kind ∈ {instruction_pdf, service_pdf, ldraw}`. `document.origin ∈ {team_authored, external}`; the UI names it on every citation (e.g. `TEAM-AUTHORED SERVICE SHEET`). The optional external generality guide is a saved PDF (`kind: service_pdf, origin: external`).

## 3. `observation` — perception or spatial adapter → core (~10 Hz)
```json
{
  "type": "observation", "seq": 1842, "ts_ms": 0, "source": "cv",
  "board_visible": true, "occluded": false, "stable": true, "stable_seq": 37,
  "components": [
    { "component_id": "c_red24", "status": "present", "pose": { "frame": "board", "T": ["…"], "grid": { "anchor": [3, 6], "rot": 180, "layer": 1 } },
      "confidence": 0.96, "pose_source": "grid" },
    { "component_id": "c_green22", "status": "absent", "pose": null, "confidence": 0.99, "pose_source": "grid" }
  ],
  "unknown_regions": [ { "region_id": "u-5", "cells": [[8, 9]], "reason": "unmatched_color" } ],
  "hands": [ { "present": true, "cells": [[10, 4], [10, 5]], "source": "apple_vision" } ],
  "grid": { "cells": [["base", "red", "…"]], "cell_conf": [[0.98, "…"]] },
  "timing": { "capture_ts_ms": 0, "process_ms": 18 }
}
```
Spatial adapter example component (`source: "spatial"`, frame `base`):
```json
{ "component_id": "c_motor", "status": "unknown", "reason": "hidden", "occluder": "c_deck", "pose": null, "pose_source": "arkit_object" }
{ "component_id": "c_motor", "status": "present", "pose": { "frame": "base", "T": ["…"], "discrete": { "site": "motor_bay", "rot_cw": 270 } }, "pose_source": "arkit_object", "stale": true, "last_seen_ms": 4100, "occluder": "c_deck" }
{ "component_id": "c_bar", "status": "absent", "evidence": "seen_off_assembly", "pose_source": "arkit_image" }
```
- `source ∈ {cv, spatial, replay, mock, manual_override}`. `manual_override` is always shown as such (HUD `M`, red banner).
- `status ∈ {present, absent, lifted, unknown}`. `lifted` = held off the surface; it is never treated as placed.
- `pose_source ∈ {grid, tag, arkit_object, arkit_image, manual}` (`tag` = Plan B AprilTag caps only).
- Spatial per-component fields (lock item 4): `reason ∈ {hidden, lost, out_of_view, never_seen, ambiguous_seat, ambiguous_yaw}` (with `status: unknown`); `stale` + `last_seen_ms` + `occluder` (HIDDEN_LAST_SEEN); `evidence: "seen_off_assembly"` (the only way a spatial component becomes `absent`).
- **NO_COMMIT** (camera tracking not normal, or base not locked): `board_visible: false`, `components: []`; core keeps its world; plan status `no_board`.
- **Authority rule:** placement state is decided only by the grid path (rocket) or the spatial adapter's state machine (rover, 18 v3 §3). `hands` may only *veto* commits. `stable: true` only after the producer's temporal filter commits. No AI model writes `status`.
- *(Removed: the `learned` block (YOLOE tracks, Brickognize in-hand ID) and `unknown_regions[].label` (VLM label) — all cut.)*

## 3b. `pose_observation` — spatial phone → `adapters/spatial_pose` (10 Hz; lock item 2)
Field for field as 18 v2 §4.4, plus an optional producer-local `debug: object` that consumers ignore:
```jsonc
{ "type": "pose_observation", "seq": 4411, "ts_ms": 0, "producer": "spatial-ios",
  "frame": "base", "units": "mm", "matrix_order": "row_major",          // fixed strings; adapter rejects others
  "camera": { "tracking": "normal|limited|not_available", "T_base_camera": [16] },
  "base":   { "source": "image_lock|image_continuous|aruco|manual", "state": "locked|unset", "locked_at_ms": 0 },
  "components": [
    { "component_id": "c_motor", "source": "arkit_object", "tracking_state": "tracked",
      "T_base_component": [16], "age_ms": 16, "lin_vel_mm_s": 3.1, "ang_vel_deg_s": 1.2,
      "in_view": true, "flip_rejected": false } ],
  "debug": {} }
```
- Pose-source enums (lock item 3): `base.source ∈ {image_lock, image_continuous, aruco, manual}` (`image_continuous` = the B2-continuous fallback; `manual` = B0, bannered, banned from lead runs). Component `source ∈ {arkit_object, arkit_image, none}`. `tracking_state ∈ {tracked, limited, lost, never_seen}`. `camera.tracking ∈ {normal, limited, not_available}`. `base.state ∈ {locked, unset}`.
- `in_view` uses the last pose, or the **target pose if the component was never seen**, projected into the frustum with a 10% margin.
- The phone sends raw geometry only. Classification happens in the adapter.
- **`SpatialState`** (lock item 4; display + tests) = `NO_COMMIT, LIFTED, SETTLING, REMOVED, AMBIGUOUS, PRESENT_MISPLACED, PRESENT_CORRECT, PRESENT_MISORIENTED, HOLD, HIDDEN_LAST_SEEN, HIDDEN_UNVERIFIED, OUT_OF_VIEW, LOST, NEVER_SEEN, MANUAL_OVERRIDE` (15 names; semantics in 18 v3 §3.2).

## 4. `world` — core → twin (and internal)
`{ "type":"world", "seq", "ts_ms", "task_id", "source", "components": {id: ComponentState}, "unknown_regions": [], "hands": [], "occluded": false, "satisfied_nodes": ["n_blue22"] }`.
Built only from `stable` (committed) observations. A G2 tap never writes the world (§8).

## 5. `diff`
```json
{ "type": "diff", "world_seq": 37, "task_id": "rocket-v1",
  "satisfied": ["n_blue22"],
  "items": [
    { "kind": "misoriented", "node": "n_red24", "component": "c_red24", "current": { "…": "pose" }, "target": { "…": "pose" } },
    { "kind": "missing", "node": "n_green22", "component": "c_green22" },
    { "kind": "misplaced", "node": "n_blue24", "component": "c_blue24", "current": {}, "target": {} },
    { "kind": "extra", "component": "c_black22" },
    { "kind": "unknown", "region_id": "u-5" },
    { "kind": "blocked", "node": "n_red24", "blocked_by": ["c_black24cap"] },
    { "kind": "premature", "node": "n_cap", "component": "c_black24cap", "unmet": ["n_green22"] }
  ],
  "distance": 4 }
```
`premature` = a node's predicate holds but its `requires` don't. It counts as wrong, and the fix is to undo it (07 §1). `unknown` also covers spatial components with `status: unknown` (`component` + `reason`). `unconfirmed` is reserved for `user_confirm` nodes (guided mode, cut).

## 6. `plan`
```json
{ "type": "plan", "plan_id": "p-37", "world_seq": 37, "task_id": "rocket-v1", "status": "in_progress",
  "progress": { "satisfied": 6, "total": 9 },
  "actions": [
    { "verb": "LIFT", "component": "c_black24cap", "node": "n_cap", "reason": "blocked",
      "hud": ["LIFT BLACK 2x4", "OFF THE TOP FIRST"], "evidence": ["ev_9"], "why": { "blocks": "c_red24", "because": "misoriented" } }
  ],
  "last_event": { "kind": "deviation", "detail": "c_blue22 placed 2 cells left of target" } }
```
- Verbs: `REMOVE, LIFT, MOVE, ROTATE, PLACE, CLEAR, WAIT, DONE` (+ `CONFIRM`, reserved for guided mode, cut).
- `reason ∈ {blocked, premature, inspect, extra, misplaced, misoriented, missing, unknown}`; `inspect` = `LIFT <occluder>` / `TO CHECK <c>` (the only action allowed while a component is unknown).
- `status ∈ {in_progress, verified, uncertain, occluded, no_board, awaiting_goal}`. `awaiting_goal` = the bundle has `requires_goal` and no `/control/goal` is set (HUD idle).
- `last_event.kind ∈ {progress, progress_out_of_order, deviation, external_change, none}` (a premature placement is a `deviation`).
- `why` is the structured basis that answers render from (07 §A).

## 7. `hud` — core → G2 (only on change, ≤ 4 Hz)
```json
{ "type": "hud", "seq": 211, "mode": "instruct",
  "line1": "TURN RED 2x4", "line2": "DOT AWAY · 180°", "status": "6/9",
  "brightness": 4, "alert": false,
  "answer": { "line1": "RED UNDER IT IS FLIPPED", "line2": "[MANUAL STEP 6]", "ttl_ms": 8000, "turn_id": "t-12" },
  "voice": "idle",
  "map": { "board": [[0, 1, "…"]], "highlight": [[3, 6]], "style": "target" },
  "override": false }
```
- **`mode` (sent by core) ∈ {instruct, hold, verified, uncertain, idle}.** `offline` and `detail` are **plugin-local display states** (08 §3) and never appear on the wire. *(Removed: `guided`.)*
- `voice ∈ {idle, listening, thinking, say_again}`; always `idle` unless P2 voice ships.
- `answer` is null when no answer is showing.
- Line limits: line1 ≤ 20, line2 ≤ 28, answer lines ≤ 24 / ≤ 28, status ≤ 12. Glyph whitelist per 08 §4.
- `map` is omitted for tasks without a grid (the rover).

## 8. G2 → core
```json
{ "type": "g2_input", "seq": 12, "ts_ms": 0, "input": "tap" }
{ "type": "g2_input", "seq": 13, "ts_ms": 0, "input": "menu", "item_id": 5 }
{ "type": "hud_ack",  "seq": 16, "ts_ms": 0, "hud_seq": 211, "result": "ok", "bridge_ms": 91 }
{ "type": "hello",    "seq": 0,  "ts_ms": 0, "role": "g2", "build": "1.1.0", "last_hud_seq": 210, "caps": ["menu"] }
```
- `input ∈ {tap, swipe_up, swipe_down, menu}`. Double-tap is handled locally (exit) and never sent.
- **`tap` = a recheck request:** core re-runs the planner/composer on the latest **committed** world and re-sends the current `hud` (and dismisses a showing answer). It never forces a commit and never bypasses the temporal-stability vote.
- **Menu item IDs (lock item 9):** 1 `WHY THIS STEP?` → WHY · 2 `WHERE DOES IT GO?` → WHERE · 3 `CAN I SKIP?` → CAN_I · 4 `WHAT'S DONE?` → WHAT_DONE · **5 `WHAT NEXT?` → WHAT_NEXT**. (Item 5 was `REPEAT`; REPEAT is now a voice-only intent.) After the 21:30 D valve fires, item 2 is hidden.
- P2 only (if voice ships): `{ "type": "ptt", "phase": "start"|"end", "mic": "glasses" }`, `caps += "ptt"`.

## 9. Conversation
- **Inbound question:** menu item (P1), phone page text (testing), or PTT audio (P2 only).
- **Core record** (logged; sent to the twin):
```json
{ "type": "turn", "turn_id": "t-12", "ts_ms": 0, "input": "menu|text|voice",
  "intent": "WHY", "slots": { "component": "c_black24cap" },
  "basis": "world_model|manual|both|none",
  "answer": ["RED UNDER IT IS FLIPPED", "[MANUAL STEP 6]"],
  "citations": [ { "evidence": "ev_6", "doc": "doc_1", "page": 7, "section": "Step 6" } ],
  "total_ms": 40 }
```
- Optional, voice only: `transcript`, `stt {model, ms}`, `intent_model`, `intent_ms`.
- `intent ∈ {WHY, WHERE, CAN_I, WHAT_NEXT, WHAT_DONE, MANUAL_SAYS, REPEAT, UNKNOWN}` (`MANUAL_SAYS`, `REPEAT` and `UNKNOWN` arise only from voice).
- `basis: none` ⇒ answer is `? SAY AGAIN` or `MANUAL DOESN'T SAY`.

## 10. Audio (P2 only; binary WS frames, plugin → core)
Only if hold-to-ask voice ships (18 v3 §8). Own socket `ws(s)://<host>:8787/ws/audio` (same origin; no extra whitelist entry). A binary message = 1-byte header `0xA1` + raw PCM s16le 16 kHz mono. Sent only between `ptt start` and `ptt end`. Never persisted except in debug mode.

## 11. `twin` v2 — core → phone / 2D supervisor (~4 Hz + on change; lock item 5)
```json
{ "type": "twin", "seq": 900, "task_id": "rover-v1", "frame": "base",
  "world": {}, "diff": {}, "plan": {},
  "poses": [ { "component": "c_motor", "T": ["…"], "source": "arkit_object", "state": "misoriented", "conf": 0.9, "age_ms": 40 } ],
  "target_poses": [ { "component": "c_motor", "T": ["…"] } ],
  "spatial_state": { "c_motor": "PRESENT_MISORIENTED", "c_bar": "REMOVED", "c_deck": "PRESENT_CORRECT" },
  "teardown":  { "goal": "c_motor", "path": ["c_deck", "c_bar", "c_motor"], "source": "authored_demo_metadata" },
  "highlight": ["c_motor"],
  "honesty":   { "geometry": "CAD_KNOWN_MODEL", "hidden": "CAD_LAST_SEEN", "base": "TRACKED" },
  "camera": { "jpeg_b64": "…", "occluded": false },
  "perception": { "grid_cells": [[]], "hands": [] },
  "knowledge": { "graph_source": "cad_derived", "llm_vs_cad": "11/12", "reviewed_by": "D", "doc_origin": "team_authored" },
  "turns": [ { "…": "last 5 turns" } ],
  "metrics": { "last_latency_ms": 840, "fps_vision": 11.8, "g2_connected": true },
  "log": [ { "ts_ms": 0, "kind": "deviation", "text": "DECK placed before BAR — replanned" } ] }
```
For the rocket, `frame: "board"` and the four spatial fields are absent. `camera`/`perception` are filled for the rocket only. *(Removed: `perception.tracks`, `perception.in_hand`; `board_pose_cam` is unused since the Mac AR ghost is cut.)*

## 12. Control — operator / clients → core (REST, LAN only)
| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/health` | — | `{core, vision_fps, g2_connected, twin_clients, spatial_connected}` (+ `stt_ok` only if voice ships) |
| GET | `/knowledge/<task_id>` | — | The committed bundle |
| POST | `/control/task` | `{task_id}` | Load a KnowledgeBundle (`rocket-v1`, `rover-v1`) |
| POST | `/control/goal` | `{component}` or `{clear: true}` | → `{goal, path}`. Means **access, inspect and correct the installation of `component`**; never "replace". Returns 404 when spatial is off. (lock item 6) |
| POST | `/control/ingest` | `{uri, kind}` | **Offline / build time only** (never during a demo run): wrapper around `knowledge.compile`; writes a bundle that is then committed |
| POST | `/control/calibrate` | `{}` | Vision colour calibration |
| POST | `/control/reset` | `{}` | New session |
| POST | `/control/override` | `{components}` / `{clear:true}` | Manual override (always labelled) |
| POST | `/control/ask` | `{text}` | Text question (phone page / testing). **Never called by sponsor code** (it would push an answer onto the technician's HUD) |
| POST | `/control/hud_test` | `{line1, line2}` | Bring-up only |

**Sponsor clients** may call only `GET /health`, `GET /knowledge/<task_id>`, a one-shot `ws?role=twin` snapshot, and — ARMED-only and approval-gated — `POST /control/task`, `/control/reset`, `/control/goal` (19 §8).

## 13. Transport
- Main WS endpoint: `ws(s)://<host>:8787/ws?role=vision|g2|twin`. Spatial phone → adapter: `ws://<mac1>:8790/pose`. Audio (P2): `/ws/audio`.
- G2 connection ladder: try each origin in `ENDPOINTS` (all whitelisted in `app.json`): (1) LAN `ws://<laptop-ip>:8787`, (2) `wss://<laptop>.<tailnet>.ts.net` (Tailscale Funnel). 1.5 s timeout per rung; remember the last good rung.
- The core sends the latest `hud`/`twin` snapshot on every (re)connect. Heartbeat `ping` every 2 s; clients reconnect with backoff 0.5→4 s.
- CORS: `Access-Control-Allow-Origin: *`; `OPTIONS` → 204.
- The Fetch agent reaches core at `GB_CORE_URL`, which must be set explicitly (no localhost default).

## 14. Fixtures in the lock (lock item 8)
`contracts/examples/`: `observation_*.json`, `plan_*.json`, `hud_*.json`, `twin_v1.json`, **`pose_observation.json`, `twin_v2.json`, `control_goal.json`, `bundle_rover_excerpt.json`, `spatial_transforms.json`** (18 v2 §5.4 cases 1, 2, 3, 3b, 4, 5b, 6 with values copied from that table; cases 5 and 7 stored as property cases: inputs plus the invariant name). All validated in Python and TypeScript CI.
