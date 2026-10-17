# 18 v2 — Spatial Twin Pass: Execution Correction

**Date:** 2026-10-16 (the day before the event).
**Status:** proposal. It corrects `18_SPATIAL_TWIN_PASS.md` (V1). Docs 00–18 stay authoritative until the edits in §19 are accepted. Nothing here touches the P0 rocket loop.

> **⚑ SUPERSEDED FOR EXECUTION BY `18_SPATIAL_TWIN_PASS_V3.md` WHERE THEY DIFFER (final reconciliation, 2026-10-16).** Unamended sections remain in force: frames and formulas §5, rig §7, training §8, app MUST list §9.1 (goal chip reworded to "Fix motor assembly"), teardown §10 (motor-story wording corrected), isolation rules §11.3, video plan §17 (as amended for two exports, see `20_FINAL_IMPLEMENTATION_BIBLE.md` §16). **Superseded:** the §6 state machine (→ V3 §3), §6.2 start values (→ derived from measured σ, V3 §6.4), §11.1–11.2 voice recommendation (→ decided: P2 opportunistic), §12 contract lock at 12:30 and SP5 at 15:00 (→ one lock at 12:45, V3 §4), the §13 mm gate thresholds (→ V3 §6 task gates; mm figures are diagnostics), the §14–15 demo scripts (→ V3 §10), the §18 lead rule items 2–3 (→ V3 §9), and the §19 reconciliation list (→ V3 §13, now applied).
**Scope of this pass:** execution only. V1's architecture is accepted in principle. This pass fixes tracking scope, coordinate frames, the state model, the rig, app scope, staffing, schedule and gates.
**Tags:** **[V]** checked against Apple's documentation data on 2026-10-16 (sources in §20) · **[C]** community report · **[I]** inference or estimate · **[D]** decision · **[verify]** check at hack time before depending on it.

---

## 1. Executive verdict

### **PROTOTYPE SPATIAL — CORRECTED PLAN**

- **One** learned markerless tracker: the motor. Every other moving module uses a zero-training ARKit image card. The base frame comes from a fixed fiducial on the mat, not from a training job and not from one of the four tracked-image slots.
- The native app ships seven demo-critical features (§9). Everything else is stretch or cut.
- **Spatial leads the judging demo only if all of §18 holds,** including a passing markerless motor. Otherwise the rocket leads, and spatial is a 20-second add-on or nothing.
- **The rocket P0 path is unchanged.** It is frozen at 02:00 and filmed at 02:00–02:45, before any spatial gate after S6 runs.
- **One trade the team must accept explicitly (§11):** hold-to-ask voice (W3) is demoted to opportunistic P2. Its 7 h (B 3 h, C 4 h) pay for the spatial core adapter and the 2D supervisor. The G2 contextual menu remains the judge's way to ask "Why?". If the team keeps voice instead, the spatial loop has no owner, and spatial can only be a visual add-on.

| Outcome | Estimate [I] |
|---|---|
| P(spatial passes §18 and leads) | ≈ 0.35 (iOS 27 device OK 0.9 × motor markerless passes S5 0.5 × loop + 5 clean runs 0.8) |
| P(spatial is at least a working add-on: A1 cards + live CAD) | ≈ 0.75 |
| Effect on the rocket demo | none on P0; the rocket loses the Mac three.js twin (W4), replaced by a 2D supervisor and, if spatial works, the phone |

---

## 2. What V1 got right (kept)

1. **Apple-native, on-device pose** (ARKit + RealityKit + Create ML), with no GPU and no cloud on the live path. Rejecting cloud FoundationPose was evidence-based and stays rejected.
2. **A zero-training floor**: ARKit image anchors, 4 simultaneous moving images [V].
3. **The phone on a stand is an instrument**, not the user's UI. G2 executes; the phone explains.
4. **One contract for all pose sources**; tiers fail independently.
5. **Core is the only authority on physical state.** The phone senses and renders.
6. **LEGO System custom rover** as the spatial rig (V1 §8 scoring), and exact LDraw CAD as the render source.
7. **Honesty labels on screen** (`TRACKED`, `CAD`, `LAST SEEN`, `MANUAL OVERRIDE`).
8. **Standard-mode training only,** and the scale check against callipers [V].
9. **The rocket P0 path never imports spatial code.**

## 3. What V1 got wrong or over-scoped

| # | V1 said | Problem | V2 fix |
|---|---|---|---|
| 1 | Train `.referenceobject` for 5 modules in parallel on spare Macs and 2 EC2 hosts | 4–8 h per job [C], an EC2 24 h minimum [V], and one training job per module nobody cares about | Motor only; deck optional on a second idle Mac; no EC2 (§8) |
| 2 | Base tracked by `detectionObjects`, or by an image card | A training job for something that doesn't move. And ARKit gives tracking slots to "the first images it observes" and frees one only when an image leaves view [V], so a base card permanently consumes 1 of 4 slots | Base = fixed fiducial on the mat, locked once into world tracking, not in the module image set (§4.1) |
| 3 | "tracked and ≥ 40 mm from target → `lifted`/`absent`" | A present but misplaced part becomes "absent" | Nine-state model with positive evidence for every state (§6) |
| 4 | Relations and insertion axes `source: "cad_derived"` | An LDraw parser cannot derive "bar locks motor" or removal axes in the time available | `source: "authored_demo_metadata"`; CAD supplies poses, hierarchy and bounding boxes (§10) |
| 5 | App: scan, identify, asset card, explore mode, X-ray slider, scrubber, component sheets, in-phone voice Q&A | ≈ 16 h of UI for one person | 7 MUST features ≈ 9 h (§9) |
| 6 | Demo opens by scanning our own rover | Identifying an object we built is not impressive | Open with the CAD locked to the real rover (§14) |
| 7 | S3 (4 h build) due 17:00 while A also models the rover until 14:15 and supervises training; S7 (4 h) due one hour after S6; A at ≈ 22 h | Durations exceed wall clock; A in three places at once | Critical path recomputed; every gate's work fits its window (§12–13) |
| 8 | S6 requires ≥ 3 simultaneous markerless-or-card tracks; S9 at 03:00 with video at 04:00 | Mixes system success with frontier success; video late | Separate metrics (§13); rocket footage at 02:00, before spatial S7 |
| 9 | `T_base_c = inverse(T_world_base) · T_world_c · T_anchor_cad` | Ambiguous names; no units; no ARKit↔OpenCV camera flip; no LDraw→base mapping; yaw sign unspecified vs the grid's clockwise `rot` | Full frame model with naming rule, units, matrix order and test vectors (§5) |
| 10 | Not mentioned | Apple recommends **extended** training for `trackingObjects` [V]; extended ≈ 7× standard [C], so ≈ 28 h | Accept the risk: standard + **Upright** viewing angles, which Apple says track more accurately than All Angles [V]; constrain the demo motion to match (§7) |
| 11 | New `scene_state` message | Duplicates 05 §11 `twin`, which already carries world, diff, plan and target poses | `twin` v2 = `twin` + 4 fields (§4.5) |
| 12 | "W4 three.js twin replaced by the phone" **and** "fallback: Mac three.js twin" | If nobody builds W4, the fallback doesn't exist | Explicit: W4 is not built unless spatial is killed at S2/S4, in which case A builds a reduced W4-lite (§16) |
| 13 | "Rocket AR on the phone for free" | Needs board registration to the phone; not free | Cut |
| 14 | Hidden parts: `lost` while a blocker covers it → `unknown` | No rule for a part seen, verified, then covered | Occlusion persistence rule (§6.3) |

---

## 4. Corrected tracking architecture

```
 MAT (stationary)  ── base fiducial card, never touched, outside rover footprint
   └─ 32×32 baseplate glued to the mat ── chassis (+ battery) snapped on: cannot slide
        ├─ MOTOR  ─ A2 markerless (.referenceobject, trackingObjects)   ← the hero
        │           A1 fallback: clip-on card (only if A2 fails S5)
        ├─ BAR    ─ A1 image card
        ├─ DECK   ─ A1 image card   (A2 only if a 2nd idle Mac + spare compute; §8)
        └─ BATTERY─ part of the chassis in MUST (rendered, explodable, not tracked);
                    A1 card in the 4th slot is stretch
```

### 4.1 Base frame

| Tier | How | Cost | Slots used | Status |
|---|---|---|---|---|
| **B2 Image lock (MUST)** | Session phase 1: `detectionImages = {baseCard}`, `maximumNumberOfTrackedImages = 1`. Average `T_world_fid` over 1 s of stable frames, then add an `ARAnchor` at `T_world_base`. Phase 2: re-run the configuration **without** the base card and **without** reset options, with the module cards plus the motor reference object. "Re-lock" button repeats phase 1 (≈ 2 s). | 0.75 h, no dependencies | 0 after lock | Keeping anchors across `run(_:)` without reset is [verify] at S2 |
| B1 ArUco continuous (stretch) | OpenCV `ArucoDetector` on `capturedImage` Y-plane at 5 Hz, `solvePnP` (IPPE_SQUARE) with `ARCamera.intrinsics`, composed with `T_world_camera` (§5). Detects a bumped rig automatically. | 2–2.5 h; needs `opencv2.xcframework` with objdetect/ArUco headers [verify] | 0 (not ARKit) | Only if C is free after S6; flag `--base aruco` |
| B0 Manual (last resort) | Tap the baseplate corner on a detected plane | 0.25 h | 0 | Bannered **MANUAL OVERRIDE**; spatial cannot lead |

**Why B2 is enough for the hackathon** [I]:
- The rig makes the base physically stationary: baseplate glued to the mat, chassis snapped onto it.
- ARKit refines world anchors as its map improves, so a locked base anchor tracks the map.
- The residual risk is the mat being bumped. The procedure is to re-lock before every run, and S7 includes a drift test.

### 4.2 Module tiers

| Module | Primary | Fallback | Why |
|---|---|---|---|
| Motor | **A2** `trackingObjects` (iOS 27 [V]) | A1 clip-on card | The one moment where markerless matters: the judge rotates a bare part and its CAD follows |
| Bar | A1 card | — | Lifted and replaced; a card on its top face stays visible |
| Deck | A1 card | A2 optional | Lifted by tabs; a card on its top face stays visible; markerless adds little wow |
| Battery | none (part of base) | A1 card in slot 4 (stretch) | Never moves in either script |

**Slot budget:** in A2 mode, 2 images (bar, deck) out of 4. In A1-only mode, 3 (motor, bar, deck). One slot is always spare. Never put more than 4 module images in `detectionImages`, because first-seen images keep their slots [V].

### 4.3 Fallback ladder (pose sources, per component)

```
A2 reference object (motor)  →  A1 image card  →  hold last committed state (≤ 1.5 s)  →  UNKNOWN
base: B2 image lock  →  B0 manual (MANUAL OVERRIDE; spatial demoted to add-on)
```
- **PoseFusion per frame:** use A2 if `isTracked`, else A1 if tracked, else hold. The rendered CAD keeps its last pose, drawn desaturated with `LAST SEEN mm:ss`.
- **Flip guard (A2):** reject a sample whose yaw jumps > 45° within 100 ms while the measured angular velocity is < 90°/s. Mark it `limited` and never commit it. A 4-fold-symmetric footprint invites exactly this failure; §7 makes the geometry asymmetric.

### 4.4 Pose contract — `pose_observation` (phone → `adapters/spatial_pose`, 10 Hz)

```jsonc
{ "type": "pose_observation", "seq": 4411, "ts_ms": 0, "producer": "spatial-ios",
  "frame": "base", "units": "mm", "matrix_order": "row_major",          // fixed strings; adapter rejects others
  "camera": { "tracking": "normal|limited|not_available", "T_base_camera": [16] },
  "base":   { "source": "image_lock|aruco|manual", "state": "locked|unset", "locked_at_ms": 0 },
  "components": [
    { "component_id": "c_motor", "source": "arkit_object", "tracking_state": "tracked",
      "T_base_component": [16], "age_ms": 16, "lin_vel_mm_s": 3.1, "ang_vel_deg_s": 1.2,
      "in_view": true, "flip_rejected": false },
    { "component_id": "c_bar",  "source": "arkit_image", "tracking_state": "lost",
      "T_base_component": [16], "age_ms": 2300, "in_view": true },
    { "component_id": "c_deck", "source": "none", "tracking_state": "never_seen", "T_base_component": null }
  ] }
```
- `tracking_state ∈ {tracked, limited, lost, never_seen}`. `in_view` means the component's last pose projects inside the camera frustum with a 10% margin.
- The phone sends **raw geometry only**. Classification happens in the adapter (§6), which emits 05 §3 `observation` messages to core as producer `source: "spatial"`. That is the same pattern as `perception/`, so core's authority model doesn't change.

### 4.5 Core → phone: `twin` v2 (05 §11 plus four fields)

```jsonc
{ "type": "twin", "seq": 902, "task_id": "rover-v1", "frame": "base",
  "world": {}, "diff": {}, "plan": {},                         // unchanged
  "poses": [ { "component": "c_motor", "T": [16], "source": "arkit_object", "state": "misoriented", "age_ms": 40 } ],
  "target_poses": [ { "component": "c_motor", "T": [16] } ],   // unchanged; base frame, mm
  "spatial_state": { "c_motor": "PRESENT_MISORIENTED", "c_bar": "REMOVED", "c_deck": "PRESENT_CORRECT" },  // NEW (display)
  "teardown":  { "goal": "c_motor", "path": ["c_deck", "c_bar", "c_motor"], "source": "authored_demo_metadata" }, // NEW
  "highlight": ["c_motor"],                                    // NEW
  "honesty":   { "geometry": "CAD_KNOWN_MODEL", "hidden": "CAD_LAST_SEEN", "base": "TRACKED" } }  // NEW
```

---

## 5. Corrected transform and coordinate model

### 5.1 Naming rule (no exceptions in code, comments or docs)

**`T_A_B` maps coordinates in frame B to frame A:** `p_A = T_A_B · p_B`.
- Composition chains inner indices: `T_A_C = T_A_B · T_B_C`.
- Inverse swaps indices: `T_B_A = (T_A_B)⁻¹`.
- A variable that doesn't follow this pattern fails code review.

### 5.2 Frames

| Frame | Definition | Units / handedness |
|---|---|---|
| `world` | ARKit world; origin = session start; +Y up (gravity alignment) [V] | m; right-handed [V] |
| `cam` | ARKit camera; +x along the long axis, +y up in landscape-left, +z out of the screen, so the camera looks along −z [V] | m |
| `cv` | OpenCV camera for `capturedImage`: +x right, +y down, +z forward. **`T_cam_cv = diag(1, −1, −1, 1)`** [I; verify by reprojecting the base card corners at S2] | m |
| `fid` | Base card image anchor. Assumed: origin at the image centre, image in the anchor's x–z plane, +y normal out of the image [I; verify with an axis gizmo at S2] | m |
| **`base`** | **Canonical GhostBuild frame:** origin at the baseplate's near-left top corner; +X right (the judge's left → right), +Y away from the judge, +Z up. Same axis convention as 05 §1 `board`. | **mm in every contract** |
| `img_k` | Image anchor of module k's card (same convention as `fid`) | m |
| `obj_k` | `ARObjectAnchor` of module k. Assumed = origin of the USDZ it was trained from [I; measured at S5 by seated calibration] | m |
| `c_k` | Component frame: origin at the bottom centre of the footprint on the seating plane; axes equal `base` axes when the component is at its target pose | m inside the app, mm on the wire |
| `model_k` | Local frame of the RealityKit entity loaded from the USDZ (may be Y-up) | m |
| `tgt_k` | Target pose of component k | `T_base_tgt_k` from CAD |

**Wire rules:**
- Internal math is in metres. Translation is converted to mm only when the contract is written.
- Matrices are **row-major on the wire**. `simd_float4x4` is column-major, so serialise with an explicit loop. Test 6 below checks it.
- **Yaw** is counter-clockwise-positive about +Z (right-hand rule). The discrete `rot_cw` sent to core uses the 05 §1 grid convention (clockwise from above): `rot_cw = (−yaw) mod 360`.

### 5.3 Formulas

| # | Quantity | Formula |
|---|---|---|
| F1 | Base (B2 lock) | `T_world_base = T_world_fid · T_fid_base`. `T_fid_base` is constant, authored from the mat layout. With the card flat, its top edge pointing away from the judge: `R_fid_base = [[1,0,0],[0,0,1],[0,−1,0]]`; translation = baseplate corner relative to the card centre. |
| F1b | Base (B1 ArUco, stretch) | `T_world_base = T_world_cam · T_cam_cv · T_cv_tag · T_tag_base`, median-filtered over 1 s |
| F2 | Module, A1 | `T_world_c = T_world_img · T_img_c` |
| F3 | Module, A2 | `T_world_c = T_world_obj · T_obj_c` (expected ≈ `T_obj_model`; measured by F7) |
| **F4** | **Canonical pose (what core consumes)** | **`T_base_c = (T_world_base)⁻¹ · T_world_c`** |
| F5 | Ghost render | `T_world_tgt = T_world_base · T_base_tgt` |
| F6 | Error terms | `Δp = p(T_base_c) − p(T_base_tgt)` (base frame); `Δxy = ‖Δp.xy‖`; `Δz = Δp.z`; `R_tgt_c = R_tgtᵀ · R_c`; `Δyaw = wrap(atan2(R_tgt_c[1][0], R_tgt_c[0][0]))` to (−180°, 180°]; `tilt = acos(clamp(R_base_c[2][2]))` |
| F7 | Seated calibration (A1 card offsets and the A2 origin check) | With module k physically seated at its target, averaged ≥ 1 s: `T_img_c := (T_world_img)⁻¹ · T_world_base · T_base_tgt`. Validate by rotating 90° (motor) or by lift-and-reseat (bar, deck): the reading must return to target within 4 mm / 3°. This replaces calliper-measured card offsets. |
| F8 | Camera in base (visibility, `in_view`) | `T_base_cam = (T_world_base)⁻¹ · T_world_cam` |
| F9 | CAD → base targets | Blender + ImportLDraw puts the rover in a Z-up scene. Place the baseplate's near-left corner at the Blender origin, judge-away = +Y. Then `T_base_tgt_k` = each component object's world matrix after its origin is set to bottom-centre. A ≤ 30-line `bpy` script writes `testbed/rover/component_frames.json` (mm, row-major) **and** the per-component USDZ files. One source feeds the app, the bundle and Create ML. `R_c_model` (USD up-axis handling) is checked at S2: the gear must appear on the correct side and the motor must be upright. [verify] |

**Common bugs these formulas prevent:**
- applying a card offset in the world frame instead of the component frame;
- mixing up m and mm;
- writing column-major matrices into a row-major contract;
- the ARKit −z camera direction;
- the clockwise/counter-clockwise sign of `rot`;
- a scale factor folded into a rotation matrix. Convert LDraw translations to mm first and keep rotations orthonormal.

### 5.4 Unit-test vectors

D generates these with numpy as `contracts/examples/spatial_transforms.json`. Both the Swift XCTest suite (A) and the Python adapter tests (C) consume the same file. Let `R_wb = [[1,0,0],[0,0,1],[0,−1,0]]` (base → world for a flat mat: base X → world X, base Y → world −Z, base Z → world Y; det = +1).

| # | Case | Input | Expected `T_base_c` (mm) | What it catches |
|---|---|---|---|---|
| 1 | Identity | `T_world_base = I`, `T_world_img = I`, `T_img_c = I` | `I` | plumbing |
| 2 | Translation | `T_world_base = [R_wb │ (0.20, 0.00, −0.30)]`; `T_world_c = [R_wb │ (0.25, 0.02, −0.33)]` | `[I │ (50, 30, 20)]`: 50 right, 30 away, 20 up | world Y-up vs base Z-up; m → mm |
| 3 | 90° yaw | `T_world_c = T_world_base · [Rz(+90°) │ (0.100, 0.050, 0)]` | `[[0,−1,0],[1,0,0],[0,0,1] │ (100, 50, 0)]`; `yaw = +90`, `rot_cw = 270`; vs target yaw 0: `Δyaw = +90`, correction = clockwise 90° → HUD `TURN MOTOR 90° →` | sign conventions; HUD direction |
| 3b | Wrap | yaw 359° vs target 1° | `Δyaw = −2°` | wrap bug |
| 4 | Anchor offset | Card centre at `(30, 0, 40)` mm in `c`, flat, top edge toward +Y_c: `T_c_img = [[1,0,0],[0,0,−1],[0,1,0] │ (0.030, 0, 0.040)]`. True `T_base_c = [Rz(90°) │ (100, 50, 0)]`. Synthesise `T_world_img = T_world_base · T_base_c · T_c_img`; run F2 + F4. | recovers `[Rz(90°) │ (100, 50, 0)]`. The card centre sits at `(100, 80, 40)`. The wrong "subtract the offset without rotating it" path gives `(70, 80, 0)` and must fail. | offset applied in the wrong frame or order |
| 5 | Camera moves, part still | `T_world_cam1 = [I │ (0, 0.40, 0.30)]`, `T_world_cam2 = [Ry(30°) │ (0.20, 0.45, 0.25)]`; synthesise `T_cv_tag_i = (T_world_cam_i · T_cam_cv)⁻¹ · T_world_tag`; part's `T_world_img` unchanged | `T_world_base` identical (≤ 1e−9) for both cameras; `T_base_c` identical; `T_base_cam` differs | camera-relative leakage; missing `T_cam_cv` |
| 5b | Flip | point `(0, 0, 0.5)` in `cv` | `(0, 0, −0.5)` in `cam` | OpenCV vs ARKit camera |
| 6 | Serialisation | simd matrix with translation (1, 2, 3) | JSON indices `[3]=1, [7]=2, [11]=3` | column-major leak |
| 7 | Seated calibration round trip | random `T_img_c`; synthesise seated reading; run F7; then F2 + F4 at a new pose | recovers the new pose ≤ 1e−6 | calibration math |

---

## 6. Corrected spatial state machine — SUPERSEDED (→ V3 §3; do not implement this table)

### 6.1 States (per component, evaluated in the adapter each sample, in this order)

| Rule | Condition (base frame; thresholds in §6.2) | State | Core `observation` | Commits? |
|---|---|---|---|---|
| 0 | camera `tracking ≠ normal` or base `≠ locked` | **NO_COMMIT** | nothing new; core keeps last world, plan status `uncertain` | no |
| 1 | tracked, but `lin_vel > v_move` or `ang_vel > ω_move`, or not stable for `t_stable` | **SETTLING** | nothing new for this component | no |
| 2 | tracked, `Δz_seat > z_lift` or `tilt > tilt_lift` | **LIFTED / IN HAND** | `lifted` | after 500 ms continuous |
| 3 | tracked, seated (`│z − z_seat│ ≤ z_tol`, `tilt ≤ tilt_tol`), at target site (`Δxy ≤ xy_site`), `│Δyaw│ ≤ yaw_ok` | **PRESENT_CORRECT** | `present`, pose `discrete: {site: target, rot_cw: target}` | yes |
| 4 | as 3, but `│Δyaw − 90k│ ≤ yaw_q` for k ∈ {1, 2, 3} | **PRESENT_MISORIENTED** | `present`, `rot_cw ≠ target` → diff `misoriented` → `ROTATE` | yes |
| 4b | as 3, yaw in neither band | **AMBIGUOUS** | `unknown`, `reason: ambiguous` → `ADJUST MOTOR` / `SEAT IT SQUARE` | yes, as unknown |
| 5 | tracked, seated, **inside** `install_zone`, not at the target site | **PRESENT_MISPLACED** | `present`, `site: <other site id>` or `"zone"` → diff `misplaced` → `MOVE` | yes |
| 6 | tracked, seated, **outside** `install_zone` on the mat | **REMOVED (off-assembly)** | `absent`, `evidence: seen_off_assembly`. Positive evidence it is elsewhere. | yes |
| 7 | not tracked, `never_seen`, a **present** occluder covers it (authored `occludes`) | **HIDDEN · NEVER SEEN** | `unknown`, `reason: hidden`, `occluder: c_deck` → planner may issue an inspect action (§10.4) | yes, as unknown |
| 8 | not tracked, last committed **while visible**, then an occluder became present over it | **HIDDEN · LAST SEEN** | keeps last committed status, `stale: true`, `last_seen_ms` | holds |
| 9 | not tracked < `t_hold` (typically a hand) | **HOLD** | nothing new | no |
| 10 | not tracked, last pose outside the frustum | **OUT_OF_VIEW** | `unknown`, `reason: out_of_view` | yes, as unknown |
| 11 | not tracked ≥ `t_hold`, should be visible, no occluder | **LOST** | `unknown`, `reason: lost` → plan `uncertain`, HUD `SHOW MOTOR` / `TO THE CAMERA` | yes, as unknown |
| 12 | never tracked, nothing covers it | **NEVER_SEEN** | `unknown`, `reason: never_seen` | yes, as unknown |
| — | operator override | **MANUAL_OVERRIDE** | 05 `source: manual_override` | bannered; banned from lead runs |

**Losing a track is never treated as absence.** `absent` comes only from rule 6, where the part is positively seen somewhere else. A part that disappears is HOLD, then LOST or HIDDEN, never ABSENT.

### 6.2 Tunable demo parameters (`adapters/spatial_pose/params.yaml`) — fallback defaults only; final values are derived from measured σ (V3 §6.4)

These are starting values for this rig, not product constants. Tune them at S4/S7 from recorded histograms: 3 trials per motion, then set each threshold at about 3σ of the static jitter.

| Param | Start | Notes |
|---|---|---|
| `xy_site` (enter / exit) | 6 mm / 9 mm | hysteresis |
| `yaw_ok` (enter / exit) | 12° / 18° | hysteresis |
| `yaw_q` | ±20° around 90/180/270 | |
| `z_tol`, `tilt_tol` | 6 mm, 10° | seated |
| `z_lift`, `tilt_lift` | 20 mm, 25° | in hand |
| `install_zone` | chassis top bbox + 15 mm, from CAD | authored region |
| `v_move`, `ω_move` | 15 mm/s, 15°/s | moving |
| stability | `lin < 5 mm/s ∧ ang < 5°/s` for ≥ 5 samples **and** ≥ 300 ms | same K/settle as the P0 grid |
| `t_hold` | 1.5 s | hand occlusion |
| `occludes` | deck → {motor, bar, battery}; bar → {motor} | authored (§10) |

### 6.3 Occlusion persistence

A hidden component keeps its last committed status **only if** that status was committed while the component was visible and the occluder arrived afterwards (rule 8). This is what lets "deck on before bar" be judged: the motor was verified correct, then covered.
- If the occluder was already there when the session started, the component is NEVER SEEN (rule 7). The system then asks the judge to expose it rather than assuming.
- The phone label reads `MOTOR · VERIFIED 12:41 · NOW HIDDEN`.

### 6.4 Invariants (adapter and planner tests)

1. No `ROTATE`, `MOVE` or `PLACE` is ever issued for a component in SETTLING, HOLD, AMBIGUOUS, LOST, OUT_OF_VIEW or NEVER_SEEN.
2. The only instruction allowed while a component is unknown is the information-gathering one: `LIFT <occluder>` / `TO CHECK <component>`. It is valid in every possible hidden state, because exposing a part is reversible and needed for verification. Otherwise the plan is `uncertain`, which is the 07 §4 step 0 behaviour.
3. A recorded hand-occlusion session (motor covered for 1.2 s) produces zero state changes.
4. A recorded "motor carried to the mat" session produces REMOVED, never MISPLACED. "Motor seated in the battery bay" produces MISPLACED.

**Uncertain state never produces a confident physical instruction.**

---

## 7. Corrected rover and physical module design

### 7.1 Layout

```
                 far side (away from judge)
        ┌──────────────── mat (A3, matte) ────────────────┐
        │ [BASE CARD 80×80]        phone on gooseneck:     │
        │                          35–40 cm from centre,   │
        │   ┌──── 32×32 baseplate (glued) ───┐  ~50° down, │
        │   │  ┌─ chassis 12×20 (dk grey) ─┐ │  far-left   │
        │   │  │ [battery] [ MOTOR 6×6 ]   │ │  corner     │
        │   │  │ ═══ BAR (L, yellow) ═══   │ │             │
        │   │  └── DECK shell over all ────┘ │             │
        │   └────────────────────────────────┘ tray: bar/deck rest here
        └──────────────────────────────────────────────────┘
                 near side: judge stands here; hands come from here
```
- **Phone placement:** on the far side, elevated about 50°, looking down at the module tops. The judge's hands come from the near side and grip module sides, so the tops (cards and the motor's features) stay visible.
- **Lighting:** the LED panel used for P0, diffuse. Matte cards, no lamination.
- **Mirror:** the phone screen goes to Mac 2 over USB (QuickTime movie recording). The same cable records the spatial footage.

### 7.2 Modules

| Module | Size (studs → mm) | Colour | Asymmetric features | Tracking surface | Judge grips | Notes |
|---|---|---|---|---|---|---|
| Base + chassis + battery | baseplate 32×32 (256 mm); chassis 12×20 (96×160) | dark grey; battery blue | wheels, rear bumper, blue "+" tower | **base card on the mat**, outside the footprint | never touched | snapped to the glued baseplate so it cannot slide |
| **Motor** | **6×6 footprint (48×48)**, ≈ 40 mm tall | red body, black top on one half | **yellow gear wheel on +X only**, one 1×1 round tower at the rear-left corner, black/red split top. No 90° or 180° symmetry. | A2: whole body, **no card**. A1 fallback: clip-on 40×40 mm card on a tiled top | pinch front and back faces while rotating | the square footprint seats at 0/90/180/270, which is the planted error; the asymmetry makes the error visible and prevents tracker flips |
| Bar | L: 6 wide (48 mm) × 12 long, + 6×4 foot | yellow | L shape; 1×2 vertical handles at both ends | **40×80 mm card** on the long arm's tiled top | the end handles | sits over the motor's rear edge and the battery: "locks the motor" |
| Deck | 12×14 (96×112) shell, 2 bricks tall | white, black trim | antenna fin at rear-left; grip tabs front and back | **70×70 mm card** centred on top | the front/back tabs; lifted straight up | **seats on chassis pillars identically with or without the bar**, so a premature deck reads as "seated at target" |

### 7.3 Card rules

- One distinct, high-texture, non-repeating photo per card. Check it against Xcode's AR asset-catalog quality warnings.
- Set `physicalWidth` to the measured printed width. A wrong width scales the depth.
- Mount cards on tiles (flat, no studs), with matte paper and no gloss.
- Cards are ≥ 40 mm on the short side [I: about 170 px across at 40 cm on the wide camera].
- Offsets come from seated calibration (F7), not from callipers.

### 7.4 Motion design (6-DoF internally; the demo uses three motions)

1. **Yaw rotation in place** (motor, 90°): the top stays visible throughout.
2. **Lift and removal along +Z** (deck, bar): the judge holds it level, so the card faces the phone; tilt > 25° is LIFTED anyway.
3. **Placement on the mat or tray** (REMOVED), and re-seating.

No hand-tumbling. This is why the motor trains with **Upright** viewing angles [V: restricted angles track more accurately]. It also gives tilt a clean role as the LIFTED signal.

### 7.5 Reset (target < 40 s)

1. Deck off.
2. Bar off.
3. Turn the motor to the "reset" sticker (90° wrong).
4. Bar on, deck on.
5. Press `R` on the operator panel.
6. Tap **Re-lock base** (2 s).

The rocket rig stays on the same table with its own < 40 s reset (11).

---

## 8. Create ML training plan

| Item | Decision |
|---|---|
| What | **Motor only** (priority 1). Deck is priority 2, only under the conditions below. |
| Mode / angles | `xcrun createml objecttracker -s motor.usdz -o motor.referenceobject` (standard is the default [V]) with **Upright** angles (flag name from `-h` [verify]). No objects-to-avoid: no other module USDZ exists at kick-off, and the motor's colours are unique on the table. |
| Where | A dedicated trainer Mac: (1) a borrowed Apple-silicon Mac (ask Friday), else (2) D's laptop if D's laptop is not Mac 1, else (3) B's laptop **after G0**. **Never Mac 1** (perception + core) and **never A's Mac** (Xcode + device builds). |
| Requirements | Apple silicon, macOS 15+ to train [V]; the CLI exists since Xcode 26 (macOS 15.4+) [V]. Objects trained with Xcode 27 / macOS 27 need iOS 27 [V], which is fine. |
| Kick-off | **Target 13:30, hard deadline 13:45 Sat (gate S1).** Motor first, before the rocket model (§12). |
| Wall clock | ≈ 4 h standard on an M4 Max/128 GB [C]; budget 4–8 h on our laptops [I]. S1 rule: if the ETA shown at 13:45 is past 22:45, **A2 dies now**. The motor gets its card and nobody re-trains. |
| While it runs | A builds the rocket model, the app floor, the other modules and A1. Nobody babysits; check the ETA at 16:45, 19:30 and 21:30 standups (2 min each). |
| Failure mid-run | No restart unless the new ETA finishes before 22:45. |
| Friday calibration (S0) | On the trainer Mac, start a job on any public sample USDZ, read the ETA after 10 min, cancel. This is tool familiarity, not project work, and it tells us the machine's speed before Saturday. |
| Second Mac (only if idle) | Used in this priority order: (a) **deck** if its USDZ exists by 18:15 and ETA ≤ 5 h (done ≤ 23:15; C tests it at 00:00). (b) Nothing else. |
| Extended mode | Not used: ≈ 7× standard [C], so > 24 h, even though Apple recommends it for `trackingObjects` [V]. Upright angles plus constrained motion are our mitigation. Accepted risk. |
| EC2 Mac | **Rejected.** 24 h minimum allocation [V, AWS]; dedicated-host quota requests may not be granted same-day [I]; Xcode 27 install on the AMI takes 1–2 h [I]; M2-class hosts are not faster than our laptops [I]. All of that buys one optional job a borrowed laptop does with zero setup. |

### 8.1 Tracking asset vs rendering asset (Object Capture)

**Separation works in principle.** The reference object embeds the USDZ it was trained on (`usdzFile`) [V], and nothing forces us to render that mesh. We render the clean CAD entity in frame `c`.
- If tracking were trained on an Object Capture mesh (captured on iPhone with the Reality Composer app → USDZ [V]), its origin would be arbitrary.
- F7 seated calibration measures `T_obj_c` in 10 s, so no ICP alignment step is needed.

**Decision: Object Capture is not on the plan.** Three reasons:
1. LEGO in uniform colours is close to the "photorealistic" CAD Apple asks for [V], and CAD-only is the simplest truthful path.
2. A small, glossy 48 mm object is a weak Object Capture subject [I].
3. Training takes 4–8 h, so a CAD failure found at S5 (23:30) cannot be fixed by re-training on a capture.

The only viable form is a **parallel hedge started by 16:30**. **Gate S-OC (optional):** run it only if a second Mac is idle at 16:00 **and** someone has 20 minutes free (capture 10 min, on-device processing 10 min, AirDrop). If both conditions hold, train in parallel and test both models at S5. If not, skip it without discussion. It never blocks anything.

---

## 9. Corrected native app scope (`spatial/`, Swift, SwiftUI + RealityKit `ARView`)

`ARView` with a custom `ARWorldTrackingConfiguration` is the path Apple's own iOS 27 reference-object sample uses [V]. Each component is a parent entity in frame `c` with its model child at fixed `T_c_model`. Its world transform is set every frame from PoseFusion. One code path covers A1, A2 and hold.

### 9.1 MUST (demo-critical; ≈ 9 h of A's 13 h lane, plus the floor and tracking)

| | Feature | Implementation | h |
|---|---|---|---|
| A | **Live AR CAD** | CAD at 0.55 opacity, tinted by source; banner "Exact CAD (LDraw) at tracked poses — not a scan"; debug overlay (fps, per-source state, WS status) | in floor + A1 |
| B | **Target ghost** | Clone at `T_world_tgt` (F5), 0.25 opacity, cyan; shown when status ≠ correct, and always for the goal | 0.5 |
| C | **Current → target diff** | Rotation arc (segment of small spheres around the component centre from current to target yaw) plus a live `90°` billboard computed locally with F6 at 60 Hz (labelled TRACKED vs TARGET); translation arrow when `Δxy > 10 mm`. The **commit** (green ring, G2) comes only from core. | 1.0 |
| D | **Select / highlight** | `generateCollisionShapes`, `arView.entity(at:)`, emissive outline plus a one-line label: name · state · source · age | 0.5 |
| E | **One explode control** | Toggle: offset each component along its `removal_axis` by bbox height + rank × 25 mm, `move(to:duration: 0.4)` | 0.5 |
| F | **Intelligent teardown** | Goal chip "Fix motor assembly" (V3 §7; access, inspect and correct the installation — not "replace") → `POST /control/goal {component}` → `twin.teardown.path`. Only the path explodes, numbered 1-2-3; others go to 0.15 opacity; the goal glows. | 0.75 |
| G | **Source / honesty labels** | Per-component chip: `TRACKED·OBJ` / `TRACKED·IMG` / `CAD·LAST SEEN mm:ss` / `UNKNOWN` (wireframe, no pose claim) / `TARGET`; red `MANUAL OVERRIDE` banner | 0.75 |

Floor and tracking (also A's): Xcode/ARView/USDZ load 1.0 · base lock + transforms + tests 1.0 · A1 + seated calibration 1.25 · A2 0.67 · sender + recorder 0.5 · `twin` v2 receiver 0.5.

### 9.2 STRETCH (only when every MUST item of the owner is green, behind a flag, and before 00:45)

Ordered by value per hour:
1. Deck X-ray opacity toggle (0.25 h).
2. Minimal component sheet: name, state, source, age, manual page number (0.5 h).
3. LiDAR scene-reconstruction occlusion so hands hide CAD (0.3 h) [verify].
4. Battery card in slot 4 (0.5 h).
5. B1 ArUco base (C, 2–2.5 h).
6. Deck A2 (second Mac).

### 9.3 CUT (do not start)

Scan/Identify flow · VLM product recognition · asset registry and online CAD resolution · live asset download · generic model search · image-to-3D · Explore mode (virtual camera) · X-ray slider · teardown timeline scrubber · full component sheets / part browser · manual thumbnails · in-phone voice or manual Q&A · rocket AR on the phone.

The product story (Devpost, pitch) may describe these as roadmap items using V1 §7. The build does not depend on any of them.

---

## 10. Intelligent teardown implementation

### 10.1 Provenance (shown on screen and in the bundle)

| Data | Source | Label |
|---|---|---|
| Component hierarchy and names | Studio MPD submodels → Blender → `component_frames.json` | `cad_derived` |
| Target poses `T_base_tgt` | same | `cad_derived` |
| Bounding boxes, seat heights, explode distances | CAD bbox | `cad_derived` |
| Install zone | CAD bbox of the chassis top + margin | `cad_derived` (margin authored) |
| `blocked_by`, `removal_axis`, `occludes`, alternate sites | written by us, checked on the physical rig | **`authored_demo_metadata`** |
| `requires` (bar needs motor correct; deck needs bar) | written by us; matches the service sheet | `authored_demo_metadata` |
| Step evidence ("The retaining bar locks the motor…") | **a one-page rover service sheet the team writes** (LEGO instruction PDFs contain no text). It goes through the existing K1 Opus extraction if time allows; otherwise authored evidence records. | `llm_extracted` from a team-authored doc, or `authored`; the doc is labelled "team-authored service sheet" |
| Goal "fix motor assembly" (V3 §7) | MUST: goal chip tap (deterministic). The free-text → Haiku stretch is CUT (voice is P2, V3 §8). | `user_selected` |
| Path deck → bar → motor | pure function over authored relations | `DETERMINISTIC` |
| Cross-check (optional, 20 min) | derive "A covers B" from CAD bbox (A above B, XY overlap); CI asserts authored `occludes` ⊇ derived | test only |

### 10.2 Bundle excerpt (`knowledge/rover-v1/bundle.json`, D)

```jsonc
"relations": [
  { "component": "c_motor", "blocked_by": ["c_bar", "c_deck"], "removal_axis": [0,0,1], "source": "authored_demo_metadata" },
  { "component": "c_bar",   "blocked_by": ["c_deck"],          "removal_axis": [0,0,1], "source": "authored_demo_metadata" },
  { "component": "c_deck",  "blocked_by": [],                  "removal_axis": [0,0,1], "source": "authored_demo_metadata" } ],
"occludes": { "c_deck": ["c_motor", "c_bar", "c_battery"], "c_bar": ["c_motor"] },
"task_graph.nodes": [
  { "id": "n_motor", "predicate": { "kind": "placed", "component": "c_motor", "pose": { "frame": "base", "T": [16], "discrete": { "site": "motor_bay", "rot_cw": 0 } } },
    "verifier": "object_pose", "requires": [], "source": "cad_derived" },
  { "id": "n_bar",  "…": "…", "requires": ["n_motor"], "evidence": ["ev_r2"], "source": "authored_demo_metadata" },
  { "id": "n_deck", "…": "…", "requires": ["n_bar"],   "evidence": ["ev_r3"], "source": "authored_demo_metadata" } ],
"task_flags": { "requires_goal": true }
```

### 10.3 Algorithm (`core/teardown.py`, pure, domain-agnostic)

```
access_path(goal):   visit(c): for b in sorted(blocked_by[c], by CAD top-z desc): if present(b): visit(b)
                     append c (once)        → deck, bar, motor
reassembly(goal)   = reverse(access_path) minus goal-if-replaced   → bar, deck
explode offset_i   = removal_axis_i × (bbox_height_i + rank_i × 25 mm)    (CAD-derived numbers)
```
Unit tests: the path for every component, absent blockers skipped, determinism under input order, and no cycles in the authored relations.

### 10.4 Planner additions (D; additive and flag-guarded; rocket snapshots must stay byte-identical)

1. **`blocked_by` from relations.** A non-correct component with a present blocker cannot be acted on, so `LIFT`/`REMOVE` the blocker first. This generalises 07's layer-2 covering rule, which stays as-is for the rocket.
2. **Inspect action.** `unknown(reason=hidden, occluder=X)` with X present and stable → head `LIFT X` / `TO CHECK <c>` (verb `LIFT`, reason `inspect`). Any other unknown → 07 §4 step 0 (uncertain/WAIT).
3. **`requires_goal`.** The HUD stays idle until `/control/goal` is set. Then the plan runs from world state as usual: teardown actions come from the inspect and blocked rules, and the fix comes from the diff.
4. **`/control/goal {component}`** (REST) and the `twin` v2 fields.

**What the demo shows (wording per V3 §7):** the goal is "fix the motor assembly". Exposing the motor reveals it is installed 90° off its documented orientation, so the diff yields `ROTATE`. GhostBuild verifies the installation state only; it makes no claim about motor function.

---

## 11. Corrected team plan

### 11.1 Capacity (be honest about it)

- **Supply:** 24 h − 3 h sleep − 1.25 h meals/kickoff − 1.5 h final submission/judging prep ≈ **18 h awake-work per person**, of which **≈ 16–17 h is engineering**. Team total ≈ 70 h.
- **Doc 13 already plans ≈ 83 h** (A 20, B 20, C 21, D 22.5). That gap exists before spatial.
- **V2 adds ≈ 21 h of spatial work and removes ≈ 23 h of P1:**
  - W4 Mac three.js twin, 9 h;
  - W6 iFixit live, 2.5 h → video/Devpost only;
  - W5 VLM label, 1 h;
  - A's panels 3 → 0 (moved to B at 1.5);
  - video 6 → 3.25 (split);
  - **W3 voice, 7 h → opportunistic P2**.
- **Net:** V2 is about cost-neutral against doc 13 and does not create the overage. The remaining overage is listed per person below with its release valve.

**The voice decision, stated plainly.** The spatial loop needs about 1.5 h of adapter work after 20:00 and about 3 h of bench and gate support. Only C, after G2, has that time, and only if C is not building the voice server. Keep voice, and the spatial loop has no owner: spatial becomes a visual add-on and cannot lead. **Recommendation:** demote voice. The G2 contextual menu (built first per D-19) asks the same answer engine, and the judge-initiated "Why?" moment survives as a temple-tap menu question.

### 11.2 Assignments and load (engineering h; shared = M3 0.5 + P0 freeze runs 1.0 + rocket footage 0.75)

| Person | Owns in V2 | Lane h | Shared h | Other (video, Devpost, rehearsal) | Total | vs ≈ 18 |
|---|---|---|---|---|---|---|
| **A** | Spatial app and rig (all of §9 MUST), motor asset and training kick-off, rocket Studio model + PDF (P0 support), spatial footage; demo captain | 13.2 (motor 1.5 · rocket 1.0 · floor 2.0 · rover + cards 1.5 · A1 1.25 · sender 0.5 · `twin` v2 + ghost + diff 2.0 · A2 0.67 · select/explode/teardown 1.25 · S7/S8 1.5) | 2.25 | final video 0.75 · Devpost 1.5 · captain 1.0 | **≈ 18.7** | at limit; no slack outside kill gates |
| **B** | G2 plugin, network, Beta (unchanged P0); menu; **M10 2D supervisor page** (from A); conditional iOS signing help (≤ 0.5 h at 16:00, only if S2 is red); PTT capture only if voice is reinstated | 17.0 (HUD 8 · ladder 3 · Beta QA 4 · menu 2 · −PTT 3 · +M10 1.5 · +help 0.5) | 2.25 | rehearsal 0.5 | **≈ 19.75** | +1.75 → valve: minimap polish, then glyph polish |
| **C** | P0 perception and testbed (unchanged until G2); **after G2 at 20:00: `adapters/spatial_pose`**, rig bench (lighting, thermal soak, drift), S6 with D; video rough cut v1 (05:45) | 19.0 (perception 12 · testbed 2 · hands 2 · adapter 1.5 · bench 1.5) | 2.25 | rough cut 1.5 | **≈ 22.75** | +4.75. Pre-existing (doc 13 C = 21). Valve: if G2 is late, C stays on P0 and the adapter moves to D after S6 prep, or spatial becomes visual-only. Hands helper → motion gate if V2 is not green by 16:00. |
| **D** | Contracts, planner/arbiter, compiler, answer engine (unchanged); **spatial contracts + transform fixtures (in the single 12:45 lock, V3 §4), rover bundle, planner additions §10.4, teardown, `/control/goal`, `twin` v2**; S6, S7 judge stand-in, S8 | 21.25 (planner 9 · contracts 2.5 · compiler 5 · answers 3 · spatial 2.75 · −iFixit) | 2.25 | eval + README 1.0 | **≈ 24.5** | +6.5. Doc 13 D was 22.5, so V2 adds +0.25. Valves in order: K1 → authored evidence (−2); answer engine to WHY/CAN_I/WHAT_DONE only (−1); review page → JSON diff (−0.5); spatial planner additions not merged by 00:45 → 45 s script only (−1.5). |

**Overall:** A and B fit. C and D are over, as they already were in doc 13. The valves are pre-agreed, triggered by clock time at standups and not by feel. **No spatial task is assigned to C or D before their P0 gates** (C after G2 at 20:00; D's first spatial work at 15:00 is fixture writing while K1 calls run).

### 11.3 Merge and isolation rules (adds to 04 §8)

1. **Separate process.** `adapters/spatial_pose/` runs on its own (phone → `ws://mac1:8790/pose` → adapter → core `ws role=vision`, `source: "spatial"`). The rocket never launches it.
2. **Core changes for spatial are additive and flag-guarded** (`--spatial`, or a bundle with `relations`/`task_flags`). CI requires byte-identical rocket HUD snapshots with the flag on and off.
3. **Merge cutoff for spatial changes to `core/`: Sun 00:45.** The 01:00–02:00 P0 freeze runs then validate them. After 02:00, only `spatial/` (phone) and `adapters/spatial_pose/` may change, until S8.
4. **The phone app is never on Mac 1. Training never runs on Mac 1 or A's Mac.**

---

## 12. Corrected critical-path timeline — AMENDED (contract lock 12:45 and D's slots per V3 §4.3; SP5 removed; sponsor overlay per 19 §11; final schedule in docs 14 and 21)

### 12.1 Feature estimates

| ID | Feature | Person-h | Wall-clock | Depends on | Owner | Earliest start | Latest finish | Fallback |
|---|---|---|---|---|---|---|---|---|
| SP1 | Motor: build + Studio + Blender USDZ + scale check + kick training | 1.5 | 1.5 | S0 toolchain, bricks | A | 12:15 | **13:45 (S1)** | A2 dead; motor card |
| SP2 | Motor training | 0.1 | 4–8 | SP1 | trainer Mac | 13:30 | 22:45 | motor card |
| SP3 | Rocket Studio model + PDF + LDraw export | 1.0 | 1.0 | bricks; brick list from C | A | 13:45 | 14:45 | D parses a sample `.ldr`; golden JSON from 11's layout |
| SP4 | App floor: ARView, USDZ, debug overlay, base lock B2, Swift transform tests | 2.0 | 2.0 | S0 signing; SP1 USDZ; 12:45 lock | A | 14:45 | **16:45 (S2)** | B helps 16:00–16:30; kill 17:30 → A to W4-lite |
| ~~SP5~~ | **REMOVED (V3):** spatial contracts and fixtures are part of the single 12:45 lock | — | — | — | D | — | — | — |
| SP6 | Bar, deck, chassis/battery, base card: build + Studio + USDZ + `component_frames.json` + cards printed and mounted | 1.5 | 1.5 | SP1 pattern; printer | A | 16:45 | **18:15 (S3)** | deck + bar only |
| SP7 | A1 tracking + seated calibration (F7) | 1.25 | 1.25 | SP4, SP6 | A | 18:15 | **19:30 (S4)** | kill → A to W4-lite (§16) |
| SP8 | `pose_observation` sender + session recorder; record 4 sessions | 0.5 | 0.5 | SP7 | A | 20:20 | 20:50 | adapter uses synthetic poses |
| SP9 | `adapters/spatial_pose` (state machine §6 + tests §6.4) | 1.5 | 2.0 | 12:45 lock; SP8 recordings at 20:50; G2 passed | C | 20:00 | 22:00 | spatial visual-only |
| SP10 | Rover bundle (nodes, authored relations, evidence from the service sheet) | 0.5 | 0.5 | `component_frames.json` (18:15); G3 work done | D | 21:00 | 21:30 | — |
| SP11 | Planner additions §10.4 + `core/teardown.py` + `/control/goal` + `twin` v2 emit | 1.5 | 2.0 | SP10 | D | 21:30 | 23:30 | not merged → 45 s script; teardown path precomputed in the bundle |
| SP12 | `twin` v2 receiver, ghost, diff arc/arrow, honesty chips | 2.0 | 2.0 | 12:45 `twin_v2` fixture | A | 20:50 | 22:50 | chips + ghost only |
| SP13 | A2 motor integration + test | 0.67 | 0.67 | SP2 done; SP7 | A (C as "hand") | 22:50 | **23:30 (S5)** | motor card |
| SP14 | Select + explode + teardown visualisation | 1.25 | 1.25 | SP12; SP11 or fixture | A | 23:30 | 00:45 | explode toggle only |
| SP15 | Rig bench: lighting, 10-min thermal soak, 5-min base drift | 1.5 | 1.5 | SP7 | C | 22:00 | 23:30 | — |
| SP16 | S6 replay loop (recorded poses → adapter → core → G2 simulator) | 1.0 × 2 | 1.0 | SP9, SP11 | C + D | 23:30 | **00:30 (S6)** | visual-only |
| SP17 | S7 live loop on real G2 | 0.75 × 2 | 0.75 | S6; P0 freeze; rocket footage | A + D | 02:45 | **03:30 (S7)** | add-on, visual only |
| SP18 | S8 selection: 5 clean 90 s runs | 0.75 × 2 | 0.75 | S7 | A + D | 03:30 | **04:15 (S8)** | rocket leads |
| SP19 | Spatial footage | 0.5 × 2 | 0.5 | S8, or S7 for add-on | A + D | 04:15 | 04:45 | none |
| SP20 | M10 2D supervisor page (HUD mirror, plan, turns, provenance, log) | 1.5 | 1.5 | `twin` stream | B | 17:00 | 21:30 | core-served text page |
| SP21 | W4-lite Mac three.js twin (**only if spatial is killed at S2 or S4**) | 2.5 | 2.5 | LDrawLoader; `twin` stream | A | 17:30 / 20:00 | 23:00 | 2D (SP20) |

### 12.2 Hour by hour

Doc 14's P0 items are unchanged unless marked **(V2)**.

**Saturday**

| Time | A (spatial + captain) | B (G2/Beta) | C (perception → spatial adapter) | D (core/knowledge → spatial core) | Trainer Mac | Gate |
|---|---|---|---|---|---|---|
| 09:00 | — | G2 borrow form | check in | check in; ask about the Studio-model rule **and** whether pre-designed physical rigs are allowed | idle | |
| 12:00–12:15 | kickoff | ← | ← | contracts + frame rule | | |
| 12:15–13:15 | **(V2) motor: build + Studio** | scaffold plugin; simulator | build board, mount camera, record | **core + spatial contracts LOCKED 12:45 (V3 §4.3)**; then planner TDD | | |
| 13:15–13:45 | **(V2) motor USDZ, viewport dims ±1 mm, kick training** | mock HUD; pick up G2 | rectification + LAB | LDraw parser on a sample `.ldr` | **motor job starts** | **S1 13:45** |
| 13:45–14:45 | **(V2) rocket Studio model + PDF** (moved from 12:15) | stub `.ehpk` → Beta; ladder; lock test | first live per-cell | merge mocks (**M1 14:30**); golden target from `rocket.ldr` at 14:45 | training | M1 14:30 |
| 14:45–15:00 | app floor starts | ← | | | | **G0 15:00** |
| 15:00–16:00 | app floor: ARView, USDZ, debug overlay | Even workshop | calibration + part fit; hands | K1 run + planner TDD (SP5 removed, V3 §4.3) | | |
| 16:00–16:45 | app floor: base lock + transform tests | menu → `g2_input`; **(V2) iOS help 16:00–16:30 only if A is red** | **V2 hands** | answer engine | | V2 16:00 · **S2 16:45** |
| 16:45–18:15 | **(V2) rover modules + cards + `component_frames.json`** | **(V2) M10 2D supervisor (17:00–18:00)** | bench under venue light | validator + review (**K1 17:00**) | ETA check | K1 17:00 · **S3 18:15** |
| 18:15–19:30 | **(V2) A1 + seated calibration** | plugin on hardware fed by real core; answer slot | tune; Plan B tags if failing | **first physical event → HUD on real G2** | | **S4 19:30** |
| 19:30–20:00 | ← all four: **M3** live replanning on hardware. **(V2) A films a 2-min insurance clip.** → | | | | ETA check | M3 |
| 20:00–20:20 | dinner | ← | ← | ← | | **G2 perception 20:00** · Even table closes |
| 20:20–20:50 | **(V2) sender + recorder; record 4 sessions** | first full Beta QA pass | **(V2) adapter on synthetic poses (SP9)** | bundle == golden | | |
| 20:50–22:00 | `twin` v2 receiver, ghost, diff | Beta QA; M10 finish (to 21:30) | adapter on A's recordings | **G3 21:00**; **(V2) rover bundle 21:00–21:30**; planner additions | done ≈ 17:30–21:45 | G3 21:00 |
| 22:00–22:50 | arc/arrow, chips | brightness/glyph/map polish | **(V2) rig bench: lighting, thermal soak, drift (SP15)** | planner additions + teardown + `/control/goal` + `twin` v2 | | adapter 22:00 |
| 22:50–23:30 | **(V2) A2 motor test** (C is the hand) | reconnect/lock hardening | ← assists S5 | ← | (deck job if a 2nd Mac) | **S5 23:30** |
| 23:30–00:30 | select + explode + teardown | hardening | **S6 replay with D** | **S6 replay with C** | | **S6 00:30** |

**Sunday**

| Time | A | B | C | D | Gate |
|---|---|---|---|---|---|
| 00:30–01:00 | finish teardown viz / buffer | Beta build | P0 tuning | merge spatial core additions (rocket snapshots byte-identical) | **core merge cutoff 00:45** |
| 01:00–02:00 | ← 5 consecutive clean **rocket** runs → | | | | **P0 FREEZE 02:00** |
| 02:00–02:45 | ← **(V2) primary submission footage, rocket:** 2 full takes; B through-lens, C table camera, Mac 2 screen record; copy to 2 drives + cloud before anyone leaves → | | | | **footage secured** |
| 02:45–03:30 | **S7 live spatial** (operator) | sleep 02:45–05:45 | sleep 02:45–05:45 | S7 (wears G2 as judge) | **S7 03:30** |
| 03:30–04:15 | **S8: 5 clean spatial runs** | | | S8 | **S8 04:15** (tests only; feature freeze 04:00 holds) |
| 04:15–04:45 | **spatial footage** (lead or add-on version) | | | ← | |
| 04:45–07:45 | sleep | 05:45 Beta build #N + QA | **05:45–07:15 video rough cut v1** (rocket, + spatial if captured) | sleep | v1 video exists 07:15 |
| 07:45–08:30 | final video: narration, captions | final QA | rehearse 5× (both scripts) | eval table + README | **Video 08:30** |
| 09:00–10:30 | Devpost | Even table: confirm Beta | rehearse with outsiders | Devpost technical section | |
| 10:30 | ← **code freeze + Devpost submitted** → | | | | |
| 11:00–12:00 | buffer; pick the lead script per §18 | final Beta pushed; QA signed | pack rocket + rover reset kits | tag release | **deadline 12:00** |

**Checks on this schedule:**
- Nobody holds two tasks in one slot (A's insurance clip happens inside M3).
- Every gate's work ≤ its window (§13).
- G0, G2, M3, P0 FREEZE, footage and the Beta schedule did not move.

---

## 13. Corrected gates — AMENDED (pass criteria per V3 §6; mm figures are diagnostics; clocks per V3 §8)

Each row's work fits its window.

| Gate | Clock | Owner | Window → work | Pass | Kill → fallback |
|---|---|---|---|---|---|
| **S0 Tooling** | Fri night | A + trainer owner | installs only | Spatial iPhone on iOS 27; Xcode 27 (macOS 26.6+ [C/verify]) signs a hello-world to it; `xcrun createml objecttracker -h` runs on the trainer; sample-job ETA recorded; Blender + ImportLDraw exports a sample LEGO model to USDZ with correct dims in the Create ML viewport | No iOS 27 phone → A2 dead (A1 only). No Xcode 27 Mac → spatial lane dead; A plans W4-lite |
| **S1 Motor asset + training** | Sat 13:45 | A | 12:15–13:45 → 1.5 h | Viewport dims within ±1 mm of callipers; origin at bottom-centre; job running; **ETA ≤ 22:45** | ETA later or tool error → A2 dead; motor gets a card; no retry |
| **S2 App floor** | Sat 16:45 (checkpoint 16:00) | A (B on call 16:00–16:30) | 14:45–16:45 → 2.0 h | App on device at 60 fps; base lock gizmo aligned with the mat edges (visually ≤ 2 mm / 1°); motor CAD upright, gear on the correct side, dims right; Swift tests 1–7 green; anchors survive the phase-2 re-run [verify] | Not on device by 17:30 → **spatial lane killed**; A builds W4-lite |
| **S3 Rig** | Sat 18:15 | A | 16:45–18:15 → 1.5 h | Deck, bar, chassis built to §7; cards mounted; `component_frames.json` + USDZs exported | Deck + bar only |
| **S4 A1 floor** | Sat 19:30 | A | 18:15–19:30 → 1.25 h | Bar and deck (and motor if carded) tracked simultaneously; overlay edge error ≲ 5 mm at 40 cm through 10 s each of translation, 90° yaw and lift; seated-calibration round-trip ≤ 4 mm / 3°; static jitter ≤ 1.5 mm / 1° | **Spatial lane killed** at 19:30 → A builds W4-lite 20:00–23:00 |
| **S5 Markerless motor (frontier)** | Sat 23:30 | A (C as hand) | 22:50–23:30 → 0.67 h | Motor tracked in **≥ 90% of visible frames** over a 10 s 90° rotation; **0 flips** > 30°; CAD visibly stays attached; re-acquires ≤ 1 s after a 1 s hand cover; F7 residual ≤ 4 mm / 3° after rotation; final `Δyaw` within 5° of the truth; **coexists with 2 image anchors at ≥ 30 fps** [verify] | Clip on the motor card; spatial cannot lead (§18) |
| **S6 Spatial loop (replay)** | Sun 00:30 | C + D | 23:30–00:30 → 1.0 h | The 4 recorded sessions through adapter → core → G2 simulator give exactly: `LIFT DECK` → `REMOVE YELLOW BAR` → `TURN MOTOR 90° →` → `PUT BACK YELLOW BAR` → `PUT BACK DECK` → `● VERIFIED`, plus the premature deck; §6.4 invariants green; rocket snapshots byte-identical | Spatial becomes visual-only (add-on) |
| **S7 Live loop** | Sun 03:30 | A + D | 02:45–03:30 → 0.75 h | 10 live rotate trials (with a 10-min run inside): **0 wrong HUD instructions**, physical change → G2 p50 ≤ 1.3 s, p95 ≤ 2.0 s; fps ≥ 30 and no thermal warning after 10 min; base drift ≤ 3 mm over 5 min | Visual-only add-on |
| **S8 Selection** | Sun 04:15 | A + D (D decides) | 03:30–04:15 → 0.75 h | **5 consecutive clean 90 s runs** (§14), ≤ 100 s each, 0 overrides, 0 wrong instructions | Rocket leads; spatial add-on if S7 passed |
| S-OC (optional) | Sat 16:30 start | whoever is free | 20 min | second Mac idle at 16:00 | skip |

**Two separate success metrics.** System success does not require markerless; frontier success does.

| Metric | Definition | Gates |
|---|---|---|
| **Spatial system success** | ≥ 2 moving modules tracked by **any honest mix** of A1/A2; pose → world → diff → G2 works; intelligent teardown works; current-vs-target visual works; 5 clean runs | S4 + S6 + S7 + S8 |
| **Markerless frontier success** | The motor `.referenceobject` passes S5 and holds through the S8 runs | S5 + S8 |

---

## 14. 90-second demo — SUPERSEDED / HISTORICAL (→ V3 §10.1; "Replace motor", "isn't broken" and `GEAR TO THE LEFT` are wrong)

**Set-up:**
- Rover on the mat, phone on the gooseneck, mirror on Mac 2 facing the second judge and the crowd.
- The judge wears G2; the captain holds the goal chip on Mac 2 or the phone.
- **Start state:** motor installed **90° wrong**, bar on, deck on. The motor has not been seen this session. Base re-locked.

| t (s) | Action | Phone / Mac 2 | G2 HUD | Captain |
|---|---|---|---|---|
| 0–10 | Captain lifts the phone and sweeps a 30° arc, then re-mounts it | CAD stays glued to the rover through the parallax. Chips: `DECK TRACKED·IMG` · `BAR HIDDEN` · `MOTOR NOT YET SEEN` | idle | "This is the exact CAD of this rover, registered to the real object. Not a scan." |
| 10–20 | Captain taps **Replace motor** | Intelligent teardown: deck floats up (1), bar (2), motor glows (3); chassis and battery dim | `LIFT DECK` / `TO CHECK MOTOR` | "It only takes apart what's between you and the motor." |
| 20–30 | Judge lifts the deck to the tray, then the bar | Deck CAD rises with the judge's hand; bar CAD follows the bar | `REMOVE YELLOW BAR` / `IT LOCKS THE MOTOR` | — |
| 30–45 | Motor exposed | Motor CAD amber at its tracked pose; cyan ghost at target; arc **90°**; chip `TRACKED·OBJ` | `TURN MOTOR 90° →` / `GEAR TO THE LEFT` | "You came to replace the motor. It just found the motor isn't broken; it's in 90° wrong." |
| 45–55 | **HERO:** judge turns the bare motor | **CAD motor turns with it; ghost stays fixed; readout 90° → 50° → 20° → 0°**, then the ring goes green | `●` → `PUT BACK YELLOW BAR` | (silence, then) "No marker on that motor." |
| 55–70 | Captain: "Put the deck straight back on." Judge does | Deck red: **premature**; bar ghost pulses at its target | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` | "It doesn't skip ahead. It replans from what you did." |
| 70–80 | Judge taps the temple → menu → **WHY?** (voice only if reinstated) | Turn log: question → answer → citation | `BAR LOCKS MOTOR` / `[SERVICE P.2]` | — |
| 80–88 | Judge lifts the deck, fits the bar, puts the deck on | Rings go green; motor `VERIFIED · NOW HIDDEN` | `PUT BACK DECK` → `● VERIFIED` / `MATCHES TARGET` | — |
| 88–90 | — | Honesty strip `TRACKED · CAD · TARGET` | dark, faint `●` | "The model didn't just show the repair. It stayed synchronised with reality and drove the plan." |

**Ad-libs:**
- Tracking drops mid-turn: the HUD holds. "It waits until it's sure."
- Something misreads: own it and point at the source chip.

## 15. 45-second demo — SUPERSEDED / HISTORICAL (→ V3 §10.2)

**Start state:** deck and bar on the tray, motor 90° wrong, goal pre-set, base re-locked.

| t (s) | Beat | HUD |
|---|---|---|
| 0–5 | "Exact CAD, locked to the real rover." Point at the ghost and the arc. | `TURN MOTOR 90° →` |
| 5–20 | **Judge turns the bare motor; the CAD follows; 90° → 0°.** "No marker on that motor." | `●` → `PUT BACK YELLOW BAR` |
| 20–30 | "Put the deck on first." → caught | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` |
| 30–40 | Bar, then deck | `● VERIFIED` |
| 40–45 | HUD dark. Closing line. | — |

**When the rocket leads** (doc 11 script unchanged), the **spatial add-on is +20 s**, and only if S7 passed: run the 5–20 s beat above. If only S4 passed (visual-only), show the CAD following the motor with no G2 claim, and say so.

---

## 16. Failure ladder

| Failure | Detected at | Becomes | Who does what next | Demo |
|---|---|---|---|---|
| A2 ETA too long or training error | S1 13:45 / ETA checks | Motor on A1 card | nothing; no re-train | spatial can't lead; add-on |
| A2 tracks poorly | S5 23:30 | Motor on A1 card | A continues with SP14 | add-on |
| A1 fails | S4 19:30 | **Spatial lane killed** | A builds **W4-lite** Mac three.js twin of the rocket 20:00–23:00, gate 23:00 | rocket + 3D twin, or 2D |
| App can't run on device | S2 (kill 17:30) | Spatial lane killed | A → W4-lite from 17:30 | rocket + twin |
| Base lock drifts or fails | S2 / S7 | B0 manual base | bannered `MANUAL OVERRIDE` | visual add-on only |
| Adapter or planner additions not ready | S6 00:30 / merge 00:45 | Visual-only spatial | no merges after 00:45 | add-on, no G2 claim |
| Live loop wrong or slow | S7 03:30 | Visual-only spatial | — | add-on |
| < 5 clean runs | S8 04:15 | Rocket leads | — | rocket + optional add-on |
| G2 (P0 perception) late at 20:00 | G2 | C stays on P0 | SP9 → D only if D's valves fired; else visual-only | rocket |
| Phone dies or overheats at judging | table | — | close the spatial app | rocket |
| Whole spatial lane dead | any | — | — | **rocket demo (11), unchanged** |

**Rule:** after a kill, the path is flagged off and nobody reopens it. The hours go to the named fallback.

---

## 17. Video and submission plan

| When | What | Owner | Why then |
|---|---|---|---|
| Sat 19:30 (M3) | **Insurance clip:** first real physical replan on G2, phone video, 2 min | A | proves the loop if everything later breaks |
| **Sun 02:00–02:45** | **Primary submission footage (rocket):** 2 full takes, through-lens (B), table camera (C), Mac 2 screen recording; copied to 2 drives + cloud on the spot | all four | **right after P0 FREEZE and before any spatial S7/S8 work** |
| Sun 04:15–04:45 | Spatial footage (lead or add-on version), phone mirror recorded on Mac 2 | A + D | only after S8/S7 decide what is honest to show |
| Sun 05:45–07:15 | **Rough cut v1:** a complete, submittable video from the rocket footage (+ spatial if captured); upload unlisted | C | a working submission video exists by 07:15 at the latest |
| Sun 07:45–08:30 | Final: narration, captions, honesty labels on screen | A | **Video 08:30** |
| Sun 09:00–10:30 | Devpost (AI usage, honesty map, eval table, "what we tried": cloud FoundationPose costing, EC2, extended training) | A + D | submitted 10:30 |

- **Nothing optional runs before 02:45.** Stretch items are allowed only under §9.2's conditions, and none touches P0 after 02:00.
- **The video shows only gated-in features.** If spatial is visual-only, the video says "tracked CAD, not yet wired to the planner".

---

## 18. Final go/no-go rule — AMENDED by V3 §9 (item 2 = S5 Gate A + B passed markerlessly; item 3 adds CORE-FULL merged by 00:45)

**Spatial becomes the judging lead only if every line is true at the 11:00 decision:**

1. **P0 FREEZE** was achieved and the **rocket footage is secured** (spatial never leads at P0's expense).
2. **S5 passed:** the motor is tracked **markerlessly** (frontier success). The bar and deck may be on cards.
3. **S6 and S7 passed:** tracked pose drives core and G2 live, with **0 wrong HUD instructions** in S7.
4. **S8 passed:** 5 consecutive clean 90 s runs, ≤ 100 s each, 0 manual overrides.
5. The base re-lock and the rover reset each work in < 40 s at the judging table, in one table rehearsal at 11:00.
6. The phone holds ≥ 30 fps with no thermal warning after a 10-minute run.
7. The rocket is set up and reset on the same table as the instant fallback.

**Otherwise:**
- 3 and 4 hold but 2 does not (motor on a card): the rocket leads, plus the +20 s spatial add-on.
- Only S4 holds: a visual add-on with no G2 claim.
- Nothing holds: rocket only.

**Who decides:** D calls it. Ties go to the rocket.

---

## 19. Reconciliation list — SUPERSEDED / HISTORICAL (→ V3 §13; applied in the final reconciliation)

| Doc | Edit |
|---|---|
| **00** | Add one line to the ambition-pass banner: "Spatial prototype per 18 v2; leads only under 18 v2 §18; voice demoted to opportunistic P2." |
| **01** | Even pitch: the "judge-initiated question" is the temple-tap menu (voice only if reinstated). Overall: add "on-device learned 6-DoF tracking (Create ML) feeding a verified planner" as the frontier claim, only if S5 passes. |
| **02** | Core experience item 7: "second person sees the phone's AR twin (if spatial passes) or the 2D supervisor". Out of scope: replace "LiDAR" with "LiDAR depth for state (LiDAR occlusion is cosmetic stretch only)"; keep "handheld scanning". |
| **03** | P1: **W3 voice → P2 (opportunistic)**; W4 → "W4-lite Mac twin, only if spatial is killed at S2/S4 (A)"; W5 → CUT; W6 → video/Devpost only. Add **W8 Spatial (A; C adapter; D core)** with gates S0–S8. P2: remove X1 and X2 (superseded). CUT list: replace "native apps", "LiDAR/ARKit sensor app" and "learned 6-DoF" with the narrower 18 v2 §9.3 items plus "learned 6-DoF on GPU/cloud". M10 owner A → B. Gates table: add S0–S8; make G1/G5 conditional on voice reinstatement. |
| **04** | Topology: add iPhone #2 `spatial/`, `adapters/spatial_pose` (port 8790), `twin` v2 consumer, Mac 2 = 2D supervisor + phone mirror. §2: amend "Rich UI on the phone?" (second, stand-mounted phone = instrument). §4: no new whitelist entries (the phone is not the plugin). §6: add rows for spatial phone down and adapter down. §7 honesty map: `TRACKED·OBJ`, `TRACKED·IMG`, `CAD·LAST SEEN`, `authored_demo_metadata`. §8: add the 18 v2 §11.3 rules (separate process, flag-guarded additions, 00:45 core merge cutoff, no training on Mac 1). |
| **05** | Add §1 frame `base` (same axes as `board`), the naming rule `T_A_B`, mm on the wire, row-major, yaw CCW+ vs `rot_cw`. Add `pose_observation` (§4.4). `observation`: `source += spatial`; component `reason ∈ {hidden, lost, out_of_view, never_seen, ambiguous}`, `stale`, `last_seen_ms`, `occluder`; `pose_source += {arkit_object, arkit_image, manual}`; `Pose.discrete {site, rot_cw}`. Bundle: `relations` (`blocked_by`, `removal_axis`), `occludes`, `task_flags.requires_goal`, `verifier += object_pose`, `source += authored_demo_metadata`. `twin` v2 fields (§4.5). Control: `POST /control/goal`. Example: `contracts/examples/spatial_transforms.json`. |
| **06** | §17: correct the learned-6-DoF row: "FoundationPose CUDA-only (still rejected); Apple iOS 27 object tracking is on-device and used for one spatial module; nothing changes for the rocket's brick state." |
| **07** | §2/§4: diff compares `Pose.discrete` when present; blocked from bundle `relations` (rocket covering rule unchanged); the inspect action for `unknown(hidden)`; `requires_goal`. Add `core/teardown.py` (§10.3) with tests. §8: rocket snapshots byte-identical with `--spatial` on and off; §6.4 invariants. |
| **08** | HUD lexicon additions for the rover (`LIFT DECK`/`TO CHECK MOTOR`, `REMOVE YELLOW BAR`/`IT LOCKS THE MOTOR`, `TURN MOTOR 90° →`, `X DECK TOO EARLY`/`LIFT IT · BAR FIRST`, answer `BAR LOCKS MOTOR`/`[SERVICE P.2]`); all within 20/28 characters. PTT section marked "only if voice reinstated". |
| **09** | Retitle "Supervisor view (2D, B) & phone AR twin". The Mac three.js twin becomes W4-lite (conditional). Add a phone section pointing to 18 v2 §9. |
| **10** | §4b: add spatial metrics: % visible frames tracked (motor A2, cards), flips, re-acquire time, seated-calibration residual, pose → G2 p50/p95, wrong instructions (target 0), drift over 5 min. Mark voice and iFixit rows conditional. Results table rows accordingly. |
| **11** | Add the 90 s and 45 s spatial scripts (§14–15), the rover layout and reset (§7.5), the +20 s add-on, and the §18 lead rule. Keep the rocket script as the default. Roles: A captain, C operator for the rover, B G2 wrangler, D second-judge host and §18 caller. |
| **12** | Add risks: A2 standard-mode quality (Apple recommends extended); image + object coexistence unverified; base bump/drift; thermal; slot starvation if > 4 images are loaded; occlusion-persistence misuse; C/D over-capacity (pre-existing) with the §11.2 valves. |
| **13** | Replace the table with 18 v2 §11.2 (hours, valves, voice demotion); the iOS-experienced teammate (B) gives conditional signing help only; trainer Mac rule. |
| **14** | Replace with 18 v2 §12.2: motor first at 12:15, rocket model at 13:45, spatial gates S1–S8, rocket footage at 02:00–02:45, sleep shifts (B/C 02:45–05:45, A/D 04:45–07:45), rough cut v1 by C at 05:45–07:15, video final at 08:30. |
| **15** | Repo layout: `spatial/` (Xcode), `adapters/spatial_pose/`, `testbed/rover/` (`rover.io`, `rover.mpd`, `component_frames.json`, USDZs, cards, service sheet). "What not to build": native apps are allowed for `spatial/` only. [verify] list: anchors across `run(_:)` without reset, image + `trackingObjects` coexistence, image-anchor axes, USD up-axis in RealityKit, Upright CLI flag, Xcode 27 macOS floor. |
| **16** | D-28 spatial prototype per 18 v2 (lead rule §18); D-29 second phone = instrument (amends D-07); D-30 Apple-native pose, no cloud, no EC2; D-31 motor-only markerless, cards elsewhere, base by fixed fiducial; D-32 authored demo metadata for blockers/axes; **D-33 voice demoted to opportunistic P2 to fund the spatial loop**; D-34 W4 replaced (W4-lite conditional). Assumptions: A-15 iOS 27 spatial phone; A-16 motor training ≤ 9 h on our trainer; A-17 image + object tracking coexist; A-18 B2 base drift ≤ 3 mm / 5 min. Remove V1's A-17 ("≥ 3 simultaneous tracks"). |
| **17** | §5 rows for FoundationPose and ARKit sceneDepth: pointer to 18 / 18 v2. §9 voice: "demoted per 18 v2 §11". |
| **18 (V1)** | Header note: "Superseded for execution by 18 v2: tracking scope §4, state rule §6, schedule §12–13, app scope §9, staffing §11. Architecture rationale (§2, §4 matrix, §5, §16) remains valid." |

---

## Final red-team questions

| Question | Answer |
|---|---|
| Are we building a live physical↔digital twin, or just an AR demo? | A twin, if S6/S7 pass: tracked poses become the world model, and the world model drives the plan and the HUD. Without S6/S7 it is an AR demo, and §18 then forbids leading with it. |
| Does moving the real motor visibly move its CAD counterpart? | Yes, phone-local at frame rate (no network in that loop): markerless if S5 passes, on a card otherwise. |
| Does tracked state actually influence the planner and G2? | Yes, through the adapter → `observation` → unchanged world/diff/planner, gated by S6 (replay) and S7 (live, 0 wrong instructions). |
| Can the judge break the physical state and watch it recover? | Yes. Deck before bar is caught as `premature` from positive evidence (bar seen on the tray, motor last seen verified), then replanned. |
| Is the explode view task-relevant? | Yes. Only the goal's blocking path separates, in order; the same path appears as G2 actions. |
| Is markerless used where it creates the most wow per hour? | Yes. One training job on the one part the judge turns by hand. |
| Have we avoided training parts nobody cares about? | Yes. The base uses a fiducial lock; the bar, deck and battery use cards or nothing. |
| Is every fallback honest? | Cards are visible and labelled `TRACKED·IMG`; hidden parts are `LAST SEEN`; authored relations say `authored_demo_metadata`; manual base and overrides are bannered and banned from lead runs. |
| Are Person A's hours physically possible? | ≈ 13.2 h lane + 2.25 h shared + 3.25 h other ≈ 18.7 h across 21 awake hours, one task per slot. There is no slack outside kill gates, which is why S2 and S4 have early kills that return A to W4-lite. |
| Does every gate have enough wall clock? | Yes; §13 lists window ≥ work for each. Training is checked against an explicit ETA deadline. |
| Is there a working submission video before optional late-night work? | Yes. Rocket footage at 02:00–02:45 right after freeze, before S7/S8; rough cut v1 by 07:15. |
| Can the rocket still win if spatial dies completely? | Yes, with the caveats stated: it loses the three.js twin (W4) unless spatial dies early (then A builds W4-lite) and loses voice (menu asks instead). P0, the compiler, cited answers and the dependency catch are all intact. |

---

## 20. Sources (checked 2026-10-16)

- Apple, `ARWorldTrackingConfiguration.trackingObjects`: iOS 27.0+; full frame rate of the selected `videoFormat`; significant power and processing load; `.referenceobject` only; `.arobject` only with `detectionObjects`; no mixing formats. developer.apple.com/documentation/arkit/arworldtrackingconfiguration/trackingobjects
- Apple, `maximumNumberOfTrackedImages`: max 4 simultaneous; first-observed images are tracked; a new one only after another leaves view; 0 → anchors update about every couple of seconds. developer.apple.com/documentation/arkit/arworldtrackingconfiguration/maximumnumberoftrackedimages
- Apple, "Using a reference object with ARKit in iOS": iOS 27 required; max 10 `.referenceobject` across detection + tracking; detection and tracking objects in one session; `isTracked` false when out of view; object anchors not auto-removed; `usdzFile`; ARView sample. developer.apple.com/documentation/visionos/using-a-reference-object-with-arkit-in-ios
- Apple, "Implementing object tracking in your app": Apple silicon + macOS 15 to train; Xcode 27-trained objects need iOS 27; photoreal, exact-scale USDZ; Object Capture via Reality Composer; viewing angles All/Upright/Front, restricted angles more accurate; extended recommended for high-frame-rate tracking; objects to avoid; "a few hours"; CLI since Xcode 26 (macOS 15.4+); `-m extended`. developer.apple.com/documentation/visionos/implementing-object-tracking-in-your-app
- Apple, `ARCamera.transform` (camera axes) and `ARCamera.intrinsics` (pixels, principal point from top-left). developer.apple.com/documentation/arkit/arcamera
- Apple, `ARImageAnchor` / `ARObjectAnchor` overviews. developer.apple.com/documentation/arkit
- Xcode 27 requirements (macOS Tahoe 26.6+, Apple silicon only; the beta said 26.4) [C, verify against Apple release notes]: [blakecrosley.com/blog/xcode-27-release](https://blakecrosley.com/blog/xcode-27-release) · [Apple Developer Forums thread 829619](https://origin-devforums.apple.com/forums/thread/829619)
- Community iOS 27 / visionOS 27 object-tracking demo (≈ 4 h standard on an M4 Max/128 GB; extended ≈ 7×; 6 objects max at high frame rate on Vision Pro) [C]: [github.com/robomex/visionOS-27-iOS-27-Object-Tracking-Demo](https://github.com/robomex/visionOS-27-iOS-27-Object-Tracking-Demo)
- AWS, Create ML object tracking on EC2 Mac (24 h host minimum), as cited in V1 §19.
- WWDC26 session 283, "Explore enhancements to visionOS object tracking": [developer.apple.com/videos/play/wwdc2026/283/](https://developer.apple.com/videos/play/wwdc2026/283/)
- OpenCV ArUco in `objdetect` (`aruco_detector.hpp`); iOS framework contents not confirmed [verify headers before B1]: [docs.opencv.org/5.0/main_modules/aruco__detector_8hpp.html](https://docs.opencv.org/5.0/main_modules/aruco__detector_8hpp.html)

---

PROTOTYPE SPATIAL — CORRECTED PLAN
