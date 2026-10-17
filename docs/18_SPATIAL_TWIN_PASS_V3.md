# 18 v3 — Spatial Twin Pass: Final Amendment

**Date:** 2026-10-16 (the day before the event).
**Status:** **authoritative for execution. It supersedes `18_SPATIAL_TWIN_PASS_V2.md` wherever the two differ.** Every V2 section this doc does not amend stays in force as written: frames and formulas §5, rig §7, training §8, app MUST list §9.1, teardown §10, isolation rules §11.3, video plan §17.
**Docs 00–17 are not modified by this pass.** §13 lists the edits the master reconciliation pass must make. *(Final reconciliation 2026-10-16: §13 has been applied to docs 00–19. Operational summary: `20_FINAL_IMPLEMENTATION_BIBLE.md`; clock checklist: `21_HACKATHON_CHECKLIST.md`.)*
**Tags:** **[V]** checked against Apple's documentation on 2026-10-16 (sources at the end) · **[I]** inference · **[D]** decision · **[verify]** check at hack time before depending on it.

---

## 1. Final spatial verdict

### PROTOTYPE SPATIAL — FINAL EXECUTION PLAN

The V2 architecture stands:
- the P0 rocket stays independent;
- the native iPhone RealityKit app;
- exact CAD of the rover;
- one markerless hero (the motor), with cards on the deck and bar;
- phone-local live rendering;
- tracked poses feed the world model, the planner and G2;
- intelligent teardown;
- voice at P2;
- spatial leads only if its gates pass.

None of the eleven amendments found an architecture blocker. They did find **six specification defects** in V2, and this pass fixes them:

1. The V2 state machine contradicts itself (rule 4 "as rule 3"), and it leaves stable poses with no rule at all (§3.1).
2. In V2, a part held in the hand can almost never reach LIFTED, because SETTLING is evaluated first (§3.1).
3. The V2 HUD line `GEAR TO THE LEFT` points the wrong way. The gear sits on +X, which is the judge's **right** (§7).
4. V2 says the contracts lock at 12:30, then changes them at 15:00 (§4).
5. The V2 demo claims the motor "isn't broken". Nothing in the system can support that (§7).
6. The G2 menu has no `WHAT NEXT?` item, but the judge is supposed to be able to ask it (§4.1, item 9).

---

## 2. Changes from V2

| # | Amendment | Change |
|---|---|---|
| 1 | State machine | The positional precondition `SEATED_AT_TARGET_SITE` is now shared, and yaw is classified only after it holds. LIFTED is tested before SETTLING, with its own debounce. Stable but unseated poses become `AMBIGUOUS(ambiguous_seat)`. REMOVED is any stable pose outside the install zone, whatever its tilt. The rules are written as pseudocode in evaluation order, with a reachability proof and 20 tests. |
| 2 | Contract lock | **One lock, at Sat 12:45.** It includes every spatial schema and fixture. V2's SP5 at 15:00 no longer exists. After the lock, a shared schema changes only with D plus every consumer owner approving. |
| 3 | Accuracy gates | Gates are now state-classification trials with **zero unsafe errors**, plus a tracking-stability check. Thresholds are derived from measured σ and the rig's physical separations. Millimetre figures become diagnostics. |
| 4 | Base lock | **Confirmed by Apple's documentation [V]:** calling `run(_:options: [])` with a configuration of the same type keeps the anchors you added and resumes tracking. The open question is now how far the base drifts, not whether the anchor survives. If the anchor somehow does not survive, the fallback is the base card tracked continuously. |
| 5 | Motor story | The goal is now "Fix the motor assembly". GhostBuild claims only what it measured: the motor is installed 90° off its documented orientation. The "not broken" claim is gone. |
| 6 | Fallback trade | P0 reliability and the closed loop are unchanged. The fallback demo is less rich than before (no W4 unless spatial dies early, no voice, no live iFixit, no VLM label), and this doc now says so. |
| 7 | Voice | P2, opportunistic, and never scheduled. Menu item 5 becomes `WHAT NEXT?`, so the judge can ask WHY, WHAT NEXT, CAN I and WHAT'S DONE from the G2 menu. |
| 8 | Release valves | 24 clock rules, each with an automatic action. A check that is not green at its clock counts as red. A killed feature is never reopened. |
| 9 | Generality proof | Optional and cheap: the real iFixit guide, pre-ingested offline through the same document path as the rover sheet. It appears in Devpost and the README only. |
| 10 | App scope | V2's seven MUST features. Nothing is added. |
| 11 | Demo wording | Both scripts are rewritten. Every claim is classified in §10.3. The gear direction is corrected. |

---

## 3. Final state machine (`adapters/spatial_pose`, per component, per sample)

### 3.1 Pseudocode (normative evaluation order)

`P` is `params.yaml`, an adapter-local file that is not part of any shared schema and can be tuned after the lock. `g` holds the F6 geometry from V2 §5.3. `H[c]` is the history of component `c`.

```python
def classify(c, s, H, now):
    # ── S. Session gate: applies to every component ─────────────────────────
    if s.camera.tracking != "normal" or s.base.state != "locked":
        return NO_COMMIT                       # emit board_visible=false, components=[]

    o = s.components[c]
    visible = o.tracking_state == "tracked" and not o.flip_rejected

    # ── V. Visible branch ───────────────────────────────────────────────────
    if visible:
        H[c].last_visible_ts = now
        g = geometry(o.T_base_component, P.target[c])           # dxy, z, tilt, dyaw, xy
        in_zone = g.xy in P.install_zone
        at_site = in_zone and g.dxy <= P.xy_site(H[c].committed)  # hysteresis: enter/exit
        z_ref = (P.z_tgt[c]      if at_site else
                 P.zone_top_z    if in_zone else
                 P.support_z(g.xy))                              # mat or tray height

        # V1 LIFTED: tested before motion, because a part held in the hand is never "stable"
        if g.z - z_ref > P.z_lift(H[c].committed) or (in_zone and g.tilt > P.tilt_lift):
            return LIFTED                                        # commits after 500 ms continuous

        # V2 motion / settling
        if o.lin_vel_mm_s > P.v_move or o.ang_vel_deg_s > P.w_move or not stable(H[c]):
            return SETTLING

        # V3 location: positive evidence the part is off the assembly
        if not in_zone:
            return REMOVED                                       # any tilt: e.g. lying on the tray

        # V4 seat quality inside the zone
        if g.tilt > P.tilt_tol:
            return AMBIGUOUS("ambiguous_seat")
        if not at_site:
            return PRESENT_MISPLACED
        if abs(g.z - P.z_tgt[c]) > P.z_tol:
            return AMBIGUOUS("ambiguous_seat")

        # ── SEATED_AT_TARGET_SITE ≡ tracked ∧ stable ∧ seated ∧ Δxy ≤ xy_site holds here ──
        if abs(g.dyaw) <= P.yaw_ok(H[c].committed):
            return PRESENT_CORRECT
        k = nearest(P.wrong_rots[c], g.dyaw)       # authored allowed wrong seats, e.g. motor {+90, 180, −90}
        if k is not None and abs(wrap(g.dyaw - k)) <= P.yaw_q:
            return PRESENT_MISORIENTED(k)
        return AMBIGUOUS("ambiguous_yaw")          # between bands, or a seat the part cannot physically take

    # ── N. Not visible this sample (tracking lost, limited, or flip-rejected) ──
    if H[c].last_visible_ts is not None and now - H[c].last_visible_ts < P.t_hold:
        return HOLD                                # typically a hand; nothing changes
    occ = covering_occluder(c, H)                  # authored occludes[x] ∋ c, x committed present,
                                                   # c's last pose (target pose if never seen) inside x's footprint
    if occ is not None:
        vc = H[c].last_visible_commit              # last state committed while c was visible
        if vc is not None and occ.present_since >= vc.ts:
            return HIDDEN_LAST_SEEN(occ, keep=vc.state)
        return HIDDEN_UNVERIFIED(occ)              # V2's "HIDDEN · NEVER SEEN"
    if not o.in_view:                              # last pose, or target pose if never seen, is outside the frustum
        return OUT_OF_VIEW
    if H[c].last_visible_ts is None:
        return NEVER_SEEN
    return LOST
```

**Why the rules cannot overlap.** The order is a strict decision list: the first `return` wins, so every sample gets exactly one state.

**Why no state is unreachable.** Each of the 14 classifier states has a test in §3.4 that produces it (MANUAL_OVERRIDE is an operator action, outside the classifier).

**Why there are no gaps.**
- The visible branch ends in an unconditional `return AMBIGUOUS`.
- The not-visible branch ends in an unconditional `return LOST`.

**Parameter invariants**, asserted when `params.yaml` loads. A violation means spatial cannot lead.

| Invariant | Why |
|---|---|
| `yaw_ok_exit + yaw_q ≤ 60°` | Leaves a band of at least 30° between CORRECT and MISORIENTED. 40° always lands in it (test T4). |
| `yaw_q < 45°` | A reading can never match two wrong seats. |
| `z_tol < z_lift_exit` | A seated part cannot read as lifted. |
| `tilt_tol < tilt_lift` | Same, for tilt. |
| `xy_site_exit < D_site / 2` | `D_site` is the shortest distance from the target bay to any other place a part can rest inside the zone (§6.1). |

### 3.2 State table

| State | Commits as (05 `observation` component) | Debounce | Planner may act on it |
|---|---|---|---|
| NO_COMMIT | `board_visible: false`, no components; core keeps its world; plan status `no_board` | — | no |
| LIFTED | `lifted` | 500 ms continuous | as `lifted`. A lifted part is never treated as placed. |
| SETTLING | nothing new | — | no |
| REMOVED | `absent`, `evidence: seen_off_assembly` | stability (5 samples and 300 ms) | yes (`missing`) |
| AMBIGUOUS | `unknown`, `reason: ambiguous_seat \| ambiguous_yaw` | stability | only `ADJUST <c>` / `SEAT IT SQUARE` |
| PRESENT_MISPLACED | `present`, `discrete.site: <site id \| "zone">` | stability | yes (`MOVE`) |
| PRESENT_CORRECT | `present`, `discrete: {site: target, rot_cw: target}` | stability | yes (satisfied) |
| PRESENT_MISORIENTED | `present`, `discrete: {site: target, rot_cw: rot_cw(k)}` | stability | yes (`ROTATE`) |
| HOLD | nothing new | — | no |
| HIDDEN_LAST_SEEN | the last state committed while visible, plus `stale: true`, `last_seen_ms`, `occluder` | after `t_hold` | as the kept state |
| HIDDEN_UNVERIFIED | `unknown`, `reason: hidden`, `occluder` | after `t_hold` | only the inspect action `LIFT <occluder>` / `TO CHECK <c>` |
| OUT_OF_VIEW | `unknown`, `reason: out_of_view` | after `t_hold` (immediately if never seen) | no |
| LOST | `unknown`, `reason: lost` | after `t_hold` | no (`SHOW <c>` / `TO THE CAMERA`) |
| NEVER_SEEN | `unknown`, `reason: never_seen` | immediate | no |
| MANUAL_OVERRIDE | 05 `source: manual_override` (an operator action, outside the classifier) | — | bannered; banned from lead runs |

### 3.3 Invariants (property tests; they replace V2 §6.4)

1. **Losing tracking never means absent.** `absent` is emitted only by REMOVED, which needs a visible, stable pose outside the install zone. No sequence that ends in "not visible" ever moves a component to `absent`.
2. No `ROTATE`, `MOVE` or `PLACE` is ever issued for a component that is SETTLING, HOLD, AMBIGUOUS, LOST, OUT_OF_VIEW, NEVER_SEEN or HIDDEN_UNVERIFIED.
3. While any component is unknown, the planner may issue only the inspect action. Otherwise the plan status is `uncertain` (07 §4, step 0).
4. A random-input fuzz test of 10,000 samples asserts that `classify` returns exactly one state each time and never raises.
5. When the configuration only changes from `--spatial` off to on, the rocket HUD snapshots stay byte-identical.

### 3.4 Tests (`adapters/spatial_pose/tests/`; the inputs are synthetic `pose_observation` sequences)

| # | Case | Input | Expected |
|---|---|---|---|
| T1 | Correct pose | seated at target; Δxy 2 mm, Δz 1 mm, tilt 2°, Δyaw +3° | PRESENT_CORRECT |
| T2 | 90° wrong | as T1, Δyaw +88° (gear pointing away from the judge) | PRESENT_MISORIENTED(+90), `rot_cw` 270; HUD `TURN MOTOR 90° →` / `GEAR TO THE RIGHT` |
| T2b | −90° wrong | Δyaw −91° | MISORIENTED(−90); HUD arrow reversed |
| T3 | 180° wrong | Δyaw 178°: motor, then deck (`wrong_rots {180}`), then bar (`wrong_rots {}`) | motor and deck MISORIENTED(180); bar AMBIGUOUS(`ambiguous_yaw`) |
| T4 | 40° | seated at target, Δyaw 40°, stable | AMBIGUOUS(`ambiguous_yaw`); no ROTATE |
| T5 | Wrong site, right orientation | in zone, Δxy 45 mm, Δyaw 0 | PRESENT_MISPLACED, never CORRECT |
| T6 | Lifted | 40 mm above target, hand-shaken (lin_vel 30 mm/s) | LIFTED commits at 500 ms, not at 300 ms |
| T6b | Pulled at an angle | in zone, tilt 35° | LIFTED |
| T7 | Seen on the tray | outside the zone, resting flat; and again lying on its side (tilt 90°) | REMOVED in both cases (`absent`, `seen_off_assembly`) |
| T8 | Hand occlusion | CORRECT, then not visible for 1.2 s, then visible again | HOLD only; **zero commits** |
| T8b | Long occlusion | CORRECT, then not visible for 3 s with no occluder present | LOST (unknown) at 1.5 s; never `absent`, never ROTATE; CORRECT again after re-acquire |
| T9 | Hidden by the deck, never seen | deck committed present at session start, motor never visible | HIDDEN_UNVERIFIED(deck); planner head `LIFT DECK` / `TO CHECK MOTOR` |
| T9b | Verified, then covered | motor committed CORRECT while visible, then the deck committed present | HIDDEN_LAST_SEEN, keeps CORRECT, `stale` |
| T9c | Covered by a part held in the hand | deck LIFTED and held over the motor for 3 s | LOST, not HIDDEN (a lifted part is not "present") |
| T10 | Tracking loss | camera `limited`; separately, base `unset` after a session interruption | NO_COMMIT for all components; plan `no_board` |
| T10b | Out of view | last pose outside the frustum | OUT_OF_VIEW |
| T11 | Half-seated | at the target site, 9 mm high, stable | AMBIGUOUS(`ambiguous_seat`) |
| T12 | Flip | yaw jumps 90° within 100 ms while ang_vel < 90°/s | flip-rejected and treated as not visible; HOLD |
| T13 | Being turned | seated at the target site, ang_vel 40°/s through Δyaw 90° → 0° | SETTLING throughout; zero commits until stable, then CORRECT |
| T14 | Never seen, nothing covering it | never visible, target pose in view, no occluder present | NEVER_SEEN |

All tests also run in the S6 replay over A's recorded sessions.

---

## 4. Final contract-lock plan

### 4.1 Lock manifest: **Sat 12:45, one event, all schemas** (`contracts/models.py` → `make contracts` green)

The lock moves from 12:30 to 12:45, once, to make room for the spatial schema. No consumer needs a contract before 13:15:
- B starts the mock HUD at 13:15;
- C emits live observations at 14:30;
- A starts the app floor at 14:45;
- D is the author.

If the lock is not complete at 12:45, the whole lock moves and D announces the new time. **The lock is never partial.**

| # | Locked item | Content (normative text in V2 unless stated) |
|---|---|---|
| 1 | Conventions | Frame `base` (same axes as `board`). The naming rule `T_A_B`, where `p_A = T_A_B · p_B`. **mm on the wire; metres inside the app.** 16 floats, **row-major**. Yaw is counter-clockwise-positive about +Z; `rot_cw = (−yaw) mod 360`. (V2 §5.1–5.2) |
| 2 | `pose_observation` | V2 §4.4 field for field, plus an optional `debug: object` that is producer-local and that consumers ignore. `in_view` uses the last pose, or the target pose if the component was never seen. |
| 3 | Pose-source enums | `base.source ∈ {image_lock, image_continuous, aruco, manual}` (`image_continuous` is the §5 fallback). Component `source ∈ {arkit_object, arkit_image, none}`. 05 `pose_source += {arkit_object, arkit_image, manual}`. `tracking_state ∈ {tracked, limited, lost, never_seen}`. `camera.tracking ∈ {normal, limited, not_available}`. `base.state ∈ {locked, unset}`. |
| 4 | Spatial states and reasons | `SpatialState` = the 15 names in §3.2. `reason ∈ {hidden, lost, out_of_view, never_seen, ambiguous_seat, ambiguous_yaw}`. `observation` gains `source += spatial`, plus per component `reason`, `stale`, `last_seen_ms`, `occluder`, and `evidence: seen_off_assembly`. `Pose.discrete = {site, rot_cw}`. |
| 5 | `twin` v2 | 05 §11 plus `spatial_state`, `teardown`, `highlight` and `honesty` (V2 §4.5). |
| 6 | `/control/goal` | `POST {component}` or `{clear: true}` → `{goal, path}`. Meaning: **access, inspect and correct the installation of `component`**. It is not "replace". |
| 7 | Authored relation fields (bundle) | `relations[] {component, blocked_by[], removal_axis[3], source}`; `occludes {id: [id]}`; `task_flags.requires_goal`; `verifier += object_pose`; `node.source += authored_demo_metadata`. |
| 8 | Fixtures (schema plus canonical values) | `contracts/examples/pose_observation.json`, `twin_v2.json`, `control_goal.json`, `bundle_rover_excerpt.json`, `spatial_transforms.json`. The last holds V2 §5.4 cases 1, 2, 3, 3b, 4, 5b and 6 with values copied from that table. Cases 5 and 7 are stored as property cases (inputs plus the invariant name), because their expected value is an equality, not a number. All fixtures are validated in Python and TypeScript CI. |
| 9 | G2 menu | Item 5 `REPEAT` becomes **`WHAT NEXT?`** (intent `WHAT_NEXT`, already in 05 §9 and 07). Items 1–4 are unchanged. REPEAT stays a voice-only intent. |

### 4.2 After the lock

> **AFTER CONTRACT LOCK, ADDITIVE IMPLEMENTATION MAY CHANGE; SHARED SCHEMA MAY NOT CHANGE WITHOUT D + ALL CONSUMER OWNERS APPROVING IT.**

**May change without approval (implementation):**
- adapter logic and `params.yaml` thresholds;
- planner internals;
- phone and 2D UI;
- new recordings, scenarios and fixture *instances* that validate against the locked schema;
- new tests;
- producer `debug` fields.

**Shared schema, which needs approval:** any field name, type, enum value, unit, frame, matrix order, message type, endpoint path or body, or menu ID. The approvers are D plus every consumer owner listed here.

| Schema | Producer | Consumers who must approve |
|---|---|---|
| Conventions (item 1) | D | A, B, C |
| `pose_observation` | A | C, D |
| `observation` spatial fields | C (adapter) | D |
| `twin` v2 | D | A, B |
| `/control/goal` | D | A, B |
| Bundle relations, `occludes`, `task_flags` | D | C |
| `spatial_transforms.json` | D | A, C |
| Menu IDs | B | D |

The approval is posted in team chat. D merges and runs `make contracts`. A schema change after 00:45 is refused outright (§8).

### 4.3 D's schedule: changed slots only

| Time | V2 | V3 |
|---|---|---|
| 12:00–12:45 | contracts (lock at 12:30) | **core plus spatial contracts and every fixture → LOCK 12:45** |
| 12:45–13:45 | planner TDD (from 12:15) | planner TDD |
| 13:45–14:30 | LDraw parser 13:15–13:45 | LDraw parser on a sample `.ldr`, then merge mocks (**M1 14:30**) |
| 14:30–15:00 | golden target at 14:45 | golden target from `rocket.ldr` |
| 15:00–16:00 | K1 run **+ SP5 spatial contracts and fixtures** | K1 run plus planner TDD (the 0.75 h SP5 used to occupy) |

D's total hours are unchanged. SP5 is removed from the V2 §12.1 table, and SP12 (A's `twin` v2 receiver) depends on the 12:45 fixture.

---

## 5. Final base-registration plan

**What Apple's documentation says [V]:**
- `ARSession.run(_:options:)`: calling it on a running session "transitions immediately to the new session configuration… By default, the session resumes device position tracking from the last known state and keeps any anchors already included in the session (those you've added manually with `add(anchor:)`…)".
- `RunOptions.resetTracking`: "When you call the `run(_:options:)` method with a configuration of a different type… the session always resets tracking"; "when you reset tracking, ARKit also removes any existing anchors". An `ARWorldTrackingConfiguration` re-run with another `ARWorldTrackingConfiguration` is the same type, so no implicit reset happens.
- `RunOptions.removeExistingAnchors`: "By default… the session keeps any `ARAnchor` objects that you previously added."
- `ARAnchor`: adding an anchor "helps ARKit to optimize world-tracking accuracy in the area around that anchor".
- Interruptions: "By default, if your session is interrupted… any virtual content in that session is likely out of place." An interruption happens when the session fails to receive camera or motion data, including "when the device is too busy".

**The interpretation is confirmed.** The open question is no longer "does the base anchor survive the re-run?" It is now **"how far does the retained base anchor drift during a run?"**

```swift
// PHASE 1: lock the base (≈ 2 s)
let p1 = ARWorldTrackingConfiguration()
p1.detectionImages = [baseCard]
p1.maximumNumberOfTrackedImages = 1
session.run(p1, options: [])                       // the first run ever may use [.resetTracking, .removeExistingAnchors]
// average T_world_fid over ≥ 1 s of isTracked frames  →  T_world_base = T_world_fid · T_fid_base   (V2 F1)
if let old = baseAnchor { session.remove(anchor: old) }        // re-lock: drop the previous base anchor
baseAnchor = ARAnchor(name: "gb_base", transform: T_world_base) // a GENERIC ARAnchor, not an image anchor
session.add(anchor: baseAnchor)
session.remove(anchor: baseCardImageAnchor)                     // avoid a stale image anchor that is no longer updated

// PHASE 2: production
let p2 = ARWorldTrackingConfiguration()            // SAME TYPE → no implicit reset [V]
p2.detectionImages = moduleCards                   // bar, deck (+ motor card in A1 mode); ≤ 4
p2.maximumNumberOfTrackedImages = moduleCards.count
p2.trackingObjects = motorRefObjects               // A2 mode only (iOS 27) [V]
session.run(p2, options: [])                       // NEVER .resetTracking, NEVER .removeExistingAnchors

// Every frame: read the base anchor's CURRENT transform from frame.anchors by identifier.
// Never cache T_world_base.
```

**Operational rules:**
- After `sessionWasInterrupted` or any `relocalizing` state, `base.state = unset`. Every component is then NO_COMMIT until the captain presses **Re-lock** (phase 1 again, then phase 2).
- Re-lock happens before every run, and only between runs. While phase 1 runs, the module and motor tracking stops for about 2 s.
- Re-running with `options: []` is the only call allowed after the first run. A code-review check greps for `.resetTracking` and `.removeExistingAnchors` outside the first-run path.

**Verification at S2 [verify]** (the API is documented, but this combination with `trackingObjects` is new):
1. After phase 2, `gb_base` is still in `frame.anchors` with the same identifier.
2. The base gizmo stays visibly aligned with the mat edges.
3. `T_world_base` before and after the re-run differs by ≤ 1 mm / 0.5°. This is a diagnostic, not a kill condition.

**Fallback if check 1 fails** (it would contradict the documentation): **B2-continuous.** Keep the base card in `p2.detectionImages` for the whole session, with `base.source = image_continuous`. The slot budget still fits:
- A2 mode: base, bar and deck = 3 of 4 slots;
- A1 mode: base, motor, bar and deck = 4 of 4, with no spare.

This costs base jitter, which the noise gate in §6 measures. B0 manual stays the last resort, and it is bannered and banned from lead runs.

**Drift.** Measured in S7 as a task check (§6). It does not need a millimetre figure.

---

## 6. Final task-driven accuracy gates

### 6.1 The distinctions the demo needs, and their physical separation

| Distinction | Physical separation on the rig | Signal |
|---|---|---|
| Motor at target vs 90° wrong | 90° of yaw | Δyaw |
| Motor seated vs lifted | ≥ 30 mm (lift protocol); the 6×6 bay is bordered by tiles, so the motor clutches only in the bay, at 0, 90, 180 or 270 | Δz above `z_ref`, tilt |
| On the assembly vs off it (tray or mat) | tray ≥ 60 mm outside the edge of the install zone (authored layout) | xy against `install_zone` |
| In the bay vs elsewhere in the zone | ≥ 48 mm (`D_site`, one motor footprint) | Δxy |
| Deck or bar present vs removed | at target vs on the tray | as above |

**The one rig addition** is the tile border around the motor bay. It costs no code, and it is what lets position thresholds stay loose: the motor cannot clutch at a one-stud offset, so the gate never has to resolve 8 mm.

### 6.2 Gate A: state classification (primary; this is the kill condition)

**Protocol.** Repeated physical trials on the real rig, at the demo camera pose and under the demo lighting. Run it at S4 for the cards and at S5 for the motor (or at S4 if the motor is carded). Each trial is scored from the adapter's committed output.

**Error classes:**
- **Unsafe error:** a committed actionable state that is wrong. Examples:
  - CORRECT ↔ MISORIENTED;
  - the wrong turn direction;
  - PRESENT while the part is lifted or off the assembly;
  - `absent` while the part is on the assembly or occluded;
  - any commit during a hand cover of 1.2 s or less.
- **Safe miss:** the system abstains (SETTLING, HOLD, AMBIGUOUS, LOST).

| Trials | n | Pass |
|---|---|---|
| Motor seated at target | 10 | ≥ 9 CORRECT |
| Motor seated 90° wrong (5 at +90, 5 at −90) | 10 | ≥ 9 MISORIENTED with the correct direction |
| Motor seated 180° | 5 | ≥ 4 MISORIENTED |
| Motor held still at about 40° on the seat | 5 | 0 commits of CORRECT or MISORIENTED |
| Motor lifted 30–60 mm and held 1 s | 10 | ≥ 9 LIFTED |
| Motor placed on the tray | 10 | ≥ 9 REMOVED |
| Hand cover 1.2 s (5 at target, 5 at 90°) | 10 | **0 state changes** |
| Hand cover 3 s | 5 | LOST or HOLD only; 0 `absent`, 0 ROTATE |
| Deck and bar each: at target, on the tray, lifted | 3 × 10 each | ≥ 9 correct per class |
| **All trials** | | **0 unsafe errors** |

**The motor-specific truth test** is the first two rows: **can it tell 0° from 90°, in the right direction, every time it commits?**

### 6.3 Gate B: tracking stability

Run at S5 for the motor. The image-card checks (rows 3 and 4) also run at S4.

| Check | Pass |
|---|---|
| Catastrophic flips (a rendered or committed yaw jump of more than 30° with no matching physical motion) over 10 hero rotations | **0** |
| Motor tracked during a 10 s 90° rotation | ≥ 90% of the frames in which it is visible |
| Re-acquire after a 1 s hand cover | ≤ 1 s, in ≥ 9 of 10 trials |
| "Convincingly attached": D, who did not build the app, watches the mirror through 3 rotations | no visible detachment |
| Motor A2 coexisting with 2 image anchors [verify] | ≥ 30 fps |
| S7 live loop (10 rotate trials, inside a 10-minute run) | **0 wrong G2 instructions**; after 10 minutes with no re-lock, the seated motor and deck still classify CORRECT (this is the drift test) |

### 6.4 Gate C: measured noise (thresholds come from data)

1. **Measure** at S4 for each card and at S5 for the motor. Record 10 s static at the target × 3 reseats, plus 10 s at 90° for the motor. Compute `σ_xy, σ_z, σ_yaw, σ_tilt`, and the bias `b` (the mean error after F7 calibration, across reseats). Then `e_q = 3σ_q + |b_q|`.
2. **Derive** and write `params.yaml`:

| Param | Rule | Clamp |
|---|---|---|
| `xy_site` enter / exit | `e_xy + 2 mm` / enter + 3 mm | enter between 6 and 15 mm |
| `z_tol` | `e_z + 2 mm` | 4–10 mm |
| `z_lift` enter / exit | `max(20 mm, 2·z_tol)` / enter − 5 mm | — |
| `yaw_ok` enter / exit | `e_yaw + 3°` / enter + 5° | enter between 8° and 20° |
| `yaw_q` | `e_yaw(at 90°) + 5°` | 15°–30° |
| `tilt_tol` / `tilt_lift` | `e_tilt + 3°` / 25° | 8°–15° / fixed |
| `t_hold`, stability, `v_move`, `w_move` | as in V2 §6.2 | — |

3. **Feasibility.** The §3.1 invariants must hold *without* a clamp binding against the data. If `e_yaw > 25°` or `e_z > 8 mm`, no valid bands exist and spatial cannot lead. Gate A would show the same failure.

**Diagnostics.** These are logged and shown on Devpost, and they are **not** kill conditions:
- static jitter ≤ 1.5 mm / 1°;
- F7 residual ≤ 4 mm / 3°;
- overlay edge error ≤ 5 mm at 40 cm;
- final Δyaw within 5° of the truth;
- base drift ≤ 3 mm over 5 minutes.

They replace V2's hard numbers in S2, S4, S5 and S7.

---

## 7. Final motor story

| | Wording |
|---|---|
| User goal (chip, spoken) | **"Fix the motor assembly."** The chip reads `FIX MOTOR ASSEMBLY`, and `/control/goal {c_motor}` means access, inspect and correct the installation. |
| Observation | `MOTOR · MISORIENTED 90°`. TRACKED pose vs TARGET from CAD; the readout is MEASURED LIVE. |
| Plan | `TURN MOTOR 90° →` / **`GEAR TO THE RIGHT`**. This corrects V2's `GEAR TO THE LEFT`: the gear is on +X at the target pose, which is the judge's right. The phone camera sits on the far side, so on the mirror the gear appears on the left. The captain never gives directions from the mirror. |
| Truthful claim | "It didn't assume what was wrong. It exposed the motor, measured how it's installed, and found it 90° off its documented orientation, so the fix is a rotation." |
| Never said | "The motor wasn't broken", "it saved you a replacement", "it diagnosed the motor". |
| If asked "Is the motor OK?" | "It checked the installation. Whether the motor runs needs an electrical test, and GhostBuild doesn't do that here." |

**Start state.** Motor at yaw +90°, with the gear pointing away from the judge. The reset sticker marks this pose (V2 §7.5, step 3).

---

## 8. Final release valves (automatic)

**Rules:**
- At each clock, D reads each check as green or red at the standup. **Anything not demonstrably green at the clock is red. "Almost" is red.**
- The action fires with no discussion.
- **A killed feature is never reopened.** Its hours go to the named fallback.

| Clock | Check | If red → automatic action |
|---|---|---|
| Fri night (S0) | iOS 27 spatial phone; Xcode 27 signs to it | No iOS 27 → A2 dead (cards only). No Xcode 27 Mac → spatial lane dead; A plans W4-lite. |
| Sat 12:45 | Contract lock (§4) | The whole lock moves; nobody codes against a partial schema |
| 13:45 (S1) | Motor training running with an ETA ≤ 22:45 | A2 dead; the motor gets a card; no retraining |
| 16:00 | V2 hands (C) | Motion-energy gate (doc 03) |
| 17:00 (K1) | Extraction green (doc 03) | Authored evidence for the rocket **and** the rover sheet. **Extraction code is frozen and not debugged.** The §11 generality proof is cancelled. |
| 17:30 (S2 kill) | App on the device with the base gizmo aligned | **Spatial lane dead**; A builds W4-lite from 17:30 |
| 18:15 (S3) | Rig built | Deck and bar only |
| 19:30 (S4) | Gate A for the cards (§6.2) | **Spatial lane dead**; A builds W4-lite 20:00–23:00 |
| **20:00 (G2)** | P0 perception green | **C stays on P0 entirely and never starts the adapter.** Spatial becomes **visual-only**; S6 and S7 are cancelled; nobody else picks up the adapter. |
| **21:30** | D: G3 green, rover bundle merged, and WHY answering on the fixture | Answer engine limited to **WHY, WHAT_NEXT, CAN_I, WHAT_DONE**; menu item 2 (`WHERE`) hidden; review page → JSON diff |
| 21:30 | M10 2D supervisor (B) | Core-served text page |
| 22:45 | Motor training finished | A2 dead; motor card |
| 23:00 | W4-lite (only if it is being built) | 2D supervisor (M10) |
| **23:30 (S5)** | Motor Gate A + B | Motor card; spatial cannot lead |
| **23:30** | D: CORE-FULL (`teardown.py`, inspect action, `requires_goal`, `/control/goal`) unit-green | D stops CORE-FULL and merges **CORE-MIN** only (discrete-pose diff, `source: spatial`, `twin` v2 emit). The 90 s spatial script is dead and spatial cannot lead; the +20 s add-on stays possible. |
| **00:30 (S6)** | Replay loop green (V2 §13) | **Spatial is visual-only. No more core spatial work of any kind.** |
| **00:45** | Core merge cutoff | Nothing spatial merges into `core/` or `contracts/` again. Stretch work (V2 §9.2) also stops. |
| **02:00** | P0 FREEZE | Nothing merges into P0 paths |
| 02:45 | Rocket footage on 2 drives + cloud | S7 does not start until the footage is secured |
| 03:30 (S7) | Gate B live row (§6.3) | Visual-only add-on |
| 04:00 | Feature freeze (product) | Bugs and rehearsal only. *(Final reconciliation: one isolated sponsor-client exception for `integrations/fetch_agent/` only, under the nine conditions in 19 amendment 4 / 03 §Gates.)* |
| 04:15 (S8) | 5 clean 90 s runs | The rocket leads |
| 08:30 | Generality proof validated (§11) | Dropped |
| 11:00 | Lead rule (V2 §18, as amended in §9) | Ties go to the rocket |

**Honest capacity note.** D is still planned at about 24.5 h against an 18 h supply, and C at about 22.75 h. **The plan expects the 17:00, 21:30 and 23:30 valves to fire.** They are written as conditions so that work which turns out green is kept, not because firing them would be a failure.

**Voice.** Hold-to-ask voice (W3) is **opportunistic P2**:
- It is never on the schedule.
- It may start only if every gate up to that clock is green **and** the person starting it has no assigned task in that slot.
- It must pass G1 and G5 and be merged, flag-off by default, before 00:45, because PTT touches the P0 plugin.
- Otherwise it is dropped. Its architecture (05 §10, 07 voice, 08 §16) stays documented.

The G2 contextual menu stays **P1**, using the same grounded answer engine.

---

## 9. Final fallback description

| | If spatial dies, at any time |
|---|---|
| **P0 reliability** | **Unchanged.** The rocket path never imports spatial code; it is frozen at 02:00 and filmed at 02:00–02:45. |
| **P0 closed loop** | **Unchanged.** Perception → world → diff → planner → G2 → verified replan. |
| **Fallback demo ambition** | **Somewhat reduced.** The engineering budget moved into spatial, so the rocket no longer gets the full W4 Mac three.js twin (unless spatial dies early), hold-to-ask voice, live iFixit, or the VLM foreign-object label. |

**If spatial dies late (after 19:30), the rocket demo still has:**
- physical observation;
- the world model;
- diff and premature detection;
- the replanner;
- the G2 HUD;
- verified replanning;
- the manual compiler (or authored evidence if K1 fired);
- the grounded, cited answer engine;
- contextual-menu questions (WHY, WHAT NEXT, CAN I, WHAT'S DONE);
- the 2D supervisor (M10);
- the offline generality proof (§11), if it validated;
- a spatial add-on whose level depends on the gates:
  - S4 + S6 + S7 passed: a +20 s card-based (or markerless) add-on with a G2 claim;
  - only S4 passed: a visual add-on with no G2 claim, said out loud;
  - otherwise: none.

**If spatial dies early** (S2 kill at 17:30, or S4 at 19:30), A builds **W4-lite** (2.5 h, gate 23:00). The rocket then also gets a 3D twin on Mac 2.

**Lead selection.** The V2 §18 rule stands, with three amendments:
- item 2 now means "S5 Gate A + B passed markerlessly";
- item 3 adds "CORE-FULL merged by 00:45";
- the rocket script uses the menu, not voice.

**Risk register additions** (for doc 12):
- standard-mode A2 quality (Apple recommends extended training);
- image + object coexistence;
- base drift (measured as a task check);
- session interruption under thermal or CPU load, which forces a re-lock;
- the gear-direction class of bug, now covered by test T2;
- C and D over capacity, handled by the automatic valves;
- the fallback richness trade described above.

---

## 10. Demo scripts

**Script rules (both scripts):**
- Only gated-in claims are spoken.
- "No marker on that motor" is said **only if S5 passed markerlessly**. With a carded motor, the line is "That card is how it tracks this part."

### 10.1 90-second script (spatial lead; only under §9's lead rule)

**Set-up.** Rover on the mat, phone on the gooseneck, mirror on Mac 2. The judge wears G2.

**Start state.** Motor at yaw +90° (gear pointing away), bar on, deck on, no goal set. The motor has not been seen this session. Base re-locked.

| t (s) | Action | Phone / Mac 2 | G2 HUD | Captain |
|---|---|---|---|---|
| 0–10 | Captain sweeps the phone through a 30° arc and re-mounts it | CAD stays registered through the parallax. Chips: `DECK TRACKED·IMG` · `BAR HIDDEN · NOT YET SEEN` · `MOTOR HIDDEN · NOT YET SEEN` | idle | "This is the rover's own CAD, the model we built it from, registered to the real rover. Not a scan." |
| 10–20 | Captain taps **Fix motor assembly** | Teardown: deck rises (1), bar (2), motor glows (3); chassis dims. Path chip `AUTHORED RELATIONS` | `LIFT DECK` / `TO CHECK MOTOR` | "Goal: fix the motor assembly. Using the rover's assembly relations, it opens only what's in the way." |
| 20–30 | Judge lifts the deck to the tray, then the bar | Deck CAD rises with the hand; the bar follows | `REMOVE YELLOW BAR` / `IT LOCKS THE MOTOR` | — |
| 30–45 | Motor exposed | Motor amber at its tracked pose, cyan ghost at the target, arc reading `90°` | `TURN MOTOR 90° →` / `GEAR TO THE RIGHT` | "It didn't assume what was wrong. Now it can see the motor: installed 90° off its documented orientation. So the fix is a rotation." |
| 45–55 | **HERO:** the judge turns the bare motor | **The CAD motor turns with it; the ghost stays fixed; the readout goes 90° → 50° → 20° → 0°**, then the ring turns green (core commit) | `●` → `PUT BACK YELLOW BAR` | (pause) "No marker on that motor." |
| 55–70 | Captain: "Put the deck straight back on." The judge does | Deck red, `PREMATURE`; the bar ghost pulses | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` | "It doesn't skip ahead. It replans from what you actually did." |
| 70–80 | Judge: temple tap → menu → **WHY THIS STEP?** | Turn log: question → answer → citation, labelled `TEAM-AUTHORED SERVICE SHEET` | `BAR LOCKS MOTOR` / `[SERVICE P.2]` | "That's cited from the service sheet we wrote for this rover." |
| 80–88 | Judge lifts the deck, fits the bar, puts the deck back | Rings go green; `MOTOR · VERIFIED 12:41 · NOW HIDDEN` | `PUT BACK DECK` → `● VERIFIED` / `MATCHES TARGET` | — |
| 88–90 | — | Honesty strip `TRACKED · CAD · TARGET · LAST SEEN` | dark, faint `●` | "The model didn't just show the repair. It stayed synchronised with reality and drove the plan." |

**Ad-libs:**
- Tracking drops mid-turn: "It waits until it's sure." The HUD holds.
- A misread: own it and point at the source chip.
- "Did it diagnose the motor?": give the §7 answer.

### 10.2 45-second script

**Start state.** Deck and bar on the tray, motor at +90°, goal `FIX MOTOR ASSEMBLY` pre-set, base re-locked.

| t (s) | Beat | HUD |
|---|---|---|
| 0–5 | "The rover's CAD, locked to the real rover. Goal: fix the motor assembly. It measured the motor: 90° off its documented orientation." | `TURN MOTOR 90° →` / `GEAR TO THE RIGHT` |
| 5–20 | **The judge turns the bare motor; the CAD follows, 90° → 0°.** "No marker on that motor." | `●` → `PUT BACK YELLOW BAR` |
| 20–30 | "Put the deck on first." → caught | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` |
| 30–40 | Bar, then deck | `● VERIFIED` / `MATCHES TARGET` |
| 40–45 | HUD dark. Closing line from §10.1. | — |

**When the rocket leads** (doc 11, with menu instead of voice), the spatial add-on is **+20 s**, using the 5–20 s beat above, and only if S7 passed. If only S4 passed: "Here's the CAD following the real motor. That part isn't wired to the glasses yet."

### 10.3 Claim audit

| Visible or spoken claim | Class | True when |
|---|---|---|
| "The rover's own CAD, the model we built it from" | CAD / KNOWN MODEL | S3 confirms the build matches the Studio file |
| CAD "registered to the real rover" | TRACKED (base lock) | base `locked`, not B0 |
| `DECK TRACKED·IMG`, `MOTOR TRACKED·OBJ` | TRACKED | live ARKit anchor |
| `BAR / MOTOR HIDDEN · NOT YET SEEN` | DETERMINISTIC (state machine) over AUTHORED METADATA (`occludes`) | — |
| Teardown path "opens only what's in the way" | DETERMINISTIC over AUTHORED METADATA | chip says `AUTHORED RELATIONS` |
| `LIFT DECK` / `TO CHECK MOTOR` | DETERMINISTIC (inspect rule) | — |
| `IT LOCKS THE MOTOR`, `BAR LOCKS MOTOR [SERVICE P.2]` | MANUAL EVIDENCE (team-authored sheet; AI-extracted if K1 passed, otherwise authored) | label on screen; spoken in 10.1 |
| Cyan ghost | TARGET (from CAD) | — |
| `90°` readout, "90° off its documented orientation" | MEASURED LIVE (TRACKED vs TARGET) | Gate A for the motor passed |
| `TURN MOTOR 90° →` / `GEAR TO THE RIGHT` | DETERMINISTIC (diff → planner) | test T2 green |
| "No marker on that motor" | TRACKED (A2) | **S5 markerless passed**; otherwise the alternative line |
| Green ring / `●` | DETERMINISTIC (core commit) | — |
| `X DECK TOO EARLY` | DETERMINISTIC: deck TRACKED plus bar TRACKED on the tray (REMOVED) | — |
| "Replans from what you actually did" | DETERMINISTIC | S6 + S7 |
| `MOTOR · VERIFIED 12:41 · NOW HIDDEN` | LAST SEEN | HIDDEN_LAST_SEEN |
| `● VERIFIED` / `MATCHES TARGET` | DETERMINISTIC over TRACKED (deck, bar) + LAST SEEN (motor) | — |
| "Stayed synchronised with reality and drove the plan" | Summary of TRACKED → DETERMINISTIC | S6 + S7 passed, which the lead rule requires |
| Goal chip | user-selected (no AI) | — |
| AI-inferred claims in the spatial demo | **none.** If an answer's evidence was Opus-extracted, the citation chip says `AI-EXTRACTED · VALIDATED` | — |
| Removed | "The motor wasn't broken"; "it found it isn't broken"; "exact CAD" without the "model we built it from" qualifier | — |

---

## 11. Optional generality proof (replaces live iFixit; never required)

**What.** On Friday, alongside the cached JSON (doc 13), save a print of the iFixit guide **158506** (DeLonghi EC220 pump) as a PDF. After the core is stable, run it **offline** through the **same** document path as the rover service sheet:

```
POST /control/ingest {uri: "knowledge/fixtures/ifixit_158506.pdf", kind: "service_pdf"}
```

It goes through the same Opus extraction and the same validator. The output is `knowledge/ifixit-158506/bundle.json`.

**Shown only in Devpost, the README and one video frame.** No UI, no live switching, no G2 flow:

```
GHOSTBUILD KNOWLEDGE COMPILER
ROVER SERVICE SHEET  ✓ compiled   n components · n steps · n warnings · n evidence refs
REAL REPAIR GUIDE    ✓ compiled   n components · n steps · n warnings · n evidence refs (quotes verified verbatim)
```

The caption reads "compiled, not executed", with the CC BY-NC-SA attribution.

**When and who.** D, at 07:45–08:30, alongside the eval table. The ingest is one batch call plus about 15 minutes of review.

**Kill conditions:**
- K1 fired at 17:00;
- the rover sheet did not compile;
- it is not validated by 08:30.

Any of these drops it. If it needs any code change, it is cut.

---

## 12. Exact diff against V2

| V2 section | Old decision | New decision |
|---|---|---|
| Header, §1 | "Corrected plan"; proposal status | Final execution plan; V3 is authoritative |
| §1 table | "Effect on the rocket: none on P0" | P0 unchanged; fallback richness reduced (§9) |
| §4.1 B2 | Anchor retention across `run(_:)` is [verify] | Documented [V]; exact phase 1/2 code; interruption → re-lock; B2-continuous fallback (§5) |
| §4.4 | `pose_observation` | Unchanged, plus an optional `debug` field; `in_view` defined for never-seen components |
| §6.1 rules 1–12 | Rule 4 "as 3"; SETTLING before LIFTED; no rule for stable-but-unseated; REMOVED needed "seated" | §3.1 decision list: shared `SEATED_AT_TARGET_SITE`; LIFTED first with its own debounce; `ambiguous_seat`; REMOVED is any stable pose off the zone; HIDDEN split into LAST_SEEN and UNVERIFIED |
| §6.2 | Fixed start values | Derived from measured σ (§6.4); V2 values become fallback defaults |
| §6.4 | 4 invariants | 5 invariants plus 20 tests (§3.3–3.4) |
| §7.2 motor | Square footprint seats at 4 yaws | Plus a tile border around the bay: the motor clutches only in the bay |
| §10.1 goal | "Replace motor" (`user_selected`) | "Fix motor assembly" = access, inspect, correct |
| §10.4 "what the demo shows" | "Goal was replace motor… yields ROTATE, not a swap" | "Exposing the motor reveals it is installed 90° off; the fix is a rotation." No swap counterfactual. |
| §11.1 | Voice demoted, as a recommendation | Decided: P2, opportunistic, never scheduled; menu item 5 = `WHAT NEXT?` |
| §11.2 C valve | "Adapter moves to D, or visual-only" | G2 red at 20:00 → visual-only, automatically; D never takes the adapter |
| §11.2 D valves | Listed; "by clock at standups" | Exact clocks in §8; expected to fire |
| §12.1 SP5 | D, 15:00–15:45 | Removed; folded into the 12:45 lock |
| §12.2 | Contracts locked 12:30 | **Lock 12:45**, all schemas; D's slots per §4.3 |
| §13 S2 | Gizmo ≤ 2 mm / 1°; anchors survive [verify] | Gizmo visibly aligned; anchor retained (kill → B2-continuous, not a lane kill) |
| §13 S4 | Edge ≲ 5 mm; F7 ≤ 4 mm / 3°; jitter ≤ 1.5 mm / 1° | Gate A for the cards; mm figures are diagnostics |
| §13 S5 | ≥ 90% frames, 0 flips, F7 ≤ 4 mm / 3°, Δyaw within 5° | Gate A for the motor (0° vs 90°, 0 unsafe errors) plus Gate B |
| §13 S7 | Base drift ≤ 3 mm / 5 min | Seated motor and deck still CORRECT after 10 minutes without a re-lock |
| §14 | "Replace motor"; "not broken"; `GEAR TO THE LEFT`; voice-or-menu WHY | §10.1: "Fix motor assembly"; measured-only claims; `GEAR TO THE RIGHT`; menu WHY; sheet authorship stated |
| §15 | Same issues | §10.2 |
| §16 | Failure ladder | Unchanged, with §8 clocks and a "never reopen" rule per row |
| §17 | iFixit "video/Devpost only" | Offline generality proof (§11), optional |
| §18 item 2 | S5 per V2 thresholds | S5 Gate A + B, markerless |
| §18 item 3 | S6 and S7 | Plus CORE-FULL merged by 00:45 |
| §19 | Reconciliation list | Superseded by §13 where they differ |

---

## 13. Final reconciliation delta (to apply to docs 00–18; not applied here)

Apply V2 §19 **as amended by this table**. Where a row here and V2 §19 differ, this table wins.

| Doc | Edit |
|---|---|
| 00 | Banner: "Spatial prototype per 18 v3. It leads only under 18 v3 §9. Voice is opportunistic P2." |
| 01 | Even pitch: the judge asks through the temple-tap menu. The frontier claim ("on-device learned 6-DoF tracking feeding a verified planner") is made only if S5 passed markerlessly. No "not broken" or diagnosis claims. |
| 02 | V2 §19 edits, plus: the spatial goal is "fix/inspect an installation", not "replace". |
| 03 | V2 §19 edits, plus: **W6 → "generality proof, offline, optional" (18 v3 §11)**; G7 → 08:30 offline validation; W3 → P2 opportunistic; add W8 Spatial with gates S0–S8 per 18 v3 §6 and §8; G1 and G5 apply only if voice starts. |
| 04 | V2 §19 edits, plus: the base-lock lifecycle (18 v3 §5) and "interruption → re-lock" in the failure table. |
| **05** | **Header: "LOCK SAT 12:45 — one lock" plus the §4.2 rule word for word, and the consumer-approval table.** Add every §4.1 item, including `reason` gaining `ambiguous_seat` / `ambiguous_yaw`, `base.source += image_continuous`, the optional `debug` field, and `/control/goal` semantics ("access, inspect, correct"). §8: **menu item 5 = `WHAT NEXT?`**. §3: NO_COMMIT uses `board_visible: false`. |
| 06 | V2 §19 edit only. |
| 07 | V2 §19 edits, plus: the §3.1 classifier is the spatial adapter's spec (the adapter lives outside core); CORE-MIN vs CORE-FULL split; menu WHAT_NEXT routes to the existing intent. |
| 08 | Menu item 5 `WHAT NEXT?`. Rover lexicon: **`GEAR TO THE RIGHT`** (not LEFT); `FIX MOTOR ASSEMBLY` chip text is phone-only. PTT section marked "only if voice starts (18 v3 §8)". |
| 09 | V2 §19 edits. |
| 10 | Spatial metrics: the Gate A confusion matrix (unsafe vs safe errors), the Gate B table, measured σ and bias, derived thresholds; mm figures as diagnostics. Generality-proof counts row. |
| 11 | Spatial scripts from 18 v3 §10 and the §10.3 claim audit. Rocket script: the "Why?" and "Can I…?" beats use the menu (no voice). The "+15 s iFixit" beat is replaced by "show the compiler card on Devpost" (no live switch). "D turns the twin" becomes "points at the 2D supervisor", or at the W4-lite twin if built. |
| 12 | §9 risk additions. |
| 13 | V2 §11.2 table, plus the §8 valve list and the capacity note. |
| **14** | **Contracts LOCKED 12:45.** D's slots per §4.3. The 15:00 SP5 row is removed. All §8 clocks, including 21:30, 23:30 and 00:30. The 07:45 generality proof is optional. |
| 15 | V2 §19 edits, plus the [verify] list: anchor retained after phase 2 (documented, confirm); image + `trackingObjects` coexistence; Upright flag name; USD up-axis; image-anchor axes. The `.resetTracking` grep rule. |
| 16 | V2 §19's D-28 to D-34, plus: **D-35** one contract lock at 12:45, with schema changes needing D plus consumers; **D-36** task-driven gates (0 unsafe errors) with σ-derived thresholds; **D-37** goal "fix motor assembly", no functional-health claims; **D-38** automatic clock valves, never reopened; **D-39** menu item 5 = WHAT NEXT?; **D-40** generality proof offline only. A-17 becomes "image + object tracking coexist at ≥ 30 fps". A-18 becomes "base drift keeps seated parts CORRECT for 10 minutes". **A-19:** anchors persist across a same-type `run(options: [])` [V; confirm at S2]. |
| 17 | §5 pointers to 18 v3; voice "P2 per 18 v3 §8"; iFixit "offline proof per 18 v3 §11". |
| 18 (V1) | Header: "Superseded for execution by 18 v3 (which amends 18 v2)." |
| 18 v2 | Header: "Superseded for execution by 18 v3 where they differ; unamended sections remain in force." |

---

## Critical self-check

| Question | Answer |
|---|---|
| Are the state rules mutually consistent? | Yes. It is a strict decision list, and yaw is classified only under `SEATED_AT_TARGET_SITE`. The load-time invariants keep the CORRECT, MISORIENTED and AMBIGUOUS bands disjoint. |
| Any unreachable states? | No. Each of the 14 classifier states has a test that produces it (§3.4); MANUAL_OVERRIDE is an operator action. V2's LIFTED-in-hand defect and its unseated gap are both fixed. |
| Is the contract lock actually a lock? | Yes. It is one event at 12:45 covering every spatial schema and fixture. SP5 at 15:00 is gone, changes need D plus every consumer, and nothing changes after 00:45. |
| Are the gate thresholds tied to physical distinctions? | Yes. Gate A tests the six demo distinctions, thresholds come from measured σ and the rig's separations, and mm figures are diagnostics only. |
| Does the base lock match Apple's documented lifecycle? | Yes [V]: a same-type re-run with `options: []` keeps the added anchors and resumes tracking. The coexistence of that call with `trackingObjects` is still [verify] at S2, with a fallback that needs no lane kill. |
| Does GhostBuild ever claim a part is "not broken"? | No. It claims only the measured installation state, and the "Is the motor OK?" answer says function is not tested. |
| Does a late spatial failure leave an honest, strong rocket demo? | Yes. P0 and the closed loop are intact, the menu answer engine works, and the reduced richness is stated (§9). |
| Are the C and D valves automatic? | Yes. Each is a clock with a red/green check and a fixed action; "almost" is red, and nothing is reopened. |
| Is there one unforgettable live moment? | Yes: the judge turns the bare motor and its CAD turns with it, 90° → 0°, then the glasses advance. |
| Was any new major feature added? | No. The additions are a menu relabel, a tile border on the rig, one fallback configuration and an offline batch run. App scope is V2's seven MUST features. |

---

**Sources (checked 2026-10-16, via developer.apple.com documentation data):**
- `ARSession.run(_:options:)`
- `ARSession.RunOptions.resetTracking`
- `ARSession.RunOptions.removeExistingAnchors`
- `ARAnchor`
- `ARSession.add(anchor:)` and `remove(anchor:)`
- `ARSessionObserver.sessionWasInterrupted(_:)`
- "Managing session life cycle and tracking quality"
- `ARWorldTrackingConfiguration.detectionImages` and `.trackingObjects`

V2 §20 sources remain valid.

PROTOTYPE SPATIAL — FINAL EXECUTION PLAN
