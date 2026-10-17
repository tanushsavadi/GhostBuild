# 09 — Supervisor View (2D, B) & Phone AR Twin (A)

> **Final reconciliation (2026-10-16).** Retitled per 18 v2 §19. The Mac three.js twin is **no longer a P1 surface**: it is built only as **W4-lite**, and only if the spatial lane is killed at S2 (17:30) or S4 (19:30). The second judge sees the **phone RealityKit twin** of the rover (mirrored to Mac 2) when spatial passes its gates, and the **2D supervisor page** otherwise. The Mac AR ghost, the hero-tag float and the iFixit guided panel are cut.

**Why not on the user's phone:** the plugin's phone page stays a minimal HUD mirror. Even designs for "phone in pocket", and a rich phone UI pulls eyes off G2. The spatial phone is a second, stand-mounted instrument, never held by the user.

## Objective
In 3 seconds, a second judge or onlooker should see three things:
1. The system really perceives the work.
2. What is wrong versus the target, and that the plan is computed from it.
3. That it replans and answers questions with cited sources.

Everything shown must be honest about what is measured and what is rendered (04 §7 provenance classes). **Upstaging the glasses is a failure**: the screen faces the second judge; the presenter points at it only after a catch.

## A. 2D supervisor page — M10, P0, owner **B** (served by core at `/twin?mode=2d`, on Mac 2)
Built Sat 17:00–21:30 (gate 21:30; red → a core-served text page).
```
┌────────────────────────────────────────────────────────────────────────┐
│ LIVE PERCEPTION (camera, rocket) │ BOARD / COMPONENT STATE (2D)        │
│ rectified feed + per-cell classes│ target vs current, diff marks,      │
│ "?" hatched, hand cells shaded   │ premature/deviation in red          │
├──────────────────────────────────┴─────────────────────────────────────┤
│ ON GLASSES: "TURN RED 2x4 · DOT AWAY · 180°"   6/9                      │
│ ASKED (menu): "CAN I SKIP?" → NOT YET / GREEN FIRST [ROCKET INSTR. S9]  │
│ MANUAL: graph from CAD · evidence AI-EXTRACTED (11/12 match) or AUTHORED│
│         · doc origin: TEAM-AUTHORED · reviewed by D                     │
│ LOG: 12:41:07 premature — cap placed before green → replanned           │
│ latency 0.84 s · vision 11.8 fps · G2 connected · [M] override banner   │
└────────────────────────────────────────────────────────────────────────┘
```
- Panels: live perception (`twin.camera`, `twin.perception`), glasses mirror (current `hud`), last 5 `turns` (input → intent → answer → citation with document origin), manual provenance (`twin.knowledge`), log + metrics.
- `?replay=logs/session.jsonl&speed=1` replays a session (labelled "REPLAY").

## B. Phone AR twin — W8, owner **A** (`spatial/`, iOS 27, RealityKit `ARView`)
Specified in 18 v2 §9.1 (scope) and 18 v3 (state, base lock, gates). **Exactly seven MUST features**, nothing added:
1. live CAD registered to reality (base locked into the AR world);
2. target ghost;
3. current-vs-target spatial diff (rotation arc + live `90°` readout, MEASURED LIVE; the commit ring comes only from core);
4. select / highlight;
5. one explode control;
6. intelligent goal-specific teardown (`FIX MOTOR ASSEMBLY` chip → `/control/goal` → only the blocking path explodes, numbered);
7. honesty / source labels (`TRACKED·OBJ`, `TRACKED·IMG`, `CAD·LAST SEEN mm:ss`, `UNKNOWN`, `TARGET`, `AUTHORED RELATIONS`, red `MANUAL OVERRIDE`).

The phone screen is mirrored to Mac 2 over USB (QuickTime), which also records the spatial footage. Not built (CUT): scan/identify, internet model lookup, CAD search, image-to-3D, component sheets, elaborate X-ray, in-phone chat/Q&A, thumbnail browser, product recognition, teardown timeline.

## C. W4-lite Mac three.js twin of the rocket — only if spatial is killed at S2/S4 (owner A, 2.5 h, gate 23:00; red → section A)
- **Assets:** `testbed/rocket/rocket.ldr` packed with three.js `utils/packLDrawModel.mjs` into `twin/public/models/rocket_Packed.mpd` [V]; LDraw library (CC BY 2.0/4.0 [V], credited in the README). Verify part numbers (3001 brick 2×4, 3003 brick 2×2).
- **Loader:** `LDrawLoader` (`setPartsLibraryPath`, `loadAsync` [V]); meshes indexed by component ID.
- **Pose:** `twin.poses[].T` (board frame, mm, 05 §1) → LDraw space: LDU = mm / 0.4, Y flipped (LDraw −Y up [V]). Interpolate ≤ 150 ms only between measured poses. `state: lifted` → part moves to an "off board" tray. Parts with conf < 0.6 or age > 500 ms render as dashed wireframes.
- **Ghost:** `twin.target_poses` at opacity 0.3; only the next action's target is highlighted. **Diff glyphs:** MOVE arrow, ROTATE arc with yaw text, REMOVE/premature red outline, LIFT up arrow.
- **Banner:** "Exact LEGO CAD (LDraw) at vision-estimated poses — not a 3D scan."
- **Performance:** ≥ 30 fps; JSON update → render < 50 ms.

## Operator panel (`?op=1`, keys; on Mac 2)
- `C` calibrate · `T` switch task (rocket / rover) · `R` reset · `F` freeze HUD
- `O` manual override → red banner "MANUAL OVERRIDE — not model output"
- `Q` type a question (`/control/ask`; shown as "typed question")

## Definition of done
- Every frame of the demo replay renders correctly; the premature/deviation event is visually obvious within 0.5 s; readable from 2 m; provenance and honesty labels always visible.

## Mocked path
Works from `core --mock-vision scenarios/demo.yaml` + `knowledge/fixtures/rocket_bundle.json` (2D, W4-lite) and `contracts/examples/twin_v2.json` (phone) from hour 1.

## Risks
- **Upstaging the glasses** (see above).
- **GPU contention:** nothing renders on Mac 1.
- **LDraw part mapping errors (W4-lite):** a test compares rendered part count and colours against the bundle.
