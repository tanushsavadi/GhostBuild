# 14 — Timeline (Sat Oct 17 12:00 PM → Sun Oct 18 12:00 PM PDT) — final reconciliation 2026-10-16

> **Final reconciliation.** Replaces the ambition-pass timeline with 18 v2 §12.2, amended by 18 v3 (**contracts LOCKED 12:45, one lock**; D's slots per 18 v3 §4.3; the 15:00 SP5 row removed; every 18 v3 §8 clock) and the sponsor overlay (19 §11, with its final amendments: table visits 11:30–12:00, Devin dispatch 15:00–15:05, Fetch under the isolated sponsor-client exception, two video exports). Gate actions: 03 §Gates and `21_HACKATHON_CHECKLIST.md`. Rule for every row: **one person, one task per slot.**

**Fixed external events** [V: live.lahacks.com/schedule, Even starter pack]:
- **Sat:** G2 application 9:00–12:00 · opening 11:00 · loan decisions 12:00–12:30 · **Even workshop 15:00–16:00** · **Even table closes 20:00**.
- **Sun:** Even table reopens 9:00 · **deadline 12:00** (Devpost + Beta + Fetch Submission Agent) · judging 12:30–15:00 · winners 16:00.

**Principles:** ugly end-to-end on mocks by 14:30 (M1) · real G2 + Beta transport by 15:00 (G0) · real physical replanning on G2 by 19:30 (M3) · **P0 freeze 02:00** · rocket footage secured by 02:45 before any late spatial gate · product feature freeze 04:00 · every P1 item reaches its gate or dies, and is never reopened.

## Friday night (no project code)
S0 (A + trainer owner) · F0 Fetch example (A) · Sentry DSN (A) · Devin login + briefs in notes (A) · purchases and prints (C) · Funnel test, iFixit PDF saved (D) · Even CLI/simulator (B).

## Saturday
| Time | A (spatial + captain) | B (G2/Beta/M10/sponsor landing) | C (perception → adapter) | D (core/knowledge → spatial core) | Trainer Mac | Gate |
|---|---|---|---|---|---|---|
| 09:00 | check-in | **G2 borrow form** | check in; **borrow Logitech webcam** | check in; ask Studio-model rule + multi-challenge rule | idle | |
| 11:00–11:30 | opening: listen for the multi-challenge rule, prizes, any Sentry/Fetch form | opening | opening | opening | | |
| 11:30–12:00 | **sponsor table visits** (Fetch, Sentry, Even; ≤ 5 min each; Discord if unstaffed) | — | — | — | | |
| 12:00–12:15 | kickoff | ← | ← | contracts + frame rule | | |
| 12:15–12:45 | motor: build + Studio | scaffold plugin; simulator | build board, mount camera, record | **core + spatial contracts + every fixture → LOCK 12:45** | | G2 loan 12:30 · **Contract lock 12:45** |
| 12:45–13:15 | motor: build + Studio | scaffold plugin | board, camera, record | planner TDD | | |
| 13:15–13:45 | motor USDZ, viewport dims ±1 mm, **kick training** | mock HUD on simulator; pick up G2 | rectification + LAB | planner TDD | **motor job starts** | **S1 13:45** |
| 13:45–14:30 | rocket Studio model + PDF + LDraw export | stub `.ehpk` → Beta; ladder; lock test | rectification + LAB → first live per-cell | LDraw parser on a sample `.ldr`; merge mocks | training | **M1 14:30** |
| 14:30–15:00 | rocket model (to 14:45) → app floor starts 14:45 | ← stub Beta / ladder | first live per-cell | golden target from `rocket.ldr` | | **G0 15:00** |
| 15:00–16:00 | app floor: ARView, USDZ, debug overlay | **15:00–15:05 read G0, paste Devin briefs A + B; then Even workshop** (ask LAN `ws://` in Beta) | calibration + part fit; hands | K1 extraction run + planner TDD | | Devin dispatched by 15:15 |
| 16:00–16:45 | app floor: base lock + transform tests | menu → `g2_input` (items 1–5); iOS help 16:00–16:30 only if A is red | **V2 hands** | answer engine | ETA check | V2 16:00 · S2 checkpoint 16:45 |
| 16:45–18:15 | rover modules + cards + `component_frames.json` | **M10 2D supervisor** (17:00–) | bench under venue light | validator + review | | **K1 17:00** · **S2 kill 17:30** · **S3 18:15** |
| 18:15–19:30 | A1 tracking + seated calibration | plugin on hardware fed by real core; answer slot; menu answers on G2 | tune; Plan B tags if failing | **first physical event → HUD on real G2** | | **S4 19:30** |
| 19:30–20:00 | ← all four: **M3** live replanning + dependency catch on hardware; A films a 2-min insurance clip inside it → | | | | ETA check | M3 |
| 20:00–20:20 | dinner | dinner | dinner | dinner | | **G2 perception 20:00** · Even table closes |
| 20:20–20:50 | sender + recorder; record 4 sessions | first full Beta QA pass | adapter on synthetic poses (**only if G2 green**; else P0) | bundle == golden test | | |
| 20:50–22:00 | `twin` v2 receiver, ghost, diff | Beta QA; M10 finish (to 21:30) | adapter on A's recordings (or P0) | **G3 21:00**; rover bundle 21:00–21:30; planner additions | done ≈ 17:30–21:45 | G3 21:00 · **D valve 21:30** · M10 21:30 |
| 22:00–22:50 | arc/arrow, honesty chips | **22:00–22:30 land Sentry bridge** (polish valve); 22:30–22:50 polish | rig bench: lighting, thermal soak, drift | planner additions + teardown + `/control/goal` + `twin` v2 | | training deadline 22:45 |
| 22:50–23:30 | A2 motor test (C is the hand) | reconnect/lock hardening; **23:00 post Sentry trace screenshot** | assist S5 (hand) | CORE-FULL to unit-green | | **Sentry kill 23:00** · W4-lite 23:00 (only if built) · **S5 + CORE-FULL 23:30** |
| 23:30–00:30 | select + explode + teardown | hardening | **S6 replay with D** | **S6 replay with C** | | **S6 00:30** |

**If spatial is killed at S2 (17:30):** A builds W4-lite 17:30–20:00 (gate 23:00), then owns Fetch 23:00–01:00. **At S4 (19:30):** A builds W4-lite 20:00–22:30, then Fetch 23:00–01:00.

## Sunday
| Time | A | B | C | D | Gate |
|---|---|---|---|---|---|
| 00:30–01:00 | finish teardown viz / buffer | Beta build | P0 tuning | **00:30 standup: S6, F1, approve or refuse the Fetch exception**; merge spatial core additions (rocket snapshots byte-identical) | **F1 00:30** · **core merge cutoff 00:45** |
| 01:00–02:00 | ← 5 consecutive clean **rocket** runs → | | | | **P0 FREEZE 02:00** |
| 02:00–02:45 | ← **primary submission footage (rocket):** 2 full takes; B through-lens, C table camera, Mac 2 screen record; copy to 2 drives + cloud before anyone leaves → | | | | **footage secured 02:45** |
| 02:45–03:30 | **S7 live spatial** (operator) | sleep 02:45–05:45 | sleep 02:45–05:45 | S7 (wears G2 as the judge) | **S7 03:30** |
| 03:30–04:15 | **S8: 5 clean spatial runs** | | | S8 | **product feature freeze 04:00** · **S8 04:15** |
| 04:15–04:45 | spatial footage (lead or add-on version) | | | ← | |
| 04:45–05:45 | sleep 04:45–07:45 | sleep | sleep | sleep 04:45–07:45 | |
| 05:45–06:45 | | **Beta build #N + QA → signed by 06:45** | **05:45–07:15 rough cut v1 = the master edit** (rocket + spatial if captured; marked insert point for an ASI:One beat) | | **Even Beta QA 06:45** |
| 06:45–07:45 | | **Fetch landing under the isolated sponsor-client exception** (only if F1 + exception + Beta QA green): set `GB_CORE_URL`, mailbox connect, README badges, disarmed then armed ASI:One QA, **F2 run** (B is supervisor and technician) | 07:15–07:45 reset kits; P0 check | | **F2 07:45** |
| 07:45–08:30 | final video: narration, captions, honesty labels → **GENERAL export (2:50–2:58)** | final QA; record the shared chat alongside one of C's rehearsal runs → **20–30 s ASI:One clip to A by 08:15** | rehearse 5× (both scripts) | **eval table incl. E-a quiet metric first**; then the optional generality proof (07:45–08:30) | **F3 08:15** · **Video / eval / Sentry decision 08:30** |
| 08:30–09:00 | **FETCH export (3:10–3:30)**: master edit + ASI:One beat (only if F3 green) | final QA | rehearse | eval polish | FETCH export by 09:00 |
| 09:00–10:30 | Devpost: overall / Even / Beyond the Digital; Commit opt-in + form; Workday paragraph only if gate 1 held | Even table: confirm Beta in person; Sentry section + screenshots (only if entered); Fetch README section; create the Submission Agent entry | rehearse with outsiders (90 s + 45 s) | Devpost technical section; README (G2 install/run, accounts, API keys) | **Workday gate 1 09:00** |
| 09:00–10:30 | ← all four join the Fetch Submission Agent with the Team ID (≈ 5 min each, if Fetch alive) → | | | | |
| 10:30 | ← **submissions materially complete; code freeze; deselect any incomplete sponsor** → | | | | **10:30** |
| 11:00–12:00 | buffer; table rehearsal; D picks the lead per 18 v3 §9 | **final Beta pushed; QA signed** | pack rocket + rover reset kits | **lead decision**; tag release | **11:00 lead + final Beta** · **deadline 12:00** |
| 12:30–15:00 | Judging (11_DEMO_RUNBOOK) | | | | |

## Non-negotiables
- No first integration after 14:30 Sat. First Beta build by 15:00 Sat, not Sunday.
- Contracts lock once at 12:45; no schema change after 00:45.
- Nothing merges into P0 paths after 02:00 without D; nothing optional runs before the 02:45 footage is secured.
- Product feature freeze 04:00; the only exception is the isolated Fetch client, and only under its nine conditions.
- Even outranks Fetch: Fetch does not start until Even Beta QA is signed.
- A's FETCH export happens only after the GENERAL export exists.
- Devpost and every selected challenge are materially complete by 10:30; nothing new after 11:00 except the final Beta push.
