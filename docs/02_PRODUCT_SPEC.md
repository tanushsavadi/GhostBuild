# 02 — Product Spec (post–ambition pass; final reconciliation 2026-10-16)

> **Final reconciliation.** Product wording and the spatial goal follow 18 v3; questions go through the G2 temple-tap menu (voice is P2 opportunistic); the external-guide generality proof is offline and optional ("compiled, not executed"). Operational summary: `20_FINAL_IMPLEMENTATION_BIBLE.md`.

## Product
**GhostBuild: an AI copilot for physical work.**
- Give it the manual (instruction PDF, service guide, repair guide) and, where available, the CAD model.
- It watches the work and keeps an explicit model of the physical state.
- It shows the smallest next action on Even G2, verifies what you did, and replans from reality.
- It answers your questions grounded in the manual, the live state, and your task history.

"An expert standing beside you who has read the manual, can see the object, remembers every step, and stays in your line of sight."

LEGO is the controlled test rig. The product is the loop:

goal → documentation / CAD → physical observation → world state → current-vs-target diff → planner / replan → G2 next action → human acts → verify → repeat → `● VERIFIED` → G2 quiet.

It is **not** a LEGO builder, an AR LEGO toy, a chatbot on glasses, an autonomous robot, or a VLM deciding physical state. The controlled rigs (the rocket grid and the rover) are testbeds for a general physical-AI architecture.

## Problem
Every guide (paper, app or glasses) advances when you say so and assumes the previous step was right. The costly errors are the unnoticed ones: a part flipped, one position off, missing, or put back too early. Finding them means stopping, putting things down, and searching a manual.

## Users & moments [D]
- **Primary story:** someone assembling or repairing something with a manual, hands full.
  - e.g. a service repair from a manual, building a kit, bench/rack setup (Even's brief names "repair guides" and "lab protocols while your hands are full").
- **Testbeds:** (1) the **rocket**, a LEGO build designed in BrickLink Studio on a registered grid, so we own its instruction PDF and exact CAD (P0); (2) the **rover**, a LEGO System assembly with exact CAD and a team-authored one-page service sheet, used for the spatial prototype. The rover goal is **"Fix the motor assembly"**: access, inspect and correct the installation. It is never "replace the motor", and GhostBuild verifies installation state, not motor function.
- **Avoid:** medical framing (Even Hub disallows medical apps [V]).

## Core experience
1. **Ingest (once):** the manual + CAD are compiled into a task graph with page-cited evidence. Provenance is shown: graph from CAD, step text read by Claude, match score, reviewer.
2. The judge wears G2. The HUD shows one action plus a tiny map: `LIFT BLACK 2x4`.
3. **Ask any time:** tap-then-hold the temple for the menu (`WHY THIS STEP?` · `WHERE DOES IT GO?` · `CAN I SKIP?` · `WHAT'S DONE?` · `WHAT NEXT?`): "Why?" → `RED UNDER IT IS FLIPPED / [MANUAL STEP 6]`. *(Hold-to-ask voice only if it opportunistically ships; P2.)*
4. **Act:** the HUD dims while hands are over the board. About 1 s after they leave, the action is verified and the next one appears. Out-of-order valid work is accepted.
5. **Skip ahead:** `CAN I SKIP?` → `NOT YET / GREEN FIRST`. Do it anyway → `X CAP TOO EARLY / LIFT IT · GREEN FIRST`.
6. **Done:** `● VERIFIED`, then the HUD goes dark.
7. **Second person:** sees the spatial phone's live CAD twin mirrored on Mac 2 (if spatial passes its gates) or the 2D supervisor page (live perception, plan, question log with citations, provenance).
8. **Generality (optional, offline):** the same compiler compiles one real external repair guide; Devpost/README show its components, steps, warnings and evidence, captioned "compiled, not executed". There is no live guided mode.

## Quiet Tech rules (requirements)
- **R1:** The HUD changes only when the next action, an alert, progress, or a requested answer changes.
- **R2:** No instruction comes from uncertain perception; abstain instead.
- **R3:** The user never needs the phone or laptop during the task.
- **R4:** ≤ 2 short lines + map; answers ≤ 2 lines + evidence tag; answers expire after 8 s.
- **R5:** When nothing is wrong, show nothing.
- **R6:** No audio output, no continuous listening, no partial transcripts on glass.
- **R7:** Every answer is grounded: rendered from planner state with a manual evidence tag, or `MANUAL DOESN'T SAY` / `? SAY AGAIN`.
- **R8:** Unknown state never produces a confident physical instruction. Safe abstention beats a wrong instruction.

## Out of scope
Arbitrary objects without registration; handheld scanning; 3D reconstruction; LiDAR depth for state (LiDAR occlusion is cosmetic stretch only); multi-user; cloud accounts; live G2 guided mode for documentation-only tasks (cut); functional (powered) verification of the rover motor.

## Success criteria (demo-level)
- A first-time judge completes the 90-second run without coaching beyond "put these on; tap and hold the temple for questions".
- The dependency catch fires with a reason, and the judge's question gets a cited answer.
- 0 wrong instructions during judging.

Positioning artefacts (pitches, novelty, judge Q&A): 00_STRATEGY (ambition-pass block) and 17.
