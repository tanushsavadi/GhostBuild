# 21 — Hackathon Checklist (clock order)

Format: **TIME — OWNER — TASK** · ✅ PASS · 🔴 IF RED.
Rules: not demonstrably green at its clock = 🔴. "Almost" = 🔴. The action fires with no discussion. **Killed work is never reopened.** D reads gates at each standup. Detail: 20 (bible), 03 §Gates, 14 (hour by hour).

---

## FRIDAY NIGHT (no project code)

**Fri — A — S0 spatial tooling**
✅ iOS 27 spatial iPhone; Xcode 27 signs a hello-world to it; `xcrun createml objecttracker -h` runs on the trainer Mac; sample-job ETA recorded; Blender + ImportLDraw exports a sample model at correct dims. Trainer Mac identified (borrowed, or D's laptop if it isn't Mac 1).
🔴 No iOS 27 → A2 dead (cards only). No Xcode 27 Mac → spatial lane dead; A plans W4-lite.

**Fri — A — F0 Fetch**
✅ Agentverse + ASI:One accounts; promo `LAHACKSAI26LAHACKSAI26AV`; official ASI-compatible example (`mailbox=True`) answers inside ASI:One; note whether it can message unprompted; stop and delete it.
🔴 **Fetch dead before the hack.**

**Fri — A — Sentry + Devin accounts**
✅ Sentry org + Python project; DSN in the password manager (never git); SDK quickstart runs. Devin login; check whether credits need an event code. 19 Appendices A + B pasted into team notes.

**Fri — B — Even tooling**
✅ Even app signed in, developer mode; `evenhub-cli` + simulator installed. Nothing added to the G2 whitelist for sponsors.

**Fri — C — Rocket rig shopping/prints**
✅ Plate, bricks, cap, dots, foam core, webcam + arm, LED panel; ArUco IDs 0–3 + grey patch printed.

**Fri — D — Network + cache**
✅ Tailscale Funnel tested (`*.ts.net` noted); LDraw library + three.js cached; iFixit 158506 saved as PDF (optional proof).

---

## SAT 09:00 — CHECK-IN

**09:00 — B — G2 loan form** · ✅ submitted at 9:00 sharp.
**09:00 — C — Hardware Lab** · ✅ borrow a spare **Logitech webcam** (the only Hardware Lab action).
**09:00 — D — Organizer questions** · ✅ ask: Studio models before 12:00 allowed? **Multiple company challenges allowed?**

## SAT 11:00 — OPENING

**11:00 — A — Listen** · ✅ note the multi-challenge rule, Overall prizes, Devin credit distribution, any Sentry/Fetch form.
**11:30 — A — Sponsor tables (≤ 5 min each)**
✅ **Fetch:** "Supervisor workflow fully in ASI:One, technician executes on G2 — does that meet 'no custom frontend'? Unprompted messages? Reply timeout?" **Sentry:** "Log-derived spans with explicit timestamps + Logs — does that count as Tracing?" **Even:** loaner count; how judging works; Beta LAN `ws://`.
Unstaffed table → same question on that sponsor's Discord; re-check at the 20:00 dinner.
🔴 Fetch says **no** (any time) → **Fetch dead.** No Fetch answer by 00:30 → F1 🔴.

## SAT 12:00 — KICKOFF

**12:00 — all — Kickoff (15 min)** · ✅ everyone has read 20; repo created; Devin connected to the repo.
**12:30 — B — G2 loan decision**
🔴 No loaner → Even effectively lost; simulator + through-lens video; optimise for Overall.

## 12:45 — D — CONTRACT LOCK (one lock)
✅ `contracts/models.py` holds every core **and** spatial schema + fixtures (`pose_observation`, `twin_v2`, `control_goal`, `bundle_rover_excerpt`, `spatial_transforms`); `make contracts` green in Python + TS.
🔴 **The lock moves as one unit; D announces the new time. Nobody codes against partial contracts.**
After the lock: schema changes need D + every consuming owner. After 00:45: none.

## 13:45 — A — S1 MOTOR TRAINING
✅ Motor USDZ dims ±1 mm; origin bottom-centre; job running on the trainer Mac; **ETA ≤ 22:45**.
🔴 **A2 dead.** Motor gets a card. No retraining.

## 14:30 — D — M1 mocked end-to-end
✅ mock → core → G2 simulator + 2D supervisor.

## 15:00 — B — G0 TRANSPORT
✅ Stub Beta `.ehpk` shows laptop-pushed text over LAN `ws://` or Funnel `wss://`; round trip < 300 ms; survives a 5-min lock.
🔴 Funnel by 16:00 → own router/hotspot → both fail by 17:00 → all hands on transport.

**15:00–15:05 — B — Devin dispatch** (after reading G0, before joining the Even workshop)
✅ Briefs A (`integrations/sentry_bridge/`) and B (`integrations/fetch_agent/`, `GB_CORE_URL` required) dispatched.
🔴 by 15:15 → Devin not used; Sentry = B hand-builds Logs + one span type in the 22:00 slot or dies; Fetch dead unless A is freed by a spatial kill.

**15:05–16:00 — B — Even workshop** · ✅ ask "Is LAN `ws://` OK in Beta?"

## 16:00 — C — V2 HANDS
✅ 0 false commits over 20 hand insertions; no stuck freeze.
🔴 Motion-energy gate.

## 17:00 — D — K1 EXTRACTION
✅ ≥ 80% steps' part multiset correct; 100% schema-valid.
🔴 **Authored evidence for the rocket and the rover sheet. Extraction frozen — not debugged. Generality proof cancelled.**

## 17:30 — A — S2 KILL (app floor)
✅ App on device at 60 fps; base gizmo visibly aligned with the mat; motor CAD upright, gear on the correct side; Swift transform tests green; `gb_base` anchor survives the phase-2 re-run [verify].
🔴 **Spatial lane dead.** A builds W4-lite from 17:30 (gate 23:00), then owns Fetch 23:00–01:00. (Anchor lost but app OK → B2-continuous base card, not a kill.)

## 18:15 — A — S3 RIG
✅ Deck, bar, chassis built; tile border round the motor bay; cards mounted; `component_frames.json` + USDZs exported.
🔴 Deck + bar only.

## 19:30 — A — S4 CARDS · all — M3
✅ S4: Gate A for deck/bar (at target / tray / lifted, ≥ 9/10 each), **0 unsafe errors**; σ measured → `params.yaml`.
✅ M3: live replanning + dependency catch on real G2; A films the 2-min insurance clip.
🔴 S4 → **Spatial lane dead.** A builds W4-lite 20:00–23:00.

## 20:00 — C — G2 PERCEPTION
✅ Bench under venue light: 19/20 correct states; 0 wrong commits.
🔴 **C stays on P0 entirely and never starts the spatial adapter. Spatial becomes visual-only; S6 + S7 cancelled. Nobody else picks up the adapter.**

## 21:30 — D — D VALVE · B — M10
✅ G3 green (21:00); rover bundle merged; WHY answering on the fixture. M10 2D supervisor up.
🔴 Answer engine limited to WHY / WHAT_NEXT / CAN_I / WHAT_DONE; menu item 2 hidden; review page → JSON diff. M10 → core-served text page.

## 22:00–22:30 — B — LAND SENTRY BRIDGE (B's polish valve)
✅ Devin PR green; touches only `integrations/sentry_bridge/`; runs on Mac 1 `nice -n 19`, read-only.

## 22:45 — trainer — MOTOR TRAINING DEADLINE
🔴 A2 dead; motor card.

## 23:00 — B — SENTRY KILL
✅ A live `glasses_instruction` trace from a **real** run visible in Sentry (screenshot posted).
🔴 **Sentry dead. Never reopened.**
**23:00 — A — W4-lite** (only if being built) · 🔴 → M10 2D supervisor.

## 23:30 — A — S5 MOTOR · D — CORE-FULL
✅ S5: motor Gate A (0° vs ±90° in the right direction ≥ 9/10 each; lifted; tray; hand covers → 0 state changes; **0 unsafe errors**) + Gate B (0 catastrophic flips; ≥ 90% frames tracked; re-acquire ≤ 1 s; ≥ 30 fps with 2 image anchors).
✅ CORE-FULL: `teardown.py`, inspect action, `requires_goal`, `/control/goal` unit-green.
🔴 S5 → motor card; spatial cannot lead. 🔴 CORE-FULL → merge CORE-MIN only; 90 s spatial script dead; +20 s add-on still possible.

## SUN 00:30 — STANDUP — C + D — S6 · D — F1
✅ S6: recorded sessions → adapter → core → G2 sim give exactly `LIFT DECK` → `REMOVE YELLOW BAR` → `TURN MOTOR 90° →` → `PUT BACK YELLOW BAR` → `PUT BACK DECK` → `● VERIFIED`, plus the premature deck; invariants green; rocket snapshots byte-identical.
✅ F1: Devin Fetch PR green against `core --mock-vision` with `GB_CORE_URL` set; Fetch clarification = yes; **D approves the isolated sponsor-client exception in writing.**
🔴 S6 → **Spatial visual-only. No more core spatial work of any kind.** 🔴 F1 → **Fetch dead.**

## 00:45 — D — CORE MERGE CUTOFF
✅ Spatial core additions merged (rocket snapshots byte-identical).
🔴 Nothing spatial merges into `core/` or `contracts/` again. **No schema change of any kind after this.** Stretch stops.

## 02:00 — D — P0 FREEZE
✅ 5 consecutive clean rocket runs; tag `p0-freeze`.
🔴 Nothing merges into P0 paths (D approves fixes only).

## 02:45 — all — PRIMARY FOOTAGE SECURED
✅ 2 full rocket takes (B through-lens, C table cam, Mac 2 screen) on **2 drives + cloud**.
🔴 S7 does not start until it is.

## 03:30 — A + D — S7 LIVE LOOP
✅ 10 live rotate trials: **0 wrong G2 instructions**; after 10 min without re-lock, seated motor + deck still CORRECT.
🔴 Visual-only add-on.

## 04:00 — all — PRODUCT FEATURE FREEZE
✅ Bugs + rehearsal only. No changes to `core/`, `contracts/`, `perception/`, `g2/`, `spatial/`, planner behaviour, P0/P1 behaviour.
The **only** exception: the isolated Fetch client (approved at 00:30), and only for landing, env config, Agentverse, ASI:One QA, client-local fixes.

## 04:15 — A + D — S8 SELECTION
✅ 5 consecutive clean 90 s spatial runs, ≤ 100 s each, 0 overrides, 0 wrong instructions. Then spatial footage 04:15–04:45.
🔴 **The rocket leads.**

## 05:45–07:15 — C — ROUGH CUT v1 = MASTER EDIT
✅ Complete submittable video from rocket (+ spatial) footage, with a marked insert point for an ASI:One beat; uploaded unlisted.

## 06:45 — B — EVEN BETA QA
✅ Beta build #N installed on physical G2: 5-min lock recovery, permission denial, root double-tap exit, relaunch, 2-min idle — **signed**.
🔴 **Fetch dead.** B stays on Even.

## 06:45–07:45 — B — FETCH LANDING (exception only)
✅ Land on B's laptop; `GB_CORE_URL=http://<MAC1-LAN-IP>:8787`; `GB_AGENT_ARMED=0`; mailbox connect; README name/address + badges; disarmed then armed ASI:One QA.
🔴 Any change needed outside `integrations/fetch_agent/` (core, contracts, perception, planner, G2, Spatial, interfaces, Beta rebuild) → **Fetch dead.**

## 07:45 — B — F2
✅ Live in ASI:One on the real rig: intent → state card → Approve → G2 instruction → status → VERIFIED card.
🔴 **Fetch dead.**

## 08:15 — B — F3
✅ Shared-chat URL saved; 20–30 s ASI:One clip delivered to A.
🔴 **Fetch dead.** No FETCH export.

## 08:30 — A / D / B — VIDEO · EVAL · SENTRY DECISION
✅ A: **GENERAL export 2:50–2:58** (through-lens G2, dark display, honesty labels).
✅ D: eval table with real n, incl. HUD changes per run + % dark/dimmed; then the optional generality proof if validated.
✅ B: `docs/sentry_findings.md` has ≥ 1 real **FINDING** + ≥ 1 real **DECISION** (with EVIDENCE + RESULT).
🔴 Video → ship rough cut v1. 🔴 Eval → delete unmeasured rows. 🔴 **Sentry → do NOT select the challenge.** 🔴 Generality proof → dropped.

## 08:30–09:00 — A — FETCH EXPORT
✅ Master edit + ASI:One beat → **3:10–3:30** export (only if F3 green).

## 09:00 — A — WORKDAY GATE 1
✅ Organizers confirmed multiple company challenges **and** the video exports are done.
🔴 Workday not entered.

**09:00–10:30 — Devpost + README**
- A: overall / Even (app name, three answers, quiet metric if measured) / Beyond the Digital; **MLH Commit opt-in + supplemental form**; Workday paragraph only after Even text is done.
- B: Even table — confirm Beta in person; Sentry section + 3 screenshots (only if entered); Fetch README section; **create the Submission Agent entry** (video = FETCH export).
- D: technical section; README: install/run on G2, accounts, API keys; repo public; no secrets.
- **all: join the Fetch Submission Agent with the Team ID** (status "Submitted").
- **Final challenge selection:** Even ✓ · Beyond the Digital ✓ · Commit ✓ · Sentry only if entry condition · Fetch only if F1–F3 green · Workday only if both gates · **never** Cognition or StepFun.

## 10:30 — all — SUBMISSIONS MATERIALLY COMPLETE
✅ Devpost submitted; every selected challenge's materials complete; code freeze.
🔴 **Deselect any incomplete sponsor rather than submit it half-done.** Workday gate 2 fails → not entered.

## 11:00 — D / B — LEAD + FINAL BETA
✅ D: lead per 18 v3 §9 after one table rehearsal (re-lock + reset < 40 s). B: final Beta pushed; QA signed.
🔴 Any lead condition red → **the rocket leads. Ties go to the rocket.**

## 12:00 — DEADLINE
✅ Devpost + Beta + Submission Agent all in. Fetch agent running **disarmed** for judging (if alive).

---

**At the table (12:30–15:00):** Even judge → glasses first, end on dark. Fetch judge → ASI:One first (arm, demo, disarm). Sentry judge → same run, then trace + abstention log + one finding→decision. Everyone else → the loop, not the sponsors. Return the G2 before leaving.
