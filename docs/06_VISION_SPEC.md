# 06 — Perception Spec (P0 grid + P1 learned layers)

**Owner:** Person C. **Depends on:** 05_CONTRACTS (`observation`; field names `components`, `grid.cells` supersede older `parts`/`cells` wording below), testbed (§2). **Consumers:** core, twin.
**Ambition-pass change:** §1–§13 (the P0 grid pipeline) are unchanged and remain the **authority** for on-board placement. §14–§17 add hand-aware gating, foreign-object VLM labels and a P2 hero-tag 6-DoF, and list what was cut. Every layer has a flag, and P0 must run alone.

> **Final reconciliation (2026-10-16).** Only §1–§14 are built. The VLM foreign-object label (§9, §15) and the hero-tag 6-DoF float (§16) are **CUT**; StepFun is dropped. The rover's spatial state comes from the separate spatial lane (18 v3; `adapters/spatial_pose`), never from this pipeline, and nothing here imports it. C stays on this pipeline until G2 perception passes at 20:00; if it is red, C never starts the spatial adapter. A borrowed Hardware Lab Logitech webcam is the spare camera.

## Objective
Read the board's discrete physical state from a fixed overhead camera, ≥ 10 fps, and emit `observation` messages whose committed (`stable`) states are **never wrong**. When uncertain, say so (`?` cells / `unknown` parts); do not guess. P1 adds hand awareness (ML) and names for foreign objects (VLM); P2 adds continuous 6-DoF for one hero part.

## Non-goals
3D reconstruction, NeRF/3DGS, learned 6-DoF pose models on GPU/cloud (CUDA-only), training a detector, open-vocabulary detectors, LiDAR, handheld camera, Technic (see §17 for reasons). *(The rover's on-device ARKit tracking is a separate lane, 18 v3.)*

## 1. Approach (decided): fiducial-registered grid + per-cell colour + part fitting
Rejected alternatives and why (see 16_DECISIONS):
- **Full 3D reconstruction (A):** minutes per capture; iPhone LiDAR depth is 256×192 and noisy, so a 3.2 mm plate is at the noise floor.
- **VLM as primary perception (C):** 1–5 s variable latency, non-deterministic, poor grid/orientation accuracy. Published LEGO state benchmarks show weak VLM performance (LEGO Co-builder reports ~40% F1 for GPT-4o). *(Final: the VLM anomaly label is cut too; unknown regions stay `CLEAR UNKNOWN ITEM`.)*
- **YOLO-style detector:** needs 150–300 labelled images and still cannot see a 180° flip without a marker. Kept as no-go fallback only.

## 2. Testbed (C builds Fri night / Sat 12:00–1:30)
- **Base:** 16×16 plate (light bluish grey preferred; if only a green baseplate is available, drop green bricks), glued/taped to foam core.
- **Fiducials:** 4 ArUco markers, `DICT_4X4_50`, IDs 0–3, 30 mm, printed matte on cardstock, at the plate's corners on the foam core (ID 0 far-left, clockwise). Plus a **neutral grey patch** (printed 50% grey) next to marker 3.
- **Parts:** 10–12 classic System bricks; colours chosen to be far apart in LAB: **red, blue, yellow, black, + green or orange (not both)**. Footprints 2×2 and 2×4. Each `(colour, footprint)` unique. No white, no transparent, no grey bricks.
- **Orientation:** every 2×4 has a matte white **dot sticker (¼″/6 mm office dot) on the far-end stud** at rot 0. 2×2s are symmetric (`oriented: false`).
- **Layer 2:** one **cap** (black 2×4) bridging two layer-1 bricks in the target, placed so each covered brick keeps **≥ 2 visible studs and its dot visible**.
- **Build redesign (ambition pass):** the black cap bridges the **red 2×4 and the green 2×2**. With green missing, the cap still rests on red, so "cap back too early" is a real, detectable dependency violation.
- ~~**Hero part (P2):** the cap carries a 14 mm ArUco (ID 10)…~~ **CUT (final):** no hero tag on the cap.
- **Design rule:** in the target, parts are separated by ≥ 1 stud where possible (clean components).
- **Lighting:** own diffuse LED panel or small light tent; matte surfaces; camera tilted 5–10° off vertical to kill stud glare.

## 3. Pipeline (per frame)

| # | Stage | Method | Budget |
|---|---|---|---|
| 0 | Capture | `cv2.VideoCapture`, 1280×720; lock exposure/WB if the camera allows (`uvc-util`/v4l2), else rely on stage 4 | ~70–130 ms camera latency |
| 1 | Register | `cv2.aruco.ArucoDetector` + corner subpixel refine; homography from 4 markers; cache last good H | 5–15 ms |
| 2 | Rectify | `warpPerspective` → 640×640 (40 px per cell) | ~2 ms |
| 3 | Occlusion gate | occluded if: any marker missing **or** frame-diff energy in board ROI > τ_motion **or** > N cells `?` touching the board edge | ~3 ms |
| 4 | Light normalisation | per-frame gain from grey patch (scale so patch = calibrated LAB L,a,b) | <1 ms |
| 5 | Cell classify | centre 50% of each cell → glare mask (high L, low chroma) → median LAB → nearest centroid (ΔE2000 or Euclidean LAB) → class + distance + top-2 margin; `?` if distance > T or margin < m | ~1–3 ms |
| 6 | Part fit | §5 | <1 ms |
| 7 | Temporal filter | §6 | adds 300–500 ms by design |
| 8 | Emit | `observation` over WS (every frame; `stable` flag per §6); rectified JPEG to core at ≤ 4 Hz | — |

Target: ~0.6–1.0 s from hand leaving the frame to a committed state.

## 4. Calibration (`POST /control/calibrate`, ~30 s, run at the venue and at the judging table)
1. Place the **correct target build**.
2. Sample every target part's visible cells (known colours), baseplate cells, dot cells, grey patch.
3. Store centroids + per-class spread in `perception/calib.json`; set T per class from spread (e.g. 3σ, min floor).
4. Validate: re-classify the frame; must be 100% correct or calibration fails loudly.

## 5. Part fitting (deterministic)
Input: 16×16 class grid (`base`, colours, `dot`, `?`). Output: `PartState[]`, `unknown_regions[]`.
1. Attach each `dot` cell to the adjacent coloured component (it sits on top of a stud of that part).
2. Connected components (4-neighbour) per colour, dots included.
3. For each component, enumerate placements of that colour's parts (≤ 2 per colour: one 2×2, one 2×4) × rotations that **exactly tile** the component's cells. 0 solutions → whole component is `unknown_region` (reason `unmatched_shape`). >1 solution → `unknown` (reason `ambiguous`).
4. Rotation for oriented parts: footprint shape gives 0/180 vs 90/270; dot cell position picks within the pair. Dot missing on an oriented part → `unknown`.
5. Covered parts (layer 1 under the cap): visible cells are a subset of the footprint. Fit with the target-derived prior "cells under the cap's footprint are hidden". Accept if visible cells + dot are consistent with exactly one placement.
6. Any `?` cell inside a candidate footprint → that part `unknown`. Coloured cells that match no part colour → `unknown_region` (reason `unmatched_color`) → VLM candidate.
7. Parts of the library not found → `absent`.

## 6. Temporal stability
- Freeze while `occluded`; emit `stable: false`.
- Commit a new state only after **K = 5 identical consecutive fitted states** and **300 ms** since the occlusion gate cleared.
- Hysteresis: a committed cell flips only if the new class wins by margin m on 5 frames.
- If any part is `unknown` for > 1.5 s while not occluded → core shows `ADJUST BRICK` (never a guess).

## 7. Interfaces
- CLI: `python -m ghostbuild_perception --camera 0 --core ws://localhost:8787/ws?role=vision`
- Dev: `python -m ghostbuild_perception --video recordings/x.mp4 --print` · `python -m ghostbuild_perception --still frames/*.png --dump` (writes rectified + overlay PNGs).
- Recording tool: `python -m ghostbuild_perception.record --out recordings/` (raw video + timestamps) — record the venue lighting early for offline iteration.

## 8. Honest limitations (say these out loud if asked)
- Top-down only: a layer-2 brick placed flat at the same x,y as its target looks identical; we don't claim height sensing. Layer is inferred from the target.
- The dot sticker is a part fiducial for symmetric bricks; without it, 180° flips are unobservable from above by any method at this scale.
- Grid-snapped placement only. Off-grid / half-pressed bricks become `?` → `ADJUST BRICK`.

## 9. Open-world VLM module — CUT (final; StepFun dropped). Kept as history only.
- Trigger: an `unknown_region` with reason `unmatched_color`/`unmatched_shape` persists ≥ 1 s.
- Send: rectified crop (padded) + compact JSON context (part library, expected colours) → VLM. Ask for `{label ≤ 12 chars, is_lego_part: bool, confidence}` with a strict JSON schema.
- Model: **StepFun `step-5-preview`** if the hour-3 check passes (vision input works, p50 < 4 s, prize exists); else Gemini Flash or Claude Haiku 5.5. Key lives in core's env, never in the plugin.
- Result → `unknown_regions[].label` with `label_source: "vlm:<model>"` → HUD `REMOVE PEN`. Timeout 6 s → stays `UNKNOWN OBJECT`.
- Never used to decide part state.

## 10. Definition of done
- T1–T5 (10_EVAL_PLAN §2) pass under venue light.
- `make perception-test` passes on recorded fixtures (≥ 10 labelled stills incl. each defect type).
- Calibration at a new table < 60 s.

## 11. Mocked-development path
C develops against stills/videos before the board exists (photograph a printed grid). Core never waits for vision: it runs `--mock-vision`.

## 12. Fallbacks (in order)
1. Light box + recalibrate.
2. **Plan B: AprilTag caps** — 14 mm `tag36h11` stickers on smooth 2×2 tiles on each part; tag ID = part, tag rotation = orientation. 1–2 h switch; same `observation` contract.
3. Plan C: Duplo (2× pixels per part).
4. Go/no-go: if neither colour nor tags pass T1 by **Sat 6:00 PM**, cut to 6 parts, single layer.

## 13. Known risks (P0)
Venue colour cast; specular glare; sleeves/skin read as red/orange (mitigated by occlusion gate + `?`); camera bump (H recomputed every frame; "CAMERA MOVED" if marker reprojection error jumps); dot stickers peeling (carry spares).


---

# P1 — Learned perception (final, after red team; each layer behind a flag)

P0 must run identically with all flags off (`--no-learned`). Learned evidence may **veto** a commit for at most 1.5 s, never commit placement.

## 14. Hands — `--hands` (P0-hardening, gate V2 by Sat 16:00)
- **Primary:** whichever runs first within 30 min.
  - (a) **MediaPipe Hand Landmarker** in-process in Python (simplest; [verify] arm64 wheel + `.task` model).
  - (b) **Apple Vision** `VNDetectHumanHandPoseRequest` in a tiny Swift CLI (`perception/hands_helper/`). Python pipes 640×360 JPEG frames to it over stdin and reads JSON landmarks from stdout. This avoids two processes opening the same camera. Measured **~7 ms warm [M]**.
- **Fallback:** the original motion-energy gate.
- Fingertips and palm are projected through the board homography → `hands[].cells` (dilated by 1 cell). Footprints touching hand cells are **frozen**: no commits.
- **Pass (V2):** zero false commits over 20 hand insertions including hovering; no stuck freeze > 1.5 s after the hand leaves.

## 15. Foreign-object label — `--vlm-label` — CUT (final). Kept as history only.
- **Trigger:** an `unknown_region` (reason `unmatched_color`/`unmatched_shape`) persists ≥ 1 s while no hand is present.
- **Action:** send the padded rectified crop once per region to `step-5-preview` (if the StepFun gate passed) or Gemini Flash (thinking minimal), asking for `{label ≤ 12 chars, is_part_of_build: bool}`. Timeout 6 s → stays `UNKNOWN OBJECT`.
- **Output:** `unknown_regions[].label`, `label_source: "vlm:<model>"`. The planner uses it only to phrase `REMOVE PEN`. It never changes state.

## 16. Hero-part 6-DoF — `--tag` — CUT (final; superseded by the spatial lane, 18 v2 §19). Kept as history only.
- A 14 mm ArUco from a **separate ID range** (`DICT_4X4_50`, ID 10; board markers are 0–3), glued to a tile on the cap.
- `solvePnP(..., SOLVEPNP_IPPE_SQUARE)` with intrinsics from a one-time ChArUco calibration (`perception/camera.json`). Then `T_board_part = T_board_cam · T_cam_tag · T_tag_part`, slerp/EMA smoothing, snap to the grid within ~4 mm / 10°, status `lifted`, `pose_source: "tag"`.
- **Isolation:** P0 masks the detected tag quad before sampling cells. G6 requires P0 bench accuracy to be unchanged with the tag on.
- **Pass:** tag tracked in ≥ 80% of frames over a 10 s lift-and-rotate; jitter < 3 mm and < 3°; no pose flips.
- **Fail:** peel the tile off. P0 is unaffected.

## 17. Cut (do not build) — with reasons
| Item | Reason |
|---|---|
| YOLOE-seg + ByteTrack | 50 fps on MPS [M], but LEGO accuracy untested (P≈0.35). Open vocabulary adds little over a closed, known part set; GPU contention on the perception Mac. |
| Brickognize in-hand ID | Closed known part set; 0.5–0.8 s API latency [M]; minimal judge value. |
| SAM 2/3, EdgeTAM | Too slow on Mac (SAM 3 ≈ 2 s/frame CoreML [V]) or iOS-only integration. |
| Learned 6-DoF on GPU/cloud (FoundationPose etc.) | CUDA-only [V]; still rejected. Apple iOS 27 on-device object tracking **is** used, for one spatial module (the rover motor, 18 v3); nothing changes for the rocket's brick state. |
| Foreign-object VLM label (§15) | Cut in the final reconciliation: a VLM never decides state, and the label added little; StepFun dropped. |
| Hero-tag 6-DoF float (§16) | Cut: superseded by the spatial lane. |
| LiDAR / ARKit sensor app / Prompt Depth Anything | ~1 cm LiDAR noise vs a 9.6 mm layer step; P≈0.15 for ~8 h; layer is already known from the target prior. Optional zero-code Stray Scanner height test before Sat 20:00 for the Devpost "what we tried" section only. |

## P1 definition of done
V2 passed; P0 T1 re-run with `--hands` on shows unchanged accuracy; `--no-learned` reproduces P0 exactly.
