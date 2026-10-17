# 13 — Team Plan (final reconciliation 2026-10-16)

> **Final reconciliation.** Replaces the ambition-pass table with 18 v2 §11.2 (as amended by 18 v3 §4.3 and §8) plus the sponsor overlay in 19 §11. Voice is demoted to opportunistic P2 to fund the spatial loop. The clock-ordered list is `21_HACKATHON_CHECKLIST.md`; hour-by-hour is `14_TIMELINE.md`.

## Role philosophy (frozen)
| Person | Role | Never |
|---|---|---|
| **A** | Captain + spatial (app, rig, motor asset, training kick-off) + story/demo/video | — |
| **B** | G2 plugin / network / Beta + 2D supervisor (M10) + **lands** sponsor clients (Sentry, Fetch) + QA | lets sponsor work delay Even: Fetch starts only after Beta QA is signed at 06:45 |
| **C** | P0 perception and testbed first; `adapters/spatial_pose` **only after G2 perception passes at 20:00** | gets sponsor work; starts the adapter if G2 is red |
| **D** | Contracts, core, planner, knowledge, answer engine, integration authority; reads every gate | puts sponsor work on the core critical path (D only reads F1 and approves/refuses the Fetch exception) |
| **Devin** | Isolated sponsor-integration coding only: `integrations/sentry_bridge/`, `integrations/fetch_agent/` | touches `core/`, `contracts/`, `perception/`, `g2/` or `spatial/` (unless a human explicitly changes this plan before the hack) |

If a Devin PR is red at its gate, that sponsor feature dies. No core team member is moved onto rescue work (the only exception: A after a spatial kill, 19 §11).

## Capacity (be honest)
- **Supply:** 24 h − 3 h sleep − 1.25 h meals/kickoff − 1.5 h final submission/judging prep ≈ **18 h awake-work per person**, ≈ 72 h total.
- **Demand (engineering + shared + other, in-hack):**

| Person | Lane (h) | Shared (M3 0.5 + P0 freeze runs 1.0 + rocket footage 0.75) | Other | Sponsor (19) | Total | vs ≈ 18 | Release valve (in order) |
|---|---|---|---|---|---|---|---|
| **A** | 13.2 (motor 1.5 · rocket model 1.0 · app floor 2.0 · rover + cards 1.5 · A1 1.25 · sender 0.5 · `twin` v2 + ghost + diff 2.0 · A2 0.67 · select/explode/teardown 1.25 · S7/S8 1.5) | 2.25 | final video 0.75 · Devpost 1.5 · captain 1.0 | FETCH export 0.25 · Commit 0.15 · Workday 0.25 (optional) | **≈ 19.3** | +1.3 | Workday paragraph drops first; FETCH export only if F3 green; S2/S4 kills return A to W4-lite |
| **B** | 17.0 (HUD 8 · ladder 3 · Beta QA 4 · menu 2 · M10 1.5 · iOS help ≤ 0.5 only if S2 red) | 2.25 | rehearsal 0.5 | Devin dispatch 0.05 · Sentry land 0.5 (inside the polish valve) · Fetch land 1.25 (after Beta QA) · chat clip 0.25 · findings log 0.25 · Sentry Devpost 0.5 · Fetch README + Submission Agent 0.35 | **≈ 21.2** (≈ 20.7 net of the polish valve) | +2.7 | minimap polish → glyph polish → **Fetch** (dies if Beta QA isn't signed by 06:45) → Sentry Devpost section (only if entered) |
| **C** | 19.0 (perception 12 · testbed 2 · hands 2 · adapter 1.5 · rig bench 1.5) | 2.25 | rough cut v1 1.5 | **0** | **≈ 22.75** | +4.75 | V2 hands → motion gate at 16:00; **G2 red at 20:00 → C stays on P0, adapter never starts, spatial visual-only** |
| **D** | 21.25 (planner 9 · contracts 2.5 (incl. spatial schemas, one lock 12:45) · compiler 5 · answers 3 · spatial core 2.75 · −iFixit) | 2.25 | eval + README 1.0 | F1 read + exception decision 0.05 · E-a quiet metric 0.25 (inside the eval slot) | **≈ 24.8** | +6.8 | **K1 17:00** → authored evidence (−2) · **21:30** → engine limited to WHY/WHAT_NEXT/CAN_I/WHAT_DONE, review page → JSON diff (−1.5) · **23:30** → CORE-MIN only (−1.5) · generality proof dropped at 08:30 |

**Overall:** ≈ 88 h of demand against ≈ 72 h of supply. **The plan expects the 17:00, 21:30 and 23:30 valves to fire** (18 v3 §8). They are written as conditions so that work which turns out green is kept, not because firing them is a failure. Sponsor work adds **0 h to C**, ≈ 0.3 h to D (no core-path time), and lands on B only inside pre-agreed slack (the 22:00 polish valve, the post-QA Sunday hour, the 09:00–10:30 Devpost window).

**Machines.** Mac 1 = perception + core (never runs the spatial app or training). Mac 2 = phone mirror + 2D supervisor + recording. A's Mac = Xcode + device builds (never training). **Trainer Mac** = a borrowed Apple-silicon Mac (ask Friday) or D's laptop if it is not Mac 1; B's laptop cannot be the trainer because S1 (13:45) precedes G0 (15:00) [verify machine assignment at S0]. B's laptop also runs the Fetch agent ("Laptop 3").

## Merge model
- Each owner merges their own module **behind a flag**. D reviews any change to `contracts/` and any change in P0 paths after 18:00.
- **Contracts:** one lock at Sat 12:45; afterwards a shared-schema change needs D plus every consuming owner (05 approval table), posted in chat; after 00:45 none at all.
- Spatial core additions are additive, flag-guarded, and merged by **00:45**. **P0 freeze tag at Sun 02:00.** **Product feature freeze 04:00** (the only exception: the isolated Fetch client, 03).
- Sponsor code merges only into `integrations/*`; a PR touching anything else is rejected.

## Unblocking rules
- Nobody waits. Every vertical starts on fixtures/mocks; no consumer needs a contract before 13:15.
- Blocked > 20 min: say so, switch to the mock, keep moving.
- D runs a 5-minute standup at each gate clock (21): green or red. Not green = red. Killed work is never reopened.

## Sleep plan
- B and C: 02:45–05:45. A and D: 04:45–07:45. Nobody sleeps before the Sun 02:45 footage is secured.

## Pre-event prep (no project code before 12:00 Sat)
| Who | Task |
|---|---|
| All | Node 20+, Python 3.11 + `uv`, git, Claude Code + the Even plugin (15 §4); join Discords; API keys (Anthropic) in a password manager, never in git |
| A | **S0:** spatial iPhone on iOS 27; Xcode 27 signs a hello-world to it; `xcrun createml objecttracker -h` on the trainer Mac + a sample-job ETA; Blender + ImportLDraw sample export. Install BrickLink Studio (+ LeoCAD fallback). **Sponsor accounts (0.75 h, no project code):** Agentverse + ASI:One + promo, run the official ASI-compatible example and confirm it answers in ASI:One (**F0**), then delete it; Sentry org + Python project + DSN in the password manager + SDK quickstart; Devin login; paste 19 Appendices A and B into team notes |
| B | Even app signed in, developer mode enabled; `npm i -g @evenrealities/evenhub-cli @evenrealities/evenhub-simulator`; watch Even EP 02–09; **G2 borrow form at 9:00 AM Sat**. Add nothing to the G2 whitelist for sponsors |
| C | Buy: 16×16 plate, bricks (red/blue/yellow/black + green; 2×2, 2×4; spares), black 2×4 cap, ¼″ white matte dots, foam core, USB webcam + clamp arm, LED panel, tape. Print ArUco `DICT_4X4_50` IDs 0–3 (30 mm) + grey patch. **Sat 09:00: borrow a spare Logitech webcam from the Hardware Lab** (the only Hardware Lab action) |
| D | Tailscale + Funnel test (`tailscale funnel 8787`), note the `*.ts.net` name; download the LDraw library zip and three.js; save a PDF print of iFixit guide 158506 for the optional offline proof; **ask organizers at check-in whether designing the LEGO models in Studio before 12:00 is allowed, and whether multiple company challenges may be selected** |
