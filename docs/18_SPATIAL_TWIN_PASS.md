# 18 — Spatial Twin Pass

**Research date:** 2026-10-16 (the day before the event).
**Status:** proposal. Docs 00–17 stay authoritative until the changes in §18 are accepted. Nothing here touches the P0 loop.

> **⚑ SUPERSEDED / HISTORICAL (final reconciliation, 2026-10-16).** Superseded for execution by `18_SPATIAL_TWIN_PASS_V3.md`, which amends `18_SPATIAL_TWIN_PASS_V2.md`. Read `20_FINAL_IMPLEMENTATION_BIBLE.md` first.
> - **Still useful as rationale only:** §2 discoveries, §4 tracking matrix, §5 CAD pipeline, §12 AI role, §16 open-source leverage.
> - **Superseded and not to be built:** five trained modules and EC2 training (→ motor-only markerless, cards for deck/bar), the S1–S9 gates and the S9 lead rule (→ V3 §8 / V2 §18 as amended by V3 §9), the §9 app screens (scan/identify, explore, X-ray slider, component sheets, in-phone Q&A → V2 §9.1 seven MUST features), the §11 `scene_state` contract (→ `twin` v2 per V3 §4.1), the §13 demo script ("Replace motor", `GEAR TO THE LEFT` → V3 §10), and the §18 change list (→ V3 §13, applied in docs 00–19).
**Tags:** **[V]** verified against an official source (URLs in §19) · **[C]** community report, not official · **[I]** inference or estimate · **[D]** decision · **[verify]** check at hack time before depending on it.

---

## 1. Executive verdict

### **PROTOTYPE "GhostBuild Spatial" (layered Apple-native pose on iPhone) BUT DO NOT DEPEND ON IT**

It gets promoted to the lead demo only if it passes the selection gate S9 (Sun 03:00).

| Version | Quality /100 | Red-team P(win)* |
|---|---|---|
| Current GhostBuild (17, trimmed upgrade) | **84** | 41 |
| GhostBuild Spatial, if S9 passes (lead demo = live AR twin of a 5-module rover + G2) | **93** | ~50 |
| GhostBuild Spatial, risk-weighted (P(S9 passes) ≈ 0.5; otherwise the rocket leads and the phone shows the AR twin of the rocket) | **≈ 89** | ~45 |

*Same method as 17: P(core demo works) × P(win if it works). These are judgment estimates, not data.

**Why this verdict and not UPGRADE.** The decisive capability (markerless learned 6-DoF tracking of our own CAD parts on an iPhone) **became official in iOS 27** [V]. Nobody has published iPhone accuracy numbers yet, and training a reference object takes "a few hours" per object [V]. That is too new and too slow to bet the demo on. A **zero-training floor** (ARKit image anchors: 4 simultaneous moving 6-DoF tracks [V]) makes the spatial experience very likely to exist in some form. So we prototype it with a hard gate and keep the rocket loop as the guaranteed demo.

**Why not KEEP.** The previous pass cut "native apps", "ARKit" and "learned 6-DoF (CUDA-only)". For our hardware those cuts are now wrong (§2). With a phone on a stand, the "moving a real module moves its CAD" moment is achievable in about 12–16 person-hours on the Apple stack, with no GPU and no cloud on the demo path.

---

## 2. Most important discoveries (including what 17 got wrong or missed)

1. **iOS 27 brings Create ML object tracking to iPhone.** [V]
   - `ARWorldTrackingConfiguration.trackingObjects` is iOS 27.0+. It "tracks the object at the full frame rate of the selected `videoFormat`" and is meant "for moving or handheld objects".
   - `detectionObjects` is the low-power option for stationary objects.
   - **Max 10 `.referenceobject` files per session**, across both lists.
   - The same file works on visionOS and iOS.
   - Input is **a USDZ of the object**, trained in Create ML on an Apple-silicon Mac.
   - Apple's own guide lists "verifying that a tool is held and positioned correctly during an assembly process" and "troubleshoot… household items… with a virtual manual" as target uses. That is our product, described by the platform vendor.
   - **What 17 said:** "learned 6-DoF (FoundationPose etc.): CUDA-only → REJECT", "native apps → CUT". For our hardware that is no longer true.
2. **Training time is the binding constraint, not runtime.**
   - Apple: "The machine learning training can take a few hours, depending on the configuration of your Mac." Extended mode "takes several times longer". [V]
   - Community reports: ~4 h per object in standard mode on an M4 Max; extended ≈ 7× longer [C]. A forum user saw an "About 8 hr" estimate [C].
   - Consequences:
     - **Standard mode only.**
     - Train every module in parallel on separate Macs.
     - The CAD must exist by ~14:30 Saturday. The schedule is **asset-first**.
     - The CLI (`xcrun createml objecttracker -s in.usdz -o out.referenceobject`) exists since Xcode 26 [V], so remote Macs can do the training (AWS documents an EC2 Mac pipeline [V]).
3. **A zero-ML floor already exists: ARKit image anchors.** [V]
   - Up to **4 images tracked simultaneously**. "If the image moves, the framework updates the… transform", checked every frame. iOS 12+.
   - Each module gets a printed photo-texture card. The CAD attaches at a measured offset.
   - This is the honest "tag-assisted" tier (E). It removes most of the risk from the experience.
4. **FoundPose runs on Apple Silicon.** The official repo ships `conda_foundpose_mps.yaml` [V]. License CC BY-NC 4.0 [V].
   - It is single-image pose estimation from RGB plus a mask. It is a re-localizer, not a tracker.
   - Per 17 it was "CUDA-only". Only FoundationPose is (CUDA, PyTorch3D, nvdiffrast, NVIDIA Source Code License) [V].
5. **Learned unseen-object pose is still slow.** BOP 2024:
   - best accuracy FreeZeV2.1 at 24.9 s/image;
   - the practical Co-op at 0.8 s/image on GPU [V].
   - FoundationPose *tracking* is fast (746–1599 tracking QPS in TensorRT on Orin / 4060 Ti [V]). Its first-frame registration is the slow part.
   - None of these beats a native 60 Hz on-device tracker for our use. That is why the cloud route is rejected for the live demo (§4).
6. **A CPU, model-based, multi-body CAD tracker exists and is MIT-licensed:** DLR **M3T/ICG** [V]. It fuses region, depth and texture, handles multiple bodies and kinematic chains, and needs Eigen, GLEW, GLFW and OpenCV.
   - Drawbacks: it needs an initial pose, an RGB-D stream into C++, and OpenGL on macOS [verify].
   - It is a credible markerless Mac fallback in principle. At 8–12 h of integration it does not fit this hackathon. Listed as future work.
7. **"Phone = rich UI breaks Quiet Tech" (09) conflated two phones.** The *user's* phone (the Even app) stays in the pocket. A **second iPhone on a gooseneck stand** is an instrument facing the work, like the webcam.
   - The G2 wearer never needs to touch it.
   - The second judge, or the wearer between steps, can lift it to explore.
   - Phone = understand; G2 = execute.
8. **We already have exact hierarchical CAD without STEP.**
   - LDraw MPD submodels give the assembly hierarchy, names and transforms.
   - three.js `LDrawLoader` → `USDZExporter`/`GLTFExporter` (both in three.js, MIT [V]) gives per-module USDZ for Create ML and RealityKit.
   - Uniform-colour LEGO plastic makes the USDZ close to "photorealistic", which Apple asks for [V].
   - The STEP path (OCCT) is only needed for the generality story (§5).
9. **Symmetric, textureless or look-alike parts hurt every tracker.** Apple supports "objects to avoid" negatives in training [V]. Design rule: each module has one dominant colour plus one asymmetric feature. The 90° error must be *visible*.
10. **No independent iPhone accuracy measurement of iOS 27 object tracking was found.**
    - One developer reports a 6-object high-frame-rate limit on Vision Pro, not iPhone [C].
    - A default-rate anchor "never reports leaving view" [C].
    - Treat multi-object performance on iPhone as unknown until gate S6.

---

## 3. Best architecture

```
 BUILD TIME (Sat 12:15–19:00; cached; shown as PRECOMPUTED)
 Studio rover model ─► rover.mpd (5 named submodels = components)                [CAD / KNOWN MODEL]
      ├─► knowledge/ LDraw parser ─► task graph + target poses + blocks/insertion axes [DETERMINISTIC]
      ├─► three.js LDrawLoader → USDZExporter ─► <module>.usdz (metric) + rover_assembly.usdz
      │        └─► xcrun createml objecttracker (standard, parallel Macs/EC2) ─► <module>.referenceobject
      └─► instructions.pdf ─► Claude Opus 5.5 ─► per-step evidence (existing K1 path)      [REAL AI]

 LIVE
 ┌──────── iPhone #2 "GhostBuild Spatial" (iOS 27, RealityKit ARView, on a gooseneck stand) ────────┐
 │ ARKit world tracking (VIO + LiDAR)                                   [MEASURED LIVE]            │
 │  pose sources (any subset; the same output shape):                                              │
 │   T1 image anchors (≤4 moving, 60 Hz, printed cards)       ── floor, zero training  [TRACKED]   │
 │   T2 reference objects (trackingObjects, ≤10, full fps)    ── markerless, trained   [TRACKED]   │
 │   T0 manual tap-to-place (operator)                        ── last resort    [MANUAL OVERRIDE]  │
 │  local render @60 Hz: CAD entity parented to its anchor (no network in this loop)              │
 │  PoseFusion: per component pick best source → T_base_component, stability, age               │
 │  UI: scan · asset card · AR twin · explore (orbit) · X-ray · explode · isolate · ask           │
 └──────┬──────────────────────── ws role=spatial (own LAN) ───────────────────────────▲─────────┘
        │ pose_observation 10 Hz (≈1.5 KB)                                scene_state 4–10 Hz
        ▼                                                                               │
 ┌──────── MAC 1 core (unchanged authority model) ─────────────────────────────────────┴─────────┐
 │ adapters/spatial_pose: continuous pose → discrete predicates (installed / misoriented(90°) /  │
 │   misplaced / removed / unseen), stability vote, abstain                       [DETERMINISTIC] │
 │ WorldModel → Diff (incl. premature) → Planner → HUD ARBITER → G2       (same code as rocket)   │
 │ teardown planner: goal component → blocking path (from task graph)             [DETERMINISTIC] │
 │ answer engine (deterministic, cited) + Haiku intent/slots + P2 cited free-form   [DET + AI]    │
 │ P0 rocket path (webcam grid) untouched; the active task picks which adapter is authority        │
 └──────┬──────────────────────────────────────────────────────────────────┬─────────────────────┘
        │ hud                                                               │ twin/scene_state
        ▼                                                                   ▼
  iPhone #1: Even app plugin ─BLE─► G2 HUD               MAC 2: 2D supervisor + phone screen mirror
                                                          (+ three.js LDraw view of scene_state, optional)
```

**Five architectural rules:**
1. **The CAD-follows-module moment never leaves the phone.** The entity is a child of the ARKit anchor, so latency is one frame.
2. **Only core decides physical state.** The phone is a sensor and a renderer.
3. **Pose sources are interchangeable behind one contract** (§11). The tiers fail independently.
4. **The phone renders core's semantics** (target ghost, diff arrows, highlight, explode plan) and never computes its own plan.
5. **The rocket P0 path does not import, link or wait for anything in this document.**

---

## 4. Tracking technology matrix

Scores 1–5; 5 is best. "Damage" = what breaks if it fails (5 = nothing).

| | **A1 ARKit image anchors** | **A2 iOS 27 reference objects** | A3 ARKit `.arobject` scan (iOS 12) | B FoundPose (MPS) | C FoundationPose (cloud GPU) | D Hybrid: ARKit world + learned re-loc | E OpenCV ArUco/AprilTag on iPhone | F M3T/ICG (Mac CPU) | G Vuforia Model Targets |
|---|---|---|---|---|---|---|---|---|---|
| What | Printed photo card per module → ARImageAnchor | USDZ → Create ML → ARObjectAnchor | Scan in-app → detection only | DINOv2 template match, RGB + mask | RGB-D register + track, CUDA | A2/A1 between B/C fixes | `solvePnP` on `capturedImage` | Region + depth CAD tracker | CAD → model target, proprietary SDK |
| First output | **1–2 h** | 2 h code + **3–5 h training** | 2 h | 4–6 h [I] | 4–8 h (Docker image, 4090 caveat [V]) | 10+ h | 3–4 h | 6–10 h [I] | 3–5 h [I] |
| Integration | 4 h | 3 h on top of A1 | 3 h | 8 h | 10–14 h | 16+ h | 6 h | 10–12 h | 6 h |
| Update rate | 60 Hz [V] | full video fps [V] | low; stationary | ≤1 Hz [I] | 5–15 Hz end to end [I] | 60 Hz + 1 Hz fixes | 30–60 Hz | 30+ Hz [I] | 30–60 Hz [I] |
| Accuracy (our scale) | 4 (planar card; ≈mm when the card is visible) [I] | **?** (no iPhone data; gate S5) | 2 | 3 | 4 | 4 | 4 | 4 | 4 |
| Multi-object | 4 max [V] | ≤10 loaded [V]; simultaneous on iPhone unknown | many, but static | per call | 1 model/instance; N× cost | via A | many | many [V] | [verify] |
| Hardware | any ARKit iPhone | iOS 27 iPhone + AS Mac for training | any | Mac | NVIDIA cloud | both | any | Mac + RGB-D stream | iPhone |
| Cloud dependency | none | none at runtime | none | none | **hard** | partial | none | none | licence server [I] |
| Occlusion recovery | instant when the card reappears | re-detect [V] (hand-occlusion demo [V]) | slow | n/a (stateless) | re-register 1–3 s [I] | good | instant | needs re-init | good [I] |
| CAD needed | offset only | **photoreal metric USDZ** [V] | none (scan) | mesh | mesh | mesh | offset | mesh | CAD |
| Reset time | 0 | 0 | 0 | 0 | re-register | 0 | 0 | manual init | guide view |
| Judge wow | 3 (visible stickers) | **5** (markerless) | 2 | 2 | 4 | 4 | 3 | 4 | 4 |
| Product relevance | 3 | **5** | 2 | 4 | 4 | 5 | 2 | 4 | 4 (industry incumbent) |
| P(works for demo) | **0.85** | **0.45** | 0.5 | 0.3 | 0.25 | 0.15 | 0.7 | 0.25 | 0.4 |
| Damage if it fails | 4 (rocket demo intact) | 5 (fall back to A1) | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| **Decision [D]** | **BUILD (floor)** | **BUILD (frontier)** | skip | reject for hack | **reject for live demo** | reject | backup for A1 if the 4-image cap bites | future work | skip (proprietary, watermark, 20-generation cap [V]) |

**Cloud FoundationPose, costed so the rejection is evidence-based:**
- **Per frame:** RGB 640×480 JPEG ≈ 35 KB plus LiDAR depth 256×192 uint16 zstd ≈ 40–60 KB, so ≈ 90 KB [I].
- **Bandwidth:** at 10 Hz that is ≈ 7 Mbps of uplink, sustained, over a cellular hotspot (venue Wi-Fi is banned by 04 §4).
- **Latency:** ≈ 60–120 ms RTT plus 30–60 ms inference for 1–4 objects, so 150–300 ms end to end at 5–10 Hz [I].
- **Registration:** first-frame registration of 1–3 s per object needs a mask (SAM or a tap).
- **Cost:** RunPod RTX 4090 ≈ $0.34–0.74/h [V, varies by tier]. Money is not the problem. The 4090 needs a community CUDA 12 image [V].
- **Setup:** ≈ 4–8 h to first pose. The result is a network-dependent tracker that is slower and jumpier than what iOS 27 does on the device.
- **Verdict:** not on the demo path. It is acceptable as a Devpost "what we tried" item only if someone is idle.

---

## 5. CAD pipeline

### 5.1 Demo path (LDraw; what we build)
| Step | Tool | Output | Owner | Time |
|---|---|---|---|---|
| Model | BrickLink Studio (LeoCAD fallback) | `rover.io` → `rover.mpd` with **one submodel per component**, named `base`, `battery`, `motor`, `bar`, `deck` (+ `mast` optional) | A | 60–75 min |
| Hierarchy | `knowledge/ldraw.py` (existing) + submodel names | components, parent/child, transforms, step order, insertion axis per submodel | D | +1 h on K/G3 |
| Web asset | three.js `utils/packLDrawModel.mjs` [V] | `rover_Packed.mpd` (Mac view, optional) | A | 10 min |
| Mobile asset | Node script: `LDrawLoader` → per submodel `USDZExporter` (scale 0.0004 m/LDU, flip −Y) [verify materials export] | `base.usdz … deck.usdz`, `rover_assembly.usdz` (entity names = component IDs) | A | 1 h |
| Fallback asset | Blender + ImportLDraw (GPL-2.0, active Oct 2026 [V]) → USD export | same | A | 1 h |
| Scale check | Create ML viewport dimensions vs callipers (Apple's top failure cause [V/C]) | ±1 mm | A | 10 min |
| Train | `xcrun createml objecttracker -s motor.usdz -o motor.referenceobject` (standard; `Upright` angles for parts that stay upright, `All` for handheld ones; other modules as **objects to avoid**) [V] | 5 × `.referenceobject` | A starts, anyone babysits | 3–5 h wall, parallel |

### 5.2 Generality path (STEP; story + future, not built for the demo)
| Need | Best OSS | Licence | Notes |
|---|---|---|---|
| STEP → hierarchical glTF in the browser | **occt-import-js** (+ Online3DViewer for the viewer UX) | LGPL-2.1 / MIT [V] | Returns mesh tree + names; WASM; zero install |
| STEP → GLB in Python | **cascadio** (trimesh org, OCCT `RWGltf_CafWriter`) | [verify] | Keeps the XCAF assembly tree/names [I] |
| Desktop convert/inspect | **Mayo** (BSD-2), FreeCAD (LGPL-2.1) | [V] | Mayo exports glTF; FreeCAD does assembly + glTF |
| Code-CAD we author | **build123d** (Apache-2.0), CadQuery | [V] | Named assembly → STEP + glTF in one script; Claude Code can write it |
| glTF → USDZ | Blender (glTF-Blender-IO, Apache-2.0) → USD; Reality Converter [verify availability] | | RealityKit loads USDZ, not glTF |
| glTF on iOS without conversion | GLTFKit2 (MIT) | [V] | SceneKit bridge, **not** RealityKit → don't use |
| Web X-ray / explode built in | xeokit (AGPL-3.0) | [V] | Not worth a second renderer; X-ray/explode are ~50 lines each in three.js/RealityKit |

**Hierarchy we preserve end to end:** `asset → assembly → component (submodel) → part (LDraw line)`. The component ID is the **entity name** in USDZ, the **mesh userData** in three.js, the **reference-object filename**, and the **contract ID**. There is one ID everywhere and a CI test compares the four lists.

---

## 6. Interactive 3D experience (phone)

| Interaction | How | Honesty badge | Build |
|---|---|---|---|
| **Scan** | VisionKit `DataScannerViewController` (barcode/QR + text) → label `GB-ROVER-01` or a model number; "Identify" button sends one frame to core → Claude vision → product guess | MEASURED (code/OCR) or AI INFERRED (VLM) | 1 h |
| **Identify** | Core looks up `assets/registry.json` (§7) → asset card: level, components, docs, provenance | CAD / KNOWN MODEL + level tag | 0.5 h |
| **Load asset** | Bundled USDZ + referenceobjects (no runtime download) | PRECOMPUTED | — |
| **Register** | Base = `detectionObjects` (A2) or image card (A1) → defines `frame:"base"`; coaching text "walk around slowly" | TRACKED | in A1/A2 |
| **Live overlay** | CAD entity is a child of its anchor; 60 Hz | **CAD at TRACKED pose — not a scan** | in A1/A2 |
| **Orbit / zoom / pan** | Explore mode: `RealityView` with `content.camera = .virtual` + `.realityViewCameraControls(.orbit)` (iOS 18+ [V]) | CAD | 1.5 h |
| **Tap / select** | `arView.entity(at:)` hit test on collision shapes → component sheet | — | 0.5 h |
| **Identify part** | Sheet: name, role, state, source, age, relations, manual page thumbnail | per field | 1 h |
| **Isolate / hide** | Others get `OpacityComponent(0.12)` / `isEnabled=false` | — | 0.5 h |
| **X-ray shell** | Slider sets the deck/base opacity (0–1). Hidden parts render with a **dashed-outline material** + badge "CAD · LAST SEEN 12:41" or "CAD · NOT YET SEEN" | CAD / AI INFERRED | 1 h |
| **Explode slider** | Each component offset along its CAD insertion axis × rank × t | CAD | 1 h |
| **Intelligent teardown** | "Show me how to replace the motor" → core returns the blocking path `deck → bar → motor`; only those explode, numbered; everything else dims | AI INFERRED goal → DETERMINISTIC path | 1 h (phone) + 1 h (core) |
| **Teardown scrubber** | t ∈ [0, n] steps through the path; each stop shows the manual evidence + G2 line | CAD + manual | 0.5 h |
| **Target ghost** | Core's `target_pose` → translucent clone of the component at the target pose (0.3 opacity, no depth write) | TARGET | 0.5 h |
| **Current-vs-target** | Arrow (translation) / arc + "90°" label (rotation) between live and ghost | TRACKED vs TARGET | 1 h |
| **Component status** | Ring colour: green correct / amber misoriented / red premature / grey unseen / dashed uncertain | AI INFERRED (deterministic over TRACKED) | 0.5 h |
| **Uncertainty** | Wireframe if source = none or age > 500 ms; jitter readout in debug | — | in above |
| **Manual linkage** | Sheet "Manual p.7, step 4" → page thumbnail (pre-rendered by PyMuPDF) | AI-EXTRACTED / CAD-generated (existing provenance) | 0.5 h |
| **AI Q&A** | Ask button (iOS `SFSpeechRecognizer` on-device or text) → `/control/ask` with `{selected_component}` → deterministic answer + optional cited free-form (P2 MANUAL_SAYS) | per 05 §9 `basis` | 1 h |

**Polish if free [verify]:** LiDAR scene-understanding occlusion so real hands hide virtual CAD (RealityKit `.occlusion`). This is the one place LiDAR adds visible value at module scale.

---

## 7. Asset-resolution strategy

**Pipeline:** identify → resolve → label → load. Each step is honest about its source.

1. **Identify** (in order of trust): QR/barcode (MEASURED) > OCR'd model number (MEASURED) > user confirmation > Claude vision guess (AI INFERRED, always shown with "Is this a …? ✔/✕").
2. **Resolve** against `assets/registry.json` (committed), then optionally against live, ToS-clean APIs.

| Level | Label on screen | Source examples | What GhostBuild does |
|---|---|---|---|
| **L1** | **EXACT CAD** | Our Studio rover/rocket; manufacturer STEP (e.g. official Raspberry Pi mechanical models [I]) | Full tracking, explode, internals, exact diff |
| **L1c** | **COMMUNITY CAD** | LDraw Official Model Repository models of retail LEGO sets (CC BY [V]); open-hardware repos with STEP | Same as L1, badge says who authored it |
| **L2** | **REFERENCE MODEL** (exterior) + **MANUAL DIAGRAMS** | Apple Object Capture scan (USDZ from photos [V]); exploded service diagrams from a PDF | Register/track the exterior; internals = manual pages, never 3D |
| **L3** | **APPROXIMATE MODEL** | Category model (Objaverse/Sketchfab CC models, licence per model) | Context only; no diff, no tracking claims |
| **L3g** | **GENERATED** | SAM 3D Objects / image-to-3D (SAM licence [V]) | Placeholder silhouette; never internals; never diff |
| **L4** | **NO MODEL** | Docs only (iFixit 158506, CC BY-NC-SA [V]) | Existing guided mode + rocket-style physical loop where observable |

**Allowed live sources:** iFixit API 2.0 (public), Rebrickable API (free key; LEGO set → inventory) [verify ToS at the event], LDraw OMR downloads.
**Not used:** scraping GrabCAD, McMaster or Thingiverse pages, or any site whose ToS forbid automated download. In the demo, the registry holds three entries: `GB-ROVER-01` (L1), `rocket-v1` (L1), `delonghi-ec220` (L4).

**Image/video-to-3D:** no role in the demo. In the product story it is honest only as L2 measured exterior (Object Capture, which then feeds Create ML) or L3g placeholders. Generated geometry never reaches `target_pose`, the diff, or the hidden-part view.

---

## 8. Demo object recommendation

| Option | Exact CAD we control | 4–6 distinctive modules | Manipulation | Dependencies | Visible orientation error | Reset | Tracking-friendly | Repair analogy | Explode wow | Judge-safe | Total /50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A. Existing rocket/grid | 5 | 1 (flat bricks) | 4 | 4 | 3 (dot) | 5 | 1 for 6-DoF | 2 | 1 | 5 | 31 |
| B. LEGO Technic rover | 4 | 3 (grey, symmetric beams) | 3 | 4 | 3 | 3 | 2 | 3 | 4 | 4 | 33 |
| **C. LEGO System modular rover (custom)** | **5** | **5** | **5** | **5** | **5** | **4** | **4** | **4** | **4** | **5** | **46** |
| D. 3D-printed modular device | 5 | 5 | 4 | 5 | 5 | 4 | 3 (single-colour PLA, low texture) | 4 | 4 | 4 | 43, but needs a printer + 6–10 h of print time [I] |
| E. PC-like assembly (Pi 5 + case + fan + HAT) | 4 (official STEP [I]) | 3 (small, flat PCBs) | 3 | 4 | 2 | 3 | 2 | 5 | 3 | 3 | 32 |
| F. Retail LEGO set + LDraw OMR | 3 (community) | 2–3 (not designed as modules) | 3 | 3 | 2 | 3 | 4 | 3 | 3 | 4 | 31 (keep only as an L1c asset-resolution showcase) |

**[D] Pick C: the "GhostBuild Rover".** It is LEGO System, about 20 × 14 cm, built physically first and then modelled in Studio. Five rigid modules, each 6–15 cm, each with one dominant colour and one asymmetric feature:

| Module | Colour | Feature | Role / dependency |
|---|---|---|---|
| `base` (chassis + wheels) | dark grey + a printed photo card on the rear | wheels make it non-symmetric | frame reference; stationary (`detectionObjects`) |
| `battery` | blue | "+" tower on one end | sits in the bay; `requires: []` |
| `motor` | red | yellow output gear on **one side only** | 4×4 footprint, so it **fits rotated 90° or 180° on the studs** (the planted error) |
| `bar` (link/lock) | yellow | L-shape | bridges motor ↔ battery; `requires: [battery, motor correct]` |
| `deck` (shell) | white/black | antenna fin at the rear-left | covers battery + motor + bar; `requires: [bar]`; the X-ray target |

- **Repair story:** "replace / fix the motor". The path is `deck → bar → motor`.
- **Analogy, said aloud:** housing → retaining bracket → pump.
- The rocket stays the P0 rig on the same table.
- If no printer exists, D is impossible. If a printer *does* exist, D is no better, because single-colour PLA is low-texture.

---

## 9. Native iOS app spec — `spatial/` (Swift, SwiftUI + RealityKit ARView) — SUPERSEDED (scope → V2 §9.1)

**Targets:** iOS 27 (A2) with an iOS 18 floor (A1). Xcode 27 [verify that the team's Macs have the macOS version Xcode 27 needs]. iPhone Pro preferred (LiDAR occlusion and better VIO). Development builds only; no TestFlight.

### Screens
1. **Scan:** camera + DataScanner overlay → "Identify" → asset card sheet.
2. **Asset card:** product, level badge (§7), components list, documents, provenance (`graph_source`, `llm_vs_cad`), [Start].
3. **Live twin (AR, default):**
   - Top: a source chip per component (`IMG`/`OBJ`/`—`) and the base status.
   - Centre: overlay, ghost, arrows.
   - Bottom: G2 mirror line (`TURN MOTOR 90° →`), X-ray slider, Explode slider, Goal chip, 🎤 Ask.
4. **Explore (virtual camera):** the same scene graph off-camera. Orbit, part tree (`List` with eye toggles), isolate, teardown scrubber.
5. **Component sheet:** name/role/status (with badge)/source/age/relations/manual thumbnail/Ask.
6. **Debug (triple-tap):** fps, per-source counts, WS RTT, kill switches (`A1`, `A2`, `send poses`), `F` freeze.

### AR session
```swift
let cfg = ARWorldTrackingConfiguration()
cfg.detectionImages = cards                    // A1: ARReferenceImage per module (physical width set)
cfg.maximumNumberOfTrackedImages = 4           // hard max [V]
if #available(iOS 27, *), flags.a2 {
  cfg.detectionObjects = [baseRef]             // stationary, low power
  cfg.trackingObjects  = [motorRef, batteryRef, barRef, deckRef]   // ≤ 10 total [V]
}
cfg.sceneReconstruction = .mesh                // LiDAR only, for occlusion polish [verify]
arView.session.run(cfg)
```
- Mixing image detection and reference objects in one configuration is unverified. Gate S5 tests it. If they conflict, run A2 alone and keep A1 cards as the fallback build flag.
- **PoseFusion (per component, per frame):** prefer A2 if `isTracked`, else A1 if tracked, else hold the last pose with `tracking_state = lost`.
  - Compute `T_base_c = inverse(T_world_base) · T_world_c · T_anchor_cad` (`T_anchor_cad` = the measured card offset for A1; identity for A2).
  - Stability = translational/rotational velocity over 300 ms.
- **Rendering:** each component's CAD entity is re-parented to whichever anchor currently wins, with a 100 ms slerp on source switches to avoid visible pops.

### Data to core (ws `role=spatial`, own LAN like 04 §4)
- `pose_observation` at 10 Hz (§11), about 1–2 KB.
- `hello` with app build and capabilities.
- `ask` turns with `selected_component`.
- Optional 2 Hz 320 px JPEG for the supervisor panel.
- **No video stream and no depth upload.**

### From core
`scene_state` at 4–10 Hz plus on change: targets, diff items, head action, highlight IDs, teardown path, honesty labels, last answers.

### Renderer decision [D]
**RealityKit.** It is the only stack where ARKit anchors, USDZ, gestures, opacity and the iOS 27 object tracking sample all line up [V].
- SceneKit is legacy.
- Unity costs build and signing time and nobody on the team uses it.
- three.js in a WKWebView has no ARKit anchors.
- WebXR AR is not available in iOS Safari [I].

---

## 10. Mac / supervisor view

- **Mac 2 shows four things:**
  1. A **QuickTime/AirPlay mirror of the spatial phone**, so the crowd sees the AR twin.
  2. The existing **2D supervisor panels** (09 §3): HUD mirror, turns with citations, provenance, log, metrics.
  3. The **task graph with the teardown path highlighted**.
  4. Optional: a three.js LDraw view of `scene_state` from a fixed isometric camera. This is the old W4 code fed by the new contract. It is the fallback 3D view if the phone dies.
- **Rocket task:** the phone can show the rocket in AR as well. Put one A1 photo card beside the board at a known offset from the ArUco frame, and core's grid poses render as CAD on the real board. That delivers 09 §6 "AR ghost" (P2) for free.
- **Division of labour:** the phone is for exploring and understanding; the Mac is for supervising and explaining to the second judge; G2 is for executing.

---

## 11. Shared scene contract (backend-independent) — SUPERSEDED (→ `twin` v2, V3 §4.1)

Additive to 05. Nothing existing changes meaning.

```jsonc
// KnowledgeBundle additions (05 §2)
"asset": { "id": "GB-ROVER-01", "level": "EXACT_CAD", "authored_by": "team", "units": "m",
           "files": { "usdz": "spatial/Assets/rover_assembly.usdz", "ldraw": "testbed/rover/rover.mpd" } },
"components": [ { "id": "c_motor", "kind": "module", "name": "MOTOR", "parent": "c_base",
                  "mesh_ref": "motor", "insertion_axis": [0,0,1], "symmetry": "none",
                  "adapter_ref": { "ldraw_submodel": "motor", "refobj": "motor.referenceobject", "image_card": "card_motor" } } ],
"relations": [ { "kind": "blocks", "a": "c_deck", "b": "c_motor", "source": "cad_derived" },
               { "kind": "connects", "a": "c_bar", "b": "c_motor", "source": "cad_derived" } ],
"task_graph.nodes[].verifier": "object_pose"      // new enum value
```

```jsonc
// pose_observation — any pose backend → core (10 Hz)
{ "type": "pose_observation", "seq": 4411, "ts_ms": 0, "producer": "spatial-ios",
  "frame": "base", "base": { "tracked": true, "source": "arkit_object", "T_world_base": [16] },
  "components": [
    { "component_id": "c_motor", "T": [16], "source": "arkit_object",       // arkit_image | arkit_object |
      "tracking_state": "tracked", "stability": 0.94, "age_ms": 16,          // grid | tag | foundpose |
      "lin_vel_mm_s": 3.1, "ang_vel_deg_s": 1.2 },                           // foundationpose | m3t | manual
    { "component_id": "c_battery", "T": [16], "source": "arkit_object", "tracking_state": "lost", "age_ms": 41000 }
  ],
  "camera": { "T_base_cam": [16] } }
```
- `tracking_state ∈ {tracked, limited, lost, never_seen}`.
- `adapters/spatial_pose` maps a pose to an `observation` (05 §3) with `pose_source` widened to the enum above, and with the discrete `status`. That means **WorldModel, Diff, Planner and the HUD arbiter don't change**.

**Pose → predicate rules [D, tune at S8]:**

| Condition (in the base frame, vs target) | Status |
|---|---|
| ‖Δt‖ < 6 mm ∧ \|Δyaw\| < 12° ∧ tilt < 10° | `present`, correct |
| ‖Δt‖ < 10 mm ∧ Δyaw ∈ {90, 180, 270} ± 15° | `present`, misoriented (rot carried for `TURN MOTOR 90°`) |
| tracked, ‖Δt‖ ≥ 40 mm from target | `lifted`/`absent` |
| `lost` / `never_seen` while its blocker covers it | `unknown` + reason `hidden` → planner asks to expose it (`LIFT DECK · TO CHECK MOTOR`) |

**Commit rule:** commit only when stability > 0.9 (lin < 5 mm/s, ang < 5°/s) for **5 consecutive samples and 300 ms**. This is the same K/settle as the P0 grid. Abstain otherwise.

```jsonc
// scene_state — core → phone & Mac (4–10 Hz + on change)
{ "type": "scene_state", "seq": 902, "task_id": "rover-v1",
  "components": { "c_motor": { "status": "misoriented", "label": "AI_INFERRED", "pose_label": "TRACKED",
                               "target_T": [16], "delta": { "yaw_deg": 90, "mm": 2 } } },
  "head_action": { "verb": "ROTATE", "component": "c_motor", "hud": ["TURN MOTOR 90° →", "GEAR TO THE LEFT"] },
  "highlight": ["c_motor"], "teardown": { "goal": "c_motor", "path": ["c_deck", "c_bar", "c_motor"] },
  "honesty": { "geometry": "CAD_KNOWN_MODEL", "hidden_parts": "CAD_LAST_SEEN" }, "turns": [] }
```

**Honesty enum (UI must render it):** `MEASURED_LIVE`, `TRACKED`, `AI_INFERRED`, `CAD_KNOWN_MODEL`, `TARGET`, `APPROXIMATE_MODEL`, `PRECOMPUTED`, `GENERATED`, `MANUAL_OVERRIDE`, `CAD_LAST_SEEN`.

---

## 12. AI role: what a traditional CAD viewer cannot do

| A CAD viewer… | GhostBuild Spatial… | Where the AI is |
|---|---|---|
| Shows the design | Shows the design **at the pose reality is in**, per module, live | Learned 6-DoF (Apple's Create ML tracker): **real ML on the device** |
| Explodes everything | Explodes **only the dependency path to your goal** | Haiku maps "replace the motor / get the pump out" → goal + intent; the path is **computed** from the CAD-derived task graph |
| Has no opinion | Says **what is wrong** (rotated 90°, deck too early) and the **next physical action** | Deterministic diff + planner over tracked state (LLM-Modulo; nothing hallucinated reaches G2) |
| Has a parts list | Answers "what does this do / why remove it first / what does the manual say" **for the part you tapped, in its current state**, with a page citation | Opus-extracted manual evidence (K1) + answer engine; P2 Claude free-form with citations |
| Needs you to find the file | Goes from object to identity to asset level, with an honest label | OCR/barcode + Claude vision identification |
| Pretends the model is the object | Separates measured, tracked, inferred, CAD and generated **on screen** | — (the honesty map is the product) |

---

## 13. 90-second demo — SUPERSEDED / HISTORICAL (→ V3 §10; "Replace motor" and `GEAR TO THE LEFT` are wrong)

**Set-up:**
- The rover sits on a mat, with the phone on a gooseneck 45 cm away at 40°.
- The judge wears G2. The second judge watches Mac 2 (the phone mirror).
- **Start state:** the motor is installed **rotated 90°** under the deck. The phone has not seen the motor this session.

| t (s) | Action | Phone / Mac 2 | G2 HUD | Captain |
|---|---|---|---|---|
| 0–8 | Captain lifts the phone at the rover | Scan → `GB-ROVER-01` → card **EXACT CAD · 5 modules · manual 12 pp · graph from CAD** | idle | "It identifies the product and finds the best model it can, and labels exactly how good that model is." |
| 8–16 | Slow arc around the rover | CAD snaps on; chips `OBJ OBJ OBJ —`; the motor is grey, **"CAD · NOT YET SEEN"** | — | "That's the real CAD, locked to the real object. Not a scan." |
| 16–26 | Captain taps **Goal → Replace motor** | Intelligent teardown: deck lifts, bar lifts, motor glows, rest dims; X-ray slider fades the deck | — | "It only shows what's between you and the motor." |
| 26–30 | Phone back on the stand | — | `LIFT DECK` / `TO CHECK MOTOR` | "It can't see through the shell, so it asks you to look." |
| 30–38 | Judge lifts the deck | **Deck CAD rises in the air with their hand** (live); the motor is now tracked → amber ring, arc **90°** | `REMOVE YELLOW BAR` / `THEN TURN MOTOR` | "It just saw the motor's in sideways." |
| 38–48 | Judge removes the bar, then rotates the motor | **CAD motor rotates as the real one does**; ghost stays at target; readout 90° → 0° → green | `TURN MOTOR 90° →` → `PUT BACK YELLOW BAR` | (silence; point at the screen) |
| 48–56 | "Try putting the deck on now." Judge puts the deck on early | Deck ring red: **premature** | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` | "It doesn't skip ahead; it replans from what you did." |
| 56–64 | Judge holds the temple: "Why the bar?" | Turn log: transcript → intent → citation | `BAR LOCKS THE MOTOR` / `[MANUAL P.7]` | |
| 64–76 | Judge lifts the deck, places the bar, puts the deck on | All rings green | `PUT BACK DECK` → `● VERIFIED` / `MATCHES TARGET` | |
| 76–82 | — | Honesty strip: `TRACKED · CAD · AI INFERRED` | dark, faint ● | "And now it's quiet." |
| 82–90 | — | — | — | "Moving the real thing moved the digital one, and GhostBuild used that to get the repair right. Instructions tell you what to do. GhostBuild checks what you did." |

- **45-second version:** start with the deck off and the motor at 90°. Run rotate → deck early → verified.
- **Rocket add-on (+15 s):** point the phone at the board; the rocket CAD sits on the real bricks.

---

## 14. Feasibility gates (hard go/no-go) — SUPERSEDED (→ V3 §6 and §8)

Owner **A** = the spatial lane (see §18/13 for staffing; Swift bootstrap by the team's iOS developer).

| Gate | Clock | Owner | Exact prototype | Build | Pass metric | Kill → fallback | Unlocks |
|---|---|---|---|---|---|---|---|
| **S0 Tooling** | **Fri night** (installs only) | A | iPhones on iOS 27; Xcode 27; `xcrun createml objecttracker -h` runs; Apple sample USDZ trains (tool familiarity, not our asset) | 1 h | CLI starts a job; app signs to the device | No iOS 27 → A2 is dead; A1 only | A2 |
| **S1 CAD** | **Sat 14:15** | A (+D for submodels) | Rover built + `rover.mpd` with 5 named submodels → 5 USDZ at metric scale | 2 h | Create ML viewport dims within ±1 mm of callipers; names = IDs | 14:45 → train whatever exists; rest A1-only | S2, S7 |
| **S2 Training kicked** | **Sat 14:45** | A | 5 parallel `objecttracker` jobs (standard) on Mac 2 + spare Macs / 2 × EC2 Mac | 15 min | All jobs report an ETA ≤ 5 h | ETA > 6 h → drop that module to A1 | S5 |
| **S3 Image-anchor floor** | **Sat 17:00** | A | App: 4 cards, 4 CAD modules attached, moved by hand | 4 h | Overlay visually attached (edge error ≲ 5 mm at 40 cm) through 10 s of translation + 90° yaw on 3 modules; 60 fps | Revert to the Mac three.js twin (old W4, G4 22:00) | S4, S7, rocket AR |
| **S4 Contract + adapter** | **Sat 19:00** | D (adapter), A (sender) | `pose_observation` → `spatial_pose` → world → plan → HUD on G2 sim, from recorded poses | 2.5 h | Recorded "rotate motor" session → `TURN MOTOR 90° →` then `●` | Spatial stays explore-only (no G2 loop) | S8 |
| **S5 Apple object tracking** | **Sat 21:30** | A | Motor `.referenceobject` in `trackingObjects` | 1 h (after training) | ≥ 90% frames tracked over 10 s of handheld rotation; no pose flips; re-acquire after a hand occludes it < 1 s; edges visually aligned | Keep A1 cards on the modules that fail | markerless wow |
| **S6 Multi-part** | **Sat 23:00** | A | Base (detection) + ≥ 3 tracking modules (any A1/A2 mix) at once | 1 h | All ≥ 3 tracked ≥ 80% of 20 s; fps ≥ 30; phone not thermal-throttled after 10 min | Track 2 + cards; or the base by card only | S8 |
| **S7 Explode** | **Sun 00:00** | A | Isolate + explode + X-ray + ghost + teardown path from `scene_state` | 4 h | All five interactions in the AR and Explore modes; 60 fps | Explode/X-ray only in Explore mode | demo 16–26 s |
| **S8 Live twin** | **Sun 01:00** | A + D | The real motor rotated 90° by a judge-stand-in | 1 h | Local CAD follows with no visible lag; core diff → G2 p50 ≤ 1.2 s, p95 ≤ 2.0 s (E4 budget); 10/10 rotate trials, **0 wrong HUD instructions** | Spatial = explore + AR overlay, no G2 | S9 |
| **S9 Demo selection** | **Sun 03:00** (after P0 FREEZE 02:00) | D calls it | 5 consecutive clean 90 s spatial runs incl. the premature catch | 1 h | 5/5 | Rocket script leads (11); spatial becomes the +15 s add-on or is cut | lead demo |
| *MPS pose (FoundPose)* | *not scheduled* | — | *1 module, 10 stills, MPS* | *4–6 h* | *rot err < 10°, < 2 s/frame* | *don't start unless someone is idle Sat 20:00–23:00; kill 23:00* | *Devpost only* |
| *Cloud FoundationPose* | *not scheduled* | — | *RunPod 4090, recorded RGB-D* | *4–8 h* | *< 300 ms e2e at ≥ 5 Hz over a hotspot* | *rejected (§4)* | *—* |

**No spatial work may delay G0, G2, P0 FREEZE or the video (04:00).** S-gates use only A's lane, D's 2.5 h adapter, and Mac/EC2 compute.

---

## 15. Cost / latency

| Item | Cost | Latency |
|---|---|---|
| On-device tracking (A1/A2) | $0 | 1 frame (≈ 16 ms) for the visible overlay |
| Phone → core pose stream | LAN, ~15 KB/s | 5–20 ms [I] |
| Core commit (vote 5 × 100 ms + 300 ms settle) | — | ≈ 0.8 s by design |
| Planner + arbiter | — | < 10 ms |
| Core → G2 (bridge) | — | 100–300 ms (08 §5) |
| **Physical change → G2 action** | — | **p50 ≈ 1.0–1.3 s** (same budget as E4) |
| Create ML training | Own Macs: $0. **EC2 Mac** (dedicated host, **24 h minimum** [V]): ≈ $25–50 per host-day [I, verify] | 3–5 h wall per module, in parallel [V "a few hours"; C ~4 h] |
| Claude (identify, Q&A) | < $5 for the event [I] | 1–3 s, off the critical path |
| *Cloud FoundationPose (rejected)* | *RunPod 4090 ≈ $0.34–0.74/h [V]* | *≈ 7 Mbps uplink; 150–300 ms e2e; 1–3 s re-registration* |

---

## 16. Open-source and platform leverage

| Name | URL | Licence | Purpose | Setup | HW | First output | Integration | Maintenance | Rec. |
|---|---|---|---|---|---|---|---|---|---|
| ARKit image tracking | developer.apple.com/documentation/arkit | Apple SDK | A1 floor | Xcode | any ARKit iPhone | 1 h | 4 h | Apple | **USE** |
| ARKit reference objects (iOS 27) + Create ML objecttracker | developer.apple.com/documentation/visionos/implementing-object-tracking-in-your-app | Apple SDK | A2 markerless 6-DoF | Xcode 27 + CLI | iOS 27; AS Mac | 2 h + training | 3 h | new (Sep 2026) | **USE (gated)** |
| RealityKit / RealityView camera controls | developer.apple.com/documentation/realitykit | Apple SDK | Render, gestures, orbit | — | iOS 18+ | 1 h | in app | Apple | **USE** |
| VisionKit DataScanner | developer.apple.com/documentation/visionkit | Apple SDK | Barcode/OCR identify | — | iOS 16+ | 30 min | 1 h | Apple | **USE** |
| three.js LDrawLoader + USDZExporter/GLTFExporter + packLDrawModel | github.com/mrdoob/three.js | MIT | LDraw → USDZ/GLB with IDs | npm | Node/browser | 30 min | 1 h | very active | **USE** |
| LDraw parts library | ldraw.org | CC BY 2.0/4.0 | Geometry | zip | — | — | — | active | **USE** |
| ImportLDraw (Blender) | github.com/TobyLobster/ImportLDraw | GPL-2.0 | Fallback LDraw → USD | Blender add-on | Mac | 30 min | 1 h | active (Oct 2026) | FALLBACK |
| occt-import-js / Online3DViewer | github.com/kovacsv/occt-import-js · /Online3DViewer | LGPL-2.1 / MIT | STEP → mesh tree (generality) | npm | browser | 30 min | 2 h | O3DV active; occt-import-js last push 2024 | STORY / FUTURE |
| cascadio | github.com/trimesh/cascadio | [verify] | STEP → GLB in Python | pip | Mac | 30 min | 1 h | active (Jul 2026) | FUTURE |
| build123d | github.com/gumyr/build123d | Apache-2.0 | Code-CAD assemblies → STEP/glTF | pip | Mac | 1 h | — | very active | FUTURE (non-LEGO rigs) |
| Mayo / FreeCAD | github.com/fougue/mayo · FreeCAD/FreeCAD | BSD-2 / LGPL-2.1 | Inspect/convert STEP | dmg | Mac | 15 min | — | active | TOOL |
| xeokit | github.com/xeokit/xeokit-sdk | AGPL-3.0 | Built-in X-ray/explode | npm | browser | 1 h | 4 h | active | SKIP (duplicates renderer) |
| GLTFKit2 | github.com/warrenm/GLTFKit2 | MIT | glTF on iOS (SceneKit) | SPM | iOS | 1 h | — | active | SKIP (not RealityKit) |
| FoundPose | github.com/facebookresearch/foundpose | CC BY-NC 4.0 | RGB 6-DoF re-loc; **MPS env** | conda | Mac | 4–6 h [I] | 8 h | last push Sep 2025 | REJECT for the hack |
| FoundationPose | github.com/NVlabs/FoundationPose | NVIDIA Source Code Licence (NC) | RGB-D register + track | Docker; CUDA | cloud NVIDIA | 4–8 h | 10–14 h | active (Apr 2026) | REJECT for the live demo |
| M3T / ICG (DLR) | github.com/DLR-RM/3DObjectTracking | MIT | CPU multi-body CAD tracking | CMake; Eigen/GLEW/GLFW/OpenCV | Mac + RGB-D source | 6–10 h [I] | 10–12 h | last push Aug 2025 | FUTURE |
| ViSP MBT | github.com/lagadic/visp | GPL-2.0 | Edge/KLT/depth model-based tracking | CMake | Mac/iOS [verify] | 6 h | 10 h | active | SKIP |
| AprilTag / OpenCV ArUco | github.com/AprilRobotics/apriltag · opencv | BSD-2 / Apache-2.0 | E: unlimited tags on iPhone | SPM/C | iPhone | 3 h | 6 h | active | BACKUP if the 4-image cap bites |
| Vuforia Model Targets | developer.vuforia.com | Proprietary; Basic = dev-only, watermark, 20 generations [V] | CAD-based tracking | SDK | iPhone | 3–5 h | 6 h | commercial | SKIP |
| SAM 3D Objects | huggingface.co/facebook/sam-3d-objects | SAM licence | Image → 3D (L3g) | GPU | cloud | — | — | new | STORY ONLY |
| Rebrickable API / LDraw OMR | rebrickable.com/api · library.ldraw.org/omr | Free key / CC BY | L1c retail-set resolution | key | — | 30 min | 1 h | active | OPTIONAL |

---

## 17. Risks / red team

1. **Staffing is the #1 risk, not tracking.** The team is already at ~80 h against ~80 h (17/13). This pass adds ~16 h. It is affordable **only** with the swaps in §18/13: the Mac three.js twin is replaced by the phone; iFixit live drops to video; X1/X2 are cut. If the team won't make those swaps → **KEEP CURRENT CAD TWIN**.
2. **Training doesn't finish or fails.** Mitigations: wrong scale is the documented failure [V/C], so check scale against callipers; use standard mode; train in parallel; start by 14:45; A1 cards cover any module that fails.
3. **iOS 27 tracking is weak on small LEGO modules or confuses look-alike modules.** Mitigations: one dominant colour each, an asymmetric feature, negatives in training [V], 6–15 cm modules, phone at 40–50 cm. The S5/S6 kill → cards.
4. **Hands occlude the module during manipulation.** This is acceptable: the commit rule waits for stability anyway; Apple's demo tracks through partial hand occlusion [V].
5. **Thermal / power** ("significantly increases power consumption" [V]). Mitigations: track ≤ 4 objects at high rate, the base as detection-only; phone on a charger on the stand; S6 includes a 10-minute soak.
6. **Upstaging G2.** The phone faces the second judge; the HUD remains the only thing the wearer reads. The spatial script still runs on G2 actions.
7. **Hidden-state honesty.** The system must never claim it saw the motor through the deck. The `CAD_LAST_SEEN` / `NOT YET SEEN` badges plus the "LIFT DECK · TO CHECK MOTOR" behaviour turn this into a strength.
8. **Two demo rigs on one table.** Rehearse the 20 s handover; the rover reset takes < 30 s (rotate motor, deck on).
9. **Rules.** Designing the rover and training reference objects happen **after 12:00 Sat**. Only tool installs and the Apple-sample training test happen Friday.
10. **"It's just AR stickers."** If A2 fails, say so: "Cards give us ground truth today; the same pipeline runs markerless with Apple's new object tracking. Here's the module that passed." Never hide the cards.

---

## 18. Exact changes to existing docs — SUPERSEDED (→ V3 §13, applied in the final reconciliation)

| Doc | Change |
|---|---|
| **03** | Add **P1 W8 "GhostBuild Spatial (phone)"**, owner A, gates S1–S9. **W4** becomes "3D twin = iPhone RealityKit (W8), with the Mac three.js LDraw view as fallback only if S3 fails". **W6** iFixit live → video/Devpost only (frees D for the S4 adapter). **X1** hero tag and **X2** Mac AR ghost → CUT (superseded by phone AR). Remove "native apps" and "LiDAR/ARKit sensor app" from CUT and add the reason. Add S0–S9 rows to the Gates table. |
| **04** | Topology: add iPhone #2 `spatial/` (`ws role=spatial`), Mac 2 = 2D + phone mirror. §2 decisions: "Rich UI on the phone?" → "Not on the user's phone; a second, stand-mounted phone is an instrument." Add `adapters/spatial_pose`. §6 failure containment: spatial down → active task falls back to rocket; the G2 loop is unaffected. §7 honesty map: add `TRACKED`, `CAD_LAST_SEEN`. §8 isolation: rule 11 "nothing in `perception/` or the rocket path imports `spatial/` or `adapters/spatial_pose`". |
| **05** | Add `pose_observation` and `scene_state` (§11); extend `pose_source` enum, `verifier += object_pose`, `status` reason `hidden`; bundle adds `asset`, `relations`, component `parent`/`mesh_ref`/`insertion_axis`/`symmetry`; WS role `spatial`; `/control/ask` accepts `selected_component`. |
| **06** | §17: correct "Learned 6-DoF — CUDA-only" to "FoundationPose CUDA-only; FoundPose has an MPS env; Apple iOS 27 object tracking is on-device; for the rocket's brick-level state none beats the grid (unchanged)". The LiDAR cut stays for brick layers. |
| **09** | Retitle "Supervisor view, phone AR twin & fallback twin". The Mac becomes 2D panels + phone mirror + optional `scene_state` three.js view. The new §10 describes the phone app (= this doc §6/§9). |
| **11** | Add the spatial 90 s + 45 s scripts (§13), the rover reset (< 30 s), the phone stand position, and the S9 rule for which script leads. Keep the rocket script as-is and as the default. |
| **13** | A: phone app 12 h + asset pipeline 2 h + video 6 h + rehearsal 2 h (old twin 9 h + panels 3 h → panels 1 h). D: +2.5 h `spatial_pose` adapter + teardown planner, −2.5 h iFixit live. The iOS-experienced teammate: 1 h Xcode/signing bootstrap with A at 13:00, 30 min review at 18:00. Compute: two EC2 Mac hosts or borrowed Macs for training. |
| **14** | Sat 12:15–14:15 A builds + models the rover (the rocket design moves to C + D's first hour, or is shortened); 14:45 training kick-off; 17:00 S3; 19:00 S4; 21:30 S5; 23:00 S6; Sun 00:00 S7; 01:00 S8; 03:00 S9. Nothing moves G0/G2/P0 FREEZE/video. |
| **15** | Add `spatial/` (Xcode project) and `adapters/spatial_pose/` to the repo layout; remove "Native apps" and "ARKit apps" from "What NOT to build" for `spatial/` only; add [verify] items: iOS 27 `trackingObjects` + image-detection coexistence, USDZExporter materials, Xcode 27 macOS requirement. |
| **16** | D-28 Spatial prototype (this doc) with promotion gate S9; D-29 a second phone is an instrument, not a UI on the user's phone (amends D-07); D-30 Apple-native pose over cloud GPU (evidence §4); D-31 LEGO System rover as the spatial rig; A-15 team iPhones on iOS 27; A-16 Create ML ≤ 5 h per module; A-17 ≥ 3 simultaneous tracks on iPhone. |
| **17** | Supersede the §5 rows "FoundationPose… REJECT (CUDA)" and "ARKit sceneDepth… CUT" with pointers to 18 §4; add the risk-weighted score row from §1. |

---

## Final self-critique

| Question | Answer |
|---|---|
| Would a judge say "holy shit"? | When the deck CAD lifts out of the real rover in the judge's own hand, and the motor CAD turns as they turn it: yes, if A2 or A1 holds. |
| Is the 3D useful, not eye candy? | Yes. It shows the path to the goal, what is hidden and unverified, and the exact correction. Each element maps to a G2 action. |
| Is the model really tied to reality? | Per-module ARKit anchors at frame rate; core's state comes only from stable tracked poses; hidden parts are labelled, not imagined. |
| Does moving something real move the twin? | Yes, on the phone, with no network in that loop. |
| Does AI materially improve it? | Yes: on-device learned 6-DoF, the manual compiler, goal understanding, identification and cited Q&A. Explicit state keeps it honest. |
| Is G2 still essential? | Yes. The wearer's hands are on the rover and their eyes on the work; the phone is for the second person and for exploring. |
| Does it generalise beyond LEGO? | Same contract for any USDZ/STEP-derived asset; Apple's tracker is object-agnostic; asset levels L1–L4 are explicit. |
| Can the CAD story be told honestly? | "Our exact CAD at tracked poses. Hidden parts are CAD at their last seen pose. Nothing here is a reconstruction." |
| Can it be built in 24 h? | The floor (A1 + explode + G2 loop): likely. Markerless (A2): a coin flip, gated by training wall-clock. |
| Can every ambitious dependency fail without killing GhostBuild? | Yes. A2 → A1 → Mac three.js twin → 2D; the spatial lane → the rocket script. P0 never imports spatial. |
| Did we find the best current technology ourselves? | Yes. iOS 27 `trackingObjects` (Sep 2026), FoundPose's MPS env, M3T as a CPU CAD tracker, and the costed cloud route; all checked against primary sources, with gaps marked [verify]. |

---

## 19. Sources

- Apple, ARKit `trackingObjects` (iOS 27.0): developer.apple.com/documentation/arkit/arworldtrackingconfiguration/trackingobjects
- Apple, "Using a reference object with ARKit in iOS" (max 10 per session; `isTracked`; `usdzFile`): developer.apple.com/documentation/visionos/using-a-reference-object-with-arkit-in-ios
- Apple, "Implementing object tracking in your app" (iOS 27 / visionOS; USDZ guidance; viewing angles; standard vs extended; objects to avoid; "a few hours"; CLI): developer.apple.com/documentation/visionos/implementing-object-tracking-in-your-app
- Apple WWDC26 session 283, "Explore enhancements to visionOS object tracking" (iOS 27 support; high frame rate; extended training; 3D-printed marker approach): developer.apple.com/videos/play/wwdc2026/283/
- Apple, `maximumNumberOfTrackedImages` (max 4, moving images): developer.apple.com/documentation/arkit/arimagetrackingconfiguration/maximumnumberoftrackedimages
- Apple, `realityViewCameraControls(_:)` (iOS 18): developer.apple.com/documentation/swiftui/view/realityviewcameracontrols(_:)
- AWS, Create ML object tracking on EC2 Mac (CLI, 24 h host minimum, iOS use): aws.amazon.com/blogs/physical-ai/build-a-spatial-object-tracking-pipeline-with-create-ml-on-amazon-ec2-mac/
- Community iOS 27 + visionOS 27 demo (≈ 4 h standard training on M4 Max; extended ≈ 7×; 6-object Vision Pro limit) [C]: github.com/robomex/visionOS-27-iOS-27-Object-Tracking-Demo
- Apple Developer Forums, Create ML training time / failure reports [C]: developer.apple.com/forums/thread/768225 · /766726 · /756875
- BOP Challenge 2024 report (FreeZeV2.1 24.9 s, Co-op 0.8 s): arxiv.org/abs/2504.02812
- FoundationPose (Docker, CUDA, licence, 4090 note): github.com/NVlabs/FoundationPose · NGC benchmarks: catalog.ngc.nvidia.com/orgs/nvidia/isaac/models/foundationpose
- FoundPose (MPS conda env, CC BY-NC 4.0): github.com/facebookresearch/foundpose
- DLR M3T/ICG (MIT): github.com/DLR-RM/3DObjectTracking · arxiv.org/abs/2208.01502
- Vuforia pricing (Basic: dev-only, watermark, 20 generations): developer.vuforia.com/library/faqs/pricing-and-licensing-options
- RunPod pricing: runpod.io/gpu-cloud/pricing
- SAM 3D Objects: ai.meta.com/sam3d/ · huggingface.co/facebook/sam-3d-objects
- three.js exporters (USDZ/GLTF) and LDrawLoader: github.com/mrdoob/three.js (examples/jsm/exporters, examples/jsm/loaders)
- OSS repos as listed in §16 (licences and last-push dates read via the GitHub API on 2026-10-16).

PROTOTYPE GHOSTBUILD SPATIAL: build a stand-mounted iPhone RealityKit twin of a five-module LEGO rover that tracks each module with zero-training ARKit image anchors, upgrades to markerless iOS 27 object tracking wherever Create ML training finishes in time, and feeds the unchanged core planner and G2 loop, leading the demo only if gate S9 passes.
