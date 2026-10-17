# 11 — Demo Runbook (final reconciliation 2026-10-16)

> **Final reconciliation.** One GhostBuild story, two possible leads. **Spatial leads only if the 18 v3 §9 lead rule holds at the 11:00 decision; otherwise the rocket leads** (ties go to the rocket; D calls it). Questions use the G2 temple-tap **menu**, never voice (voice is P2 and is not in any script). Removed from the scripts: the "+15 s iFixit" beat (the compiler card lives on Devpost only), the pen/VLM beat (cut), the hero-tag beat (cut). "D turns the twin" became "D points at the 2D supervisor" (or the W4-lite twin if it was built). Sponsor judging changes emphasis, not the product (§Sponsor variants).

**Roles:**
- **Demo captain:** Person A (talks; points at the second screen only after a catch).
- **Operator:** Person C (rocket board, rover reset, recalibration, operator keys).
- **G2 wrangler:** Person B (fit, brightness, connection, battery, phrase card; Sentry laptop and Fetch agent when those judges are present).
- **Second-judge host + lead caller:** Person D (answers technical questions; calls the lead per 18 v3 §9 at 11:00).

## Which demo leads (decided at Sun 11:00)
| Gate result | Lead | Add-on |
|---|---|---|
| P0 freeze + footage secured; S5 markerless Gate A + B; S6 + S7 (0 wrong G2 instructions); CORE-FULL merged by 00:45; S8 5 clean 90 s runs; re-lock + reset < 40 s at the table; phone ≥ 30 fps, no thermal warning after 10 min; rocket set up as instant fallback | **Spatial 90 s** (§S1) | rocket on the same table as fallback |
| S6 + S7 + S8-level reliability but the motor is on a card (S5 not markerless) | **Rocket** (§R) | +20 s spatial add-on with a G2 claim; say "That card is how it tracks this part." |
| Only S4 passed | **Rocket** | visual add-on, no G2 claim: "Here's the CAD following the real motor. That part isn't wired to the glasses yet." |
| Spatial dead | **Rocket** | none (W4-lite twin or 2D supervisor for the second judge) |

## Table layout
```
   [judge stands here, facing the work]
   ┌──────────────────────────────────────────────┐
   │ LED panel   webcam arm (Mac 1)               │   Mac 2: 2D supervisor / phone mirror
   │  ┌─────────┐        ┌───────────────────┐    │   angled to the SECOND judge, not the wearer
   │  │ ROCKET  │ tray   │ ROVER on mat      │    │   phone 1 (Even app, HUD mirror) on stand
   │  │ BOARD   │ (green │ + base card;      │    │   spatial phone on gooseneck, far side
   │  └─────────┘  2x2)  │ tray for deck/bar │    │   phrase card: menu items + 3 Even answers
   └──────────────────────────────────────────────┘   Sentry laptop / Fetch laptop (B) only when needed
```
Tape the arm, the board corners, the mat and both Macs' positions. Keep a spare pre-built board and the spare webcam under the table.

## §R Rocket script (P0; lead unless spatial qualifies)

### Build & starting state (the defect card)
- Target "Rocket" (Studio model; manual = its instruction PDF, team-authored). The **black 2×4 cap bridges red 2×4 and green 2×2**.
- Start: (1) red 2×4 **flipped 180°** (dot toward the judge) **under the cap**; (2) green 2×2 **missing** (in the tray), so the cap rests on red only; (3) *(long version only)* blue 2×2 shifted one stud.
- The target picture is not on the table.

### The 90-second run
| t (s) | What happens | G2 HUD | Captain line |
|---|---|---|---|
| 0–10 | Captain gestures at the board | (idle) | "GhostBuild read this build's manual. It watches the work and tells you only the next thing to do. This build has mistakes you can't see. Put these on." |
| 10–22 | B fits G2 | `LIFT BLACK 2x4` / `OFF THE TOP FIRST` + map | "Ask it why: tap and hold the right temple for the menu." |
| 22–30 | Judge: menu → `WHY THIS STEP?` | answer `RED UNDER IT IS FLIPPED` / `[MANUAL STEP 6]` | (silence) |
| 30–40 | Judge lifts cap (HUD dims while hands are in view), then turns red | `TURN RED 2x4` / `DOT AWAY · 180°` → `ADD GREEN 2x2` / `SEE MAP` | |
| 40–48 | Judge: menu → `CAN I SKIP?` | answer `NOT YET` / `GREEN FIRST` | "Try it anyway: put the black back." |
| 48–58 | Judge puts the cap back early | `X CAP TOO EARLY` / `LIFT IT · GREEN FIRST` | D points at the 2D supervisor: "It saw the cap go on before what supports it. It didn't skip ahead; it replanned from what you did." |
| 58–72 | Judge lifts cap, places green, puts cap on | `ADD GREEN 2x2` → `PUT BACK BLACK 2x4` → `● VERIFIED` / `MATCHES TARGET` | |
| 72–80 | HUD goes dark | (blank, faint ●) | (one beat of silence) "And now it's quiet, because nothing is wrong." |
| 80–90 | Captain points at the supervisor's provenance + turn log | — | "Every instruction came from live perception, checked against a task graph compiled from the CAD, with steps cited from our manual. **Instructions tell you what to do. GhostBuild checks what you did.**" |

**If the judge stays for more (+20 s, gated only):** the spatial add-on per the lead table above (the 5–20 s beat of §S2).

### 45-second rocket version (crowded rounds; judge already wearing G2)
Only the green is missing under the cap.
1. `LIFT BLACK 2x4` → judge lifts it.
2. `ADD GREEN 2x2` → judge places green one stud off → `X WRONG SPOT` / `MOVE GREEN 1 LEFT` → judge fixes it.
3. `PUT BACK BLACK 2x4` → `● VERIFIED` → dark.
4. One menu `WHY THIS STEP?` if time allows.

## §S Spatial scripts (copied verbatim from 18 v3 §10; spatial lead only under the lead rule)

**Script rules:** only gated-in claims are spoken. "No marker on that motor" is said **only if S5 passed markerlessly**; with a carded motor the line is "That card is how it tracks this part." Never say the motor "isn't broken"; if asked "Is the motor OK?": "It checked the installation. Whether the motor runs needs an electrical test, and GhostBuild doesn't do that here." Every visible and spoken claim is classified in 18 v3 §10.3 (claim audit); nothing outside that table is said.

### S1. 90-second spatial script

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

### S2. 45-second spatial script

**Start state.** Deck and bar on the tray, motor at +90°, goal `FIX MOTOR ASSEMBLY` pre-set, base re-locked.

| t (s) | Beat | HUD |
|---|---|---|
| 0–5 | "The rover's CAD, locked to the real rover. Goal: fix the motor assembly. It measured the motor: 90° off its documented orientation." | `TURN MOTOR 90° →` / `GEAR TO THE RIGHT` |
| 5–20 | **The judge turns the bare motor; the CAD follows, 90° → 0°.** "No marker on that motor." | `●` → `PUT BACK YELLOW BAR` |
| 20–30 | "Put the deck on first." → caught | `X DECK TOO EARLY` / `LIFT IT · BAR FIRST` |
| 30–40 | Bar, then deck | `● VERIFIED` / `MATCHES TARGET` |
| 40–45 | HUD dark. Closing line from §10.1. | — |

**When the rocket leads** (§R above, with the menu), the spatial add-on is **+20 s**, using the 5–20 s beat above, and only if S7 passed. If only S4 passed: "Here's the CAD following the real motor. That part isn't wired to the glasses yet."


## Sponsor variants (30 s each; same physical run, different emphasis; full text in 19 §10)
- **Even judge (glasses first):** "Put these on. Fix what it tells you." → instruction → action → mistake (`X … TOO EARLY`) → correction → `● VERIFIED` → dark; one beat of silence. Then the three answers (who / when / why G2) and, only if measured, "In a full run the display changed __ times and was dark or dimmed __% of the time." The phone twin is for the second judge.
- **Fetch judge (only if F2 green; ASI:One first):** the supervisor types "Fix the motor assembly on the bench rover" → state card → plan card → Approve → the technician's G2 lights up → "status?" → "measured 90° off → rotate" → VERIFIED card. "The supervisor never leaves ASI:One. The planning is GhostBuild's verified planner; the agent orchestrates it, can't instruct without approval, and reports only what was observed." Disarm (`GB_AGENT_ARMED=0`) afterwards.
- **Sentry judge (only if entered):** the same physical run, then on B's laptop: the trace of the instruction they just saw (camera frame → vote → planner → glasses render; say where the time goes only as the trace shows), the log line where it refused to instruct while a hand covered the part, and one FINDING → DECISION → RESULT entry from `docs/sentry_findings.md`, read verbatim.
- **Overall / Beyond the Digital:** the physical↔digital loop and reality-driven replanning; do **not** list sponsors.

## Menu fallbacks during the run
- The judge can't open the menu: B says "tap, then hold" and demonstrates once; never type a judge's question on the operator console unless it is labelled "typed question".
- If the 21:30 D valve fired, item 2 (`WHERE DOES IT GO?`) is hidden; don't mention it.

## Reset procedures (target < 40 s each)
- **Rocket:** `R` on the operator panel → lift cap → flip red (dot toward judge) → green to tray → cap back on red → check the supervisor shows the expected diff and the HUD shows `LIFT BLACK 2x4`.
- **Rover (18 v2 §7.5):** deck off → bar off → motor to the "reset" sticker (yaw +90°, gear pointing away) → bar on, deck on → `R` → tap **Re-lock base** (≈ 2 s; re-lock only between runs).
- Wipe the G2 nose pads; check G2 + phone batteries (charge between rounds).

## Pre-judging checklist (Sun 12:00–12:30)
- [ ] Mac 1: `caffeinate -d`, power, `make demo`, notifications off; spare webcam on the table
- [ ] Mac 2: 2D supervisor (or W4-lite) full screen; QuickTime phone mirror ready; recording ready
- [ ] Phone 1: auto-lock Never, Do Not Disturb, Beta build open, brightness fixed
- [ ] Spatial phone (if spatial is shown): charged, cool, app open, base re-locked; ≥ 30 fps
- [ ] `/health`: `g2_connected`, `spatial_connected` (if used)
- [ ] Recalibrate at the table (`C`); 1 full rehearsal of the lead script
- [ ] Sentry laptop logged in (only if Sentry entered); Fetch agent running **disarmed** on B's laptop with `GB_CORE_URL` pointing at Mac 1 (only if Fetch alive)
- [ ] Spare dots, bricks, pre-built board, phrase card
- [ ] Backup video (GENERAL export) on both Macs + phone
- [ ] G2 charged; case nearby

## If something breaks mid-demo
| Symptom | Action (≤ 10 s) | Say |
|---|---|---|
| HUD `OFFLINE` | Tap the temple; B checks `/health` | "Reconnecting to the workstation." |
| Wrong reading | C presses `F`, fixes the board / recalibrates | Own it: "It misread. Here's what it saw" (point at the perception panel). Never cover with an unlabelled override. |
| HUD holds / `CHECKING` during spatial | Keep hands still; let it re-acquire | "It waits until it's sure." |
| Spatial session interrupted (base unset) | Finish on the rocket; re-lock only between runs | "The phone lost its lock, so it refuses to commit anything. Let's do the rocket." |
| Supervisor frozen | reload `?mode=2d` | — |
| Fetch / Sentry process misbehaves | Kill the process; GhostBuild is unaffected | — |
| Total failure | Backup video + replay | "Here's the same run recorded this morning." |
