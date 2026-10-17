# 00 — Strategy & Validation Report (Phase 1)

Tags: **[V]** verified official fact (source linked) · **[I]** evidence-based inference · **[D]** our product decision.
Research date: 2026-10-16. Event: **LA Hacks AI Hackathon 2026, Sat Oct 17 12:00 PM → Sun Oct 18 12:00 PM PDT, James West Alumni Center, UCLA** [V: live.lahacks.com, la-ai-hackathon-2026.devpost.com/details/dates]. ~72 registered participants (≈18–25 teams) [V: Devpost count at time of check].

> ## ⚑ FINAL RECONCILIATION (2026-10-16) — read this first
> **Operational source of truth:** `20_FINAL_IMPLEMENTATION_BIBLE.md` (and `21_HACKATHON_CHECKLIST.md` for clocks). This doc is research history; its first-pass sections are kept for evidence.
> - **Product:** GhostBuild is **an AI copilot for physical work**. Loop: goal → documentation/CAD → physical observation → world state → current-vs-target diff → planner/replan → next action on G2 → human acts → verify → repeat → VERIFIED → G2 quiet. LEGO rigs are testbeds, not the product.
> - **P0** is the rocket/grid loop and stays independently runnable with every sponsor integration and Spatial disabled.
> - **Spatial prototype per 18 v3.** It leads only under 18 v3 §9 (V2 §18 as amended). Voice is opportunistic P2, never scheduled; the G2 contextual menu (WHY? · WHERE? · CAN I? · WHAT'S DONE? · WHAT NEXT?) is P1.
> - **Prize targets (19, final):** Even Realities (primary) · Sentry (secondary) · Fetch.ai (conditional secondary) · Beyond the Digital (organizer track) · MLH Commit Fellowship (opt-in) · Workday (framing only, if free). StepFun, Cognition-specific features and the rest are dropped. **§3 below is SUPERSEDED.**
> - **Generality proof:** optional, offline only: one real repair guide compiled through the same compiler, shown as "compiled, not executed" in Devpost/README. No live iFixit demo, no guided mode.
> - **Superseded in the ambition-pass block below:** hold-to-ask voice as P1 (→ P2), the Mac three.js twin (→ phone RealityKit twin; W4-lite only if spatial dies early), the VLM foreign-object label (→ CUT), and the live iFixit answer (→ offline proof).

> ## ⚑ AMBITION-PASS UPDATE (2026-10-16) — supersedes §1 verdict, §5 rows for voice/3D/learned perception, and §8 positioning *(itself partly superseded by the final reconciliation above)*
> Full analysis: **17_AMBITION_PASS.md**. The verdict changes from "BUILD, BUT CHANGE" to **UPGRADE (trimmed)**:
> - The P0 loop below is unchanged and remains the sole authority on physical state.
> - Four P1 layers are added, each behind a gate:
>   - a CAD-grounded **manual compiler** with LLM-extracted evidence;
>   - a deterministic **cited answer engine** reached via the G2 menu *(hold-to-ask voice: P2 opportunistic, final)*;
>   - a **live CAD twin** *(final: the phone RealityKit twin of the rover, 18 v3)*;
>   - hand-aware perception *(the VLM foreign-object label is CUT, final)*.
> - Scores: constrained 72 → trimmed upgrade **84** (red-team P(win) estimate 30 → 41).
>
> **Updated positioning**
> - **Tagline:** *The work guide that checks your work.*
> - **One sentence:** GhostBuild reads the manual, watches your hands, and shows only the next verified step on Even G2. When you ask "why?", it answers from the manual and from what it sees.
> - **15 s:** Instructions tell you what to do; nothing checks what you did. GhostBuild compiles a product's manual and CAD into a task graph and watches the build with a camera. G2 shows one verified action at a time. Open the temple menu and ask "can I skip?"; it answers from the manual and the live state. Then it goes quiet.
> - **45 s:** Every guide assumes you did the last step right. GhostBuild treats the physical world like code:
>   - Claude reads the instruction manual into per-step evidence.
>   - The CAD model gives the exact target and dependencies.
>   - A camera keeps an explicit world model that never guesses.
>   - A planner verifies the next action from wherever you actually are.
>
>   G2 shows only that action. If you skip ahead, it catches the dependency and tells you why, citing the manual page. We deliberately don't let a VLM judge fine physical state, because benchmarks show they can't. AI reads documents and understands you; explicit state keeps it honest. LEGO is our rig. *(Final: say "the same compiler also compiled a real repair guide" only if the offline generality proof validated; it is compiled, not executed.)*
> - **Novelty:** "Unlike document copilots (VSight Nova, Tulip, Dynamics 365 Guides) that cite the manual but can't see the work, and vision stations (LightGuide, Arkite, Vuforia Step Check) that see the work but follow hand-authored steps, GhostBuild compiles the manual and CAD into a dependency-aware task graph, verifies every step against the observed world, and answers 'why' with both the manual page and what it sees, on glasses that stay quiet until needed." Closest research: WorkBenchMark/Manual2Skill/AssemState (robots, not human guidance). Cite them.
> - **Technical claims we can prove:**
>   1. 0 wrong committed states over N frames, with measured per-part accuracy.
>   2. Planner plan length = BFS optimum on all ≤ 2-defect states, and the premature/deviation catch rate is measured.
>   3. LLM-extracted step evidence matches the CAD on n/m steps (only if K1 passed); every answer's citation is valid by construction. *(Voice latency only if voice ever ships; P2.)*
> - **Product claims:**
>   1. It catches errors the user didn't notice and order violations, with a reason.
>   2. It's quiet: it speaks only on change or when asked.
>   3. It generalises through documents: the same compiler compiled a real repair guide offline (only if validated; "compiled, not executed").
> - **New judge questions:**
>   - *"Is the task graph handwritten?"* No. Dependencies and target come from the CAD file; step text comes from Claude reading the PDF; the screen shows provenance and the match score. A golden file exists only as a test oracle.
>   - *"Why not let a VLM check the build?"* We measured/cited: VLMs score ~40% F1 on LEGO state and misjudge fine spatial state. We use AI where it's strong.
>   - *"Can I ask it questions?"* Yes: the temple menu asks the grounded answer engine (WHY / WHERE / CAN I / WHAT'S DONE / WHAT NEXT). *(Voice is P2 and only mentioned if it shipped.)*
> - **Ten minutes later, a judge says:** *"The glasses one — I asked if I could skip ahead, it said 'not yet, green first.' I did it anyway and it caught me, and it quoted the manual. Then it went dark."*

---

## 1. Executive verdict

| | |
|---|---|
| **GhostBuild as originally framed** (handheld phone scan, 3D understanding, rich phone 3D UI, G2 as secondary display) | **58 / 100** |
| **GhostBuild constrained** (fixed overhead camera, fiducial grid, discrete state, deterministic replanner, G2 as the only guidance surface, 2D supervisor view) | **78 / 100** |

### **Original verdict (first pass):** BUILD GHOSTBUILD, BUT CHANGE: fixed-camera discrete grid-state workcell. **Current verdict:** see 17_AMBITION_PASS — UPGRADE (trimmed).

| | |
|---|---|
| Overall-win ceiling | Top-3 plausible, not locked. Rough judgment: ~25–35% top-3, ~10–15% 1st. [I] |
| Sponsor-win ceiling | Even Realities: **favourite if executed at 80%**. Rough judgment: ~35–45% 1st, ~65–75% top-3 among teams that get a loaner. [I] |
| Biggest advantage | The only closed-loop project in the room: the judge's *own* mistake is caught and replanned on the glasses within ~1–2 s. Matches Even's brief ("repair guides", "hands full", "Quiet Tech") almost verbatim. [V brief + I] |
| Biggest technical risk | The packaged **Beta** plugin cannot reach the laptop (LAN `http/ws` in a Beta build is undocumented; venue Wi-Fi isolates clients). [V: docs silent; starter pack warns] |
| Biggest product risk | "I could see that mistake myself" / "who needs this for LEGO?" — the glasses must tell the judge something they couldn't trivially see. |
| Biggest demo risk | One wrong instruction ("REMOVE RED" when red is correct) destroys trust. Perception must abstain rather than guess. |
| Single most important experiment | **E1 (hour 2–5): under venue light, the CV reads all three defect types + a deliberate wrong placement with zero wrong committed states over 300 frames / 10 trials.** Everything else is engineering; this is the one thing that can make the idea false. |

### Why not PIVOT
- The Even brief explicitly invites this category: "repair guides while you fix a bike", "step-by-step lab protocols while your hands are full"; it warns teleprompters/translators/note-takers "won't stand out". [V: evenrealities-lahacks.vercel.app]
- "Quiet by Design: does the technology appear when it is useful and stay out of the way when it isn't?" is a judged criterion [V: official challenge doc]. GhostBuild's core behaviour (silent until something is wrong) *is* that criterion.
- The risky part (perception) can be constrained into a solved problem (fiducial grid + colour + dot markers), with a 1–2 h tag-based fallback. A camera-free G2 idea would be safer but would give up the one moment nobody else will have.

---

## 2. Winning-pattern analysis

| Project | What judges physically experienced | One-sentence transformation | Sponsor tech essential? |
|---|---|---|---|
| **Lumos** (LA Hacks 2025, 2nd overall + Fetch) | Wore Snap Spectacles; faces recognised, memory cues shown | "Glasses remember people for Alzheimer's patients" | Yes — glasses were the product [V: devpost.com/software/lumos-f8h0mn] |
| **RIIS** (LA Hacks Apr 2026, 2nd + Fetch) | Physical rover, live pose overlay, VR scene | "A rover that finds survivors in rubble" | Yes — agents ran triage [V: devpost.com/software/riis] |
| **codebreaker** (LA Hacks Apr 2026, 1st + Cognition) | Watched agents find and patch vulns live, with a benchmark | "Autonomous security that proves its fixes" | Yes — Devin [V] |
| **Pulse** / **Ghostface Cookah** (LA Hacks 2025 Snap winners) | Step-by-step CPR / recipe guidance in AR | "Guidance in your line of sight while hands are busy" | Yes [V] |
| **ChessMate**, **DUM-E** (Hack the North 2025) | Physical pieces moved/sorted by CV-driven hardware | "CV closes the loop in the physical world" | — [V] |
| **TinkerFlow** (HtN 2024) | Photo of parts → generated build steps | Closest hackathon analogue; **no verification of the build** [V] |

**Patterns** [I]: (1) the judge touches/wears something physical and the AI reacts to *them*; (2) a closed perceive→decide→act→verify loop; (3) a vivid user and moment in one sentence; (4) sponsor tech is load-bearing, which is why winners stack overall + sponsor (codebreaker, RIIS, Alto, Lumos all did) [V: galleries]; (5) one quantitative proof point (benchmark / A-B).

**GhostBuild matches** 1, 2, 4 strongly; 5 via the eval (10_EVAL_PLAN) and the VLM-baseline comparison. **Gap:** 3 — LEGO alone is not a vivid user. Fix with framing (§02_PRODUCT_SPEC): *"the work guide that checks your work"* — lab bench / kit setup — with LEGO as the testbed judges can break.

---

## 3. Track / sponsor matrix — SUPERSEDED / HISTORICAL (final targets: 19 and 20 §11)

> First-pass research only. **Final decisions:** Even primary; **Sentry secondary (added)**; **Fetch.ai conditional secondary (was "No")**; Beyond the Digital organizer track; MLH Commit opt-in; Workday framing only if free; **StepFun dropped (was "TARGET #3")**; Cognition network-only.

Full inventory (sources: live.lahacks.com/tracks + linked sponsor docs [V]; prizes marked TBD where unpublished):

| Track / challenge | Prize | Fit | Decision |
|---|---|---|---|
| **Even Realities — Smart Glasses (Quiet Tech)** | 1st: G2 per member ($2,400); 2nd $250 pp; 3rd $100 pp | Native: repair guides, hands-full, Quiet by Design | **TARGET #1** |
| **Overall** (Technical Depth / Product & Impact / Execution & Polish / Originality & Insight) | TBD (non-cash) | Closed loop + honest eval + physical demo | **TARGET #2** |
| **Beyond the Digital** (organizer track: "intelligence into the physical world… AR… emerging interfaces") | TBD | Literal fit, zero extra cost | **Select as our organizer track** (part of #2) |
| **StepFun — Get It Done with Step 5 Preview** ("must call step-5-preview when it runs"; suggests "use image understanding to guide the next action") | UNVERIFIED | Open-world VLM labels + VLM-baseline eval | **TARGET #3 — CONDITIONAL** (gate below) |
| Applied Intelligence / Model Learning / Agentverse (organizer tracks) | TBD | Weaker than Beyond the Digital | No |
| Fetch.ai ASI:One ($1.5k/$1k/$500) | — | Primary workflow must run in an ASI:One chat, "without requiring a custom frontend" — contradicts a HUD-first demo | **No** |
| Cognition — Best Use of Devin ($5k credits) | — | Only if Devin is genuinely used; high competition | Optional, zero effort only |
| Paper — Best Designed Hack ($1.5k/$1k/$500) | — | Supervisor view isn't the design story | No |
| Base44, QNX, Espressif, Visa, Intuit, Workday, CREAO, Photon, Browser Use, Sentry, veri.studio | various | Require their platform/hardware or unrelated domains | No |
| MLH Gemini / ElevenLabs etc. | swag | Gemini only if it ends up as the VLM fallback | Incidental only |

**Why these three:**
1. **Even** — removing G2 removes the product: the whole value is hands-free, eyes-on-work, one-action guidance. Largest per-member prize; limited loaners cap competition; brief literally names the category.
2. **Overall via Beyond the Digital** — same build, no extra engineering; the closed loop + BFS-verified planner + honest eval hit Technical Depth and Originality; physical demo hits Execution.
3. **StepFun (conditional)** — earns its place only because it does real work: the VLM names off-library objects ("REMOVE PEN") and anchors the "VLMs alone fail at physical state; here's our hybrid" insight. **Gate (Sat 3:00 PM):** prize confirmed at opening ceremony **and** `step-5-preview` accepts images with p50 < 4 s from the venue. Fail → use Gemini/Claude for the same module and drop the track. Never on the critical path.

---

## 4. Prior art & novelty

Closest systems (details in research notes; all [V] with links in 16_DECISIONS appendix):

| System | Observes current state? | Diffs vs target? | Replans from any state? | Glasses HUD? |
|---|---|---|---|---|
| Khuong et al., IEEE VR 2014 (Kinect, DUPLO, voxel diff) | Yes | Yes (per frame) | Partly (next layer from diff) | Video see-through HMD |
| Amazon patent US10366521B1 (2017) | Yes, incl. orientation vs CAD | Yes | Corrective instructions | Yes (AR glasses) |
| Caltech SIGGRAPH 2025 (Vision Pro + VLM, LEGO) | Yes | Yes | Guides back to valid state | Headset |
| Cornell "Augmented Assembly" TEI'26 (HoloLens) | Yes | Yes | Yes for printed parts; LEGO was a fixed sequence | Headset |
| PTC Vuforia Step Check | Per-step pass/fail classifier | Per step | **No — linear authored procedure** | Mobile/HMD |
| Retrocausal Pathfinder | Actions vs SOP | vs sequence | No | Station screen |
| Meta Ray-Ban Display step guidance | No state check | No | No | Yes |
| TinkerFlow (HtN 2024) | Parts inventory only | No | No | No |

**Novelty decomposition** [D, grounded in the above]:
1. *Existing primitives:* fiducial registration, colour classification, CAD/target diffing, step verification, glasses HUD text — all exist.
2. *Our combination:* full discrete state (presence + position + orientation + support) → typed diff → dependency-aware replanning from any observed state → one action on camera-less consumer glasses.
3. *Our system contribution:* order-independent replanning with deviation vs out-of-order-progress classification, a termination argument, and plan length checked against BFS optimum; perception that **abstains** rather than guesses; zero per-step training images.
4. *Demo/product insight:* a tiny, low-bandwidth HUD forces guidance down to **one** action — and one action is only trustworthy if it is recomputed from reality every time. The constraint justifies the architecture.

**Defensible sentence:**
> "Unlike step-checking systems such as Vuforia Step Check or Retrocausal, which grade each step of a fixed, authored procedure, GhostBuild treats the observed physical state as the source of truth and recomputes the next valid action from wherever the build actually is — out of order, flipped, missing or extra — and shows only that action on camera-less everyday glasses."

Weak sentences to **avoid**: "first AI that verifies physical assembly"; "unlike tutorials, it knows what you built" (Khuong 2014, Amazon 2017, Caltech 2025 all do). **Cite Khuong 2014 ourselves** on the prior-art slide — it reads as competence.

---

## 5. 24-hour feasibility

| Feature | Rating | Note |
|---|---|---|
| Fiducial board + rectification | GREEN | OpenCV ArUco, well-trodden |
| Per-cell LAB colour classification + venue calibration | YELLOW | Lighting; must pass E1 |
| Dot-sticker orientation (180°) | YELLOW | Sticker contrast/size; E1 |
| Part fitting (tiling search) | GREEN | Tiny search space |
| Occlusion gate + 5-frame vote | GREEN | Simple heuristics |
| Layer-2 cap (dependency, "LIFT first") | YELLOW | Partial visibility; gate at hour ~14 |
| Diff + deterministic replanner + BFS test | GREEN | Pure functions, TDD |
| Deviation vs out-of-order classification | GREEN | Distance-based rule |
| Core WS hub + mock vision replay | GREEN | |
| G2 plugin text HUD (simulator) | GREEN | Templates + skills |
| G2 on hardware via QR | GREEN/YELLOW | Needs loaner + own LAN |
| **G2 Beta build reaching the laptop** | **YELLOW→RED until E2 passes** | Undocumented; two-rung ladder |
| Minimap image on G2 | YELLOW | PNG path verified in template; hardware legibility unknown |
| Beta QA (lock, exit, denial) | YELLOW | Known checklist; test 3× |
| 2D supervisor view | GREEN | |
| Open-world VLM labels (async) | YELLOW → **CUT (final)** | Latency/API access; non-blocking |
| VLM-baseline eval (20 frames) | GREEN | Offline script |
| Isometric 3D view | YELLOW (stretch) | Cut if any gate red |
| Voice Q&A via glasses mic | RED (for 24 h) → final: **P2 opportunistic, never scheduled** (18 v3 §8) | STT provider + latency + noise; adds nothing to core claim |
| Handheld phone scanning | RED | Hands are needed for the repair; camera pose varies |
| 3D reconstruction / LiDAR | RED | Below noise floor at LEGO scale; minutes per capture (still cut; the spatial lane uses known CAD + ARKit tracking, not reconstruction) |
| Training a detector | RED (unless fallback forced) | Labels + still can't see 180° flips |
| Technic / arbitrary objects | RED | Recognition collapses |
| Second "skin" (tube rack) | YELLOW (stretch) | Only if everything else is green Sun 3 AM |

---

## 6. Core experiments (run before polish)

| # | Question | Experiment | Pass | Fail → |
|---|---|---|---|---|
| **E1** | Can we reliably identify physical state? | 10 configurations × 30 frames under venue light (target, each defect, combos, cap) | ≥ 99% per-cell single-frame; **100% per-part after vote; 0 wrong committed states** | Light box + recalibrate → AprilTag caps (Plan B) by 6 PM |
| **E1b** | Orientation/location errors? | 1-stud shifts, 180° flips, 90° turns, swaps × 10 | 10/10 each | Bigger dots / tags |
| **E2** | Can a **Beta** build reach the laptop? | Stub plugin, all ladder origins whitelisted; install via Beta; test LAN `ws://` and Funnel `wss://`; lock 5 min; retest | ≥ 1 rung connects and survives lock | Funnel over cellular; if both fail, QR sideload on own LAN for judging (disclose if asked) + escalate at Even table before 8 PM |
| **E3** | Can we drive G2 reliably? | 200 HUD updates from mock core at 2 Hz | 0 hangs; p95 `bridge_ms` < 300 ms | Lower rate; drop minimap |
| **E4** | Fast enough? | 30 trials: hand leaves → `hud_ack` | p50 ≤ 1.2 s, p95 ≤ 2.0 s | Tune K/quiet period |
| **E5** | Visible recovery from unexpected action? | 20 deliberate wrong actions by a teammate acting as judge | 20/20 detected + correct corrective instruction ≤ 2 s; 0 wrong instructions | Fix planner/vision; never ship flapping |
| ~~E6~~ | ~~VLM usable?~~ **CUT (final):** the VLM label and StepFun are dropped | — | — | Unknown regions stay `CLEAR UNKNOWN ITEM` |
| **E7** | Glyphs & minimap legible on glass? | Render glyph test + map | Judge-legible at a glance | Text-only |

---

## 7. Verdict gate — HISTORICAL (final clocks: 21_HACKATHON_CHECKLIST)
Passed → Phase 2 spec package (01–16). First-pass go/no-go checkpoints: Sat 12:30 PM (G2 loan), Sat 5:30 PM (E2 transport → final G0 15:00), Sat 6:00 PM (E1 CV path → final G2 perception 20:00), Sun 2:00 AM (→ final P0 freeze 02:00), Sun 10:30 AM (code freeze / Devpost materially complete).

---

## 8. Final positioning

**PROJECT NAME:** GhostBuild (Even Hub app name: `GhostBuild` — ≤ 20 chars, no "Even") [V rule]

**PRODUCT (final):** an AI copilot for physical work.

**TAGLINE:** *The work guide that checks your work.*

**ONE-SENTENCE PITCH:** GhostBuild watches a physical build, compares it to the known correct result, and shows you only the next fix on Even G2 — recalculating from what you actually did, and staying silent when nothing is wrong.

**15-SECOND PITCH:** Instructions tell you what to do; they never check what you did. GhostBuild watches your hands' work with a fixed camera, diffs it against the target, and puts one action in your line of sight on Even G2. Make a mistake and it catches it and replans in about a second. Get it right and it goes quiet.

**45-SECOND PITCH:** Every step-by-step guide — paper, app, or glasses — assumes you did the last step right. In real assembly and bench work, the expensive errors are the ones you didn't notice: a part one position off, flipped, or missing. GhostBuild treats the physical world like code: it observes the current state, computes a diff against the known target, and plans the shortest valid fix — including "lift this first" when something blocks the repair. G2 shows only that next action, with a tiny map, and dims while your hands are working. If you go off-script, it doesn't advance to step 4; it replans from reality. No training data, no headset — a webcam, four printed markers, and everyday glasses. LEGO is our test rig because you can break it; the same loop applies to lab racks, kits, and workstations with a known correct layout.

**DEVPOST OPENING:** "Instructions tell you what to do. Nothing checks what you did. GhostBuild is a Quiet Tech work guide for Even G2: a fixed camera reads the physical state of a build, a planner diffs it against the target and recomputes the next valid action from wherever you actually are, and G2 shows only that one action — then goes dark when the build is right."

**ONE-SENTENCE NOVELTY CLAIM:** see §4 "Unlike Vuforia Step Check or Retrocausal…".

**THREE TECHNICAL CLAIMS WE CAN PROVE**
1. Live perception of discrete physical state (presence, position, 180°-orientation, support) at ~10 fps with abstention: measured per-part accuracy and **0 wrong committed states** over N frames (10_EVAL).
2. Replanning from arbitrary observed states: planner plan length equals the BFS optimum on all ≤ 2-defect states of the demo target (unit test), and recovers from 20/20 deliberate deviations (E5).
3. Camera-to-glasses latency measured end to end with `hud_ack`: p50/p95 reported, not estimated.

**THREE PRODUCT CLAIMS WE CAN DEFEND**
1. It catches errors the user did not notice (1-stud shift, flipped part) — shown live.
2. It is quiet: the HUD changes only when the next action changes, dims during hand activity, and goes blank when correct (Quiet by Design).
3. It generalises to any setup with a known correct layout on a registered surface (kits, lab racks, workstations) without per-step training images — honest limit: top-down, grid-registered, known parts.

**TOP 10 JUDGE QUESTIONS**
1. *Why glasses, not the laptop screen?* — Your hands are in the work and your eyes stay on it. The screen is for the second person; the user never looks up. One action at a time is exactly what a 576×288 HUD is good for.
2. *Is this real AI or a script?* — Every instruction is computed from the live camera state; do something we didn't expect and watch it replan. The supervisor view shows per-cell perception live. No predetermined sequence exists in the code.
3. *Why not just ask GPT/a VLM?* — Published LEGO and physical-state benchmarks show VLMs misjudge fine physical state (17 §1); if we ran our own baseline (10 §4, optional) quote it with n. We use AI where it's strong: reading the manual. The deterministic planner, not a model, decides what to tell you.
4. *Khuong 2014 / Vuforia did this.* — Yes, and we cite them. Khuong needed a Kinect and studded DUPLO voxels; Step Check grades a fixed procedure with per-step training images. We replan from any state with zero training, on consumer glasses.
5. *Does it work on anything?* — No: top-down, registered surface, known parts. That's how industry deploys this (instrumented workcells). The markers are four stickers.
6. *How do you know orientation?* — Footprint shape gives 90°; a part fiducial (dot) gives 180° — the same idea as a barcode. Without it, nothing can see a symmetric brick flipped from above.
7. *What if it's unsure?* — It abstains: "ADJUST BRICK" or "CHECKING", never a guess. Wrong instructions issued in our trials: [0].
8. *Latency?* — Measured p50 [x] s from hand leaving to glasses updated; most is a deliberate 5-frame vote for stability.
9. *Who uses this tomorrow?* — Anyone assembling or setting up something with a known correct layout and their hands full: kit builders, lab bench setup, kitting/QC stations. LEGO is our rig because you can break it.
10. *What's next?* — Author targets by scanning a finished build once; multiple skins (tube racks, PCB placement); a second camera angle for height.

**What should a judge say to another judge ten minutes later?**
> "The LEGO one with the glasses — I made a mistake on purpose and it caught it and told me how to fix it. Then it just went quiet."

---

## 9. Final self-check

| Audit item | Status |
|---|---|
| Official LA Hacks rules | ≤ 4 members ✓; new work only ✓ (no code before 12:00 PM Sat; buying parts, accounts and tool installs are fine); public repo + 2–3 min video + in-person judging planned ✓ |
| Official judging criteria | Mapped per criterion in 01 ✓ |
| Chosen sponsor requirements | Even: Beta `.ehpk` + physical G2 + Devpost fields + name rules ✓ (01 checklist). *(Final: StepFun dropped; Sentry and Fetch requirements in 19 §6.)* |
| Current G2 SDK capabilities | Text/image containers, limits, input events, `shutDownPageContainer(1)`, whitelist/CORS verified against docs + SDK 0.0.16 typings ✓. No camera/stream reliance ✓ |
| Even submission requirements | Lock / permission / exit / relaunch / boot-console checks in 08 §11, run 3× ✓ |
| One-device limitation | Only B handles the loaner; everyone else works against the simulator/mocks; no step needs two G2s ✓ |
| 24-hour feasibility | REDs excluded; YELLOWs gated with fallbacks ✓ |
| Four-person parallelism | Mocks per vertical; one shared contract; D merges ✓ |
| Demo reliability | Abstention, own light, own network, reset < 45 s, backup video ✓ |
| Novelty / prior art | Narrow, defensible claim; Khuong 2014 cited proactively ✓ |
| Technical honesty | REAL / INFERRED / PRECOMPUTED / VISUALIZATION map (04 §7); override always labelled ✓ |

Unresolved facts needing organizer/sponsor confirmation: 16 §"Unresolved facts" (Beta LAN origins; authoritative Even rubric; loaner count; Overall prize/track rule; multi-challenge selection; Fetch "workflow in ASI:One" interpretation; stale deadline text; offline plugin launch).

**Original verdict (first pass):** BUILD GHOSTBUILD, BUT CHANGE: fixed-camera discrete grid-state workcell. **Current verdict:** see 17_AMBITION_PASS — UPGRADE (trimmed).
