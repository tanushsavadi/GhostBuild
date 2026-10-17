# 01 — Prize Strategy (final)

> **Final reconciliation (2026-10-16).** Sponsor decisions come from `19_SPONSOR_AND_TRACK_STRATEGY.md` plus its final amendments; the one-page summary is `20_FINAL_IMPLEMENTATION_BIBLE.md` §11 and §17. Superseded here: StepFun as a conditional third target (dropped), "Fetch.ai not pursued" (now a conditional secondary), "Sentry not pursued" (now secondary), and hold-to-ask voice as the judge's question path (the temple-tap menu is; voice is P2).

Owner: whole team. A owns the Devpost copy for Even, Overall/Beyond the Digital, Commit and Workday; B owns the Sentry and Fetch sections. Full track inventory: 19 §3.

**One product, not sponsor soup.** Sponsor judging changes the emphasis of the same run, never the product (20 §15).

## Targets

| Rank | Target | Role | What sponsor tech owns | Kill |
|---|---|---|---|---|
| 1 | **Even Realities: Smart Glasses Challenge** | PRIMARY | The whole user-facing guidance surface: the next verified action, menu questions, silence when correct | none of its own; no G2 loan → Even effectively lost (08 §14) |
| 2 | **Sentry: Best Use of Sentry** | SECONDARY | Live observability: photon-to-HUD traces, instruction audit trail, abstention log | Sat 23:00 live trace; Sun 08:30 real finding **and** decision |
| 3 | **Fetch.ai: ASI:One Agent Challenge** | CONDITIONAL SECONDARY | Remote physical-job supervision: intent → inspect → plan → approve → dispatch → status → verified report, all in ASI:One | F0 Fri · F1 Sun 00:30 · F2 07:45 · F3 08:15 |
| — | **Beyond the Digital** (organizer track) | GENERAL | The physical↔digital loop and reality-driven replanning | — |
| — | **MLH Commit Fellowship** | FREE OPT-IN | — (no sponsor tech) | Devpost opt-in + form |
| — | **Workday: Future of Work** | OPTIONAL, FRAMING ONLY | — (0 engineering) | Sun 09:00 gate 1, 10:30 gate 2 (19 §6.4) |

### 1. Even Realities (PRIMARY)
**Criteria**: two published versions; prepare for both [V]:
- Challenge page/starter pack: Made for G2 · Originality · User Experience · Technical Execution.
- Official challenge doc: Made for G2 · **Quiet by Design** · Originality · Experience & Polish · Execution ("Can a judge put on G2 and experience the core idea right now?").

**How we score on each**
| Criterion | Our evidence in the demo |
|---|---|
| Made for G2 | Hands busy, eyes on the work; one action + tiny map; the judge never looks at a screen |
| Quiet by Design | HUD updates only on change; dims while hands work; dark when verified. **Measured:** HUD changes per run and % of task time dark or dimmed (10 §3, E-a) |
| Originality | A verification-and-replan guide vs tap-to-advance guides; the new moment is *the glasses catching the judge's own physical mistake* |
| Experience & Polish | instruction → physical action → mistake → corrective instruction → correct sequence → `● VERIFIED` → dark display, with no instructions beyond "put these on" |
| Execution | Runs on physical G2 from the Beta build |

**The Even judge experiences:** next verified action + silence when correct. The phone twin is for the second judge and must not upstage the glasses.

**The three judge questions** (on the phrase card, one sentence each):
- *Who uses this?* Someone repairing or assembling with a manual and their hands full.
- *When?* At the moment they would stop to search the manual.
- *Why G2?* Hands in the work, eyes on the work, one action at a time, and dark when nothing is wrong.

**Hard deliverables (by Sun 12:00 PM)** [V]:
- [ ] Even Hub **Beta** build (`.ehpk`) uploaded, pushed to our Beta group, installed and tested on physical G2
- [ ] Passes: 5-min phone lock recovery, permission denial, root double-tap → `shutDownPageContainer(1)`
- [ ] App name `GhostBuild` (≤ 20 chars, no "Even"); not medical/financial/emergency-routing
- [ ] Devpost: select the Even Realities challenge; include the Even Hub app name; show the G2 experience in the GENERAL video (through-the-lens); README section on installing/running on G2 incl. accounts/API keys
- [ ] Team present in person at judging; G2 returned before leaving

### 2. Sentry (SECONDARY)
`integrations/sentry_bridge/` is a separate read-only process that tails the existing session log and emits Tracing + Logs (Issues and Fetch tool spans are bonus). It never touches `core/`, `contracts/`, `perception/`, `g2/` or `spatial/`.
- **Winning line:** "Every instruction on the glasses is a Sentry trace back to the camera frame that justified it."
- **Requirement:** ≥ 2 Sentry products beyond error monitoring (Tracing + Logs).
- **Entry condition:** select the challenge only if `docs/sentry_findings.md` holds ≥ 1 real FINDING **and** ≥ 1 real engineering DECISION it informed or validated (FINDING · EVIDENCE · DECISION · RESULT). No invented stories.

### 3. Fetch.ai (CONDITIONAL SECONDARY)
A uAgent on Agentverse (mailbox, Agent Chat Protocol), reachable from ASI:One, isolated in `integrations/fetch_agent/` on B's laptop, disarmed by default (`GB_AGENT_ARMED=0`), approval before any mutation, `GB_CORE_URL` required (no localhost default), graceful "workcell offline" replies. The supervisor's workflow is complete in ASI:One; the technician uses G2. No Payment Protocol, no second agent, no new frontend, no duplicate planner.

### 4. Overall + Beyond the Digital
Overall criteria [V, Devpost]: Technical Depth · Product Thinking & Impact · Execution & Polish · Originality & Insight.
| Criterion | Evidence |
|---|---|
| Technical Depth | Perception with abstention; dependency-aware replanner with a termination argument and BFS-optimality test; measured latency; honest eval; (if gated in) tracked CAD poses driving the same planner |
| Product Thinking & Impact | "An AI copilot for physical work"; users with hands full and a manual; LEGO rigs as breakable testbeds |
| Execution & Polish | Reliable 90 s demo, < 40 s reset, recorded backup |
| Originality & Insight | AI reads the manual; deterministic state and planning decide the instruction; safe abstention over a wrong instruction |

Required Devpost fields [V]: description incl. track and "How does it apply to the company challenges you submitted to?"; public, documented GitHub repo; **2–3 min demo video** → the **GENERAL export (2:50–2:58)**. Fetch needs its own **3–5 min** video → the **FETCH export (3:10–3:30)** from the same master edit.

## Claims allowed in pitches
- The frontier claim "on-device learned 6-DoF tracking feeding a verified planner" only if S5 passed markerlessly.
- "Installed 90° off its documented orientation" for the motor. Never "the motor isn't broken", never a diagnosis or functional claim (18 v3 §7).
- "Compiled, not executed" for the optional external repair guide, only if it validated offline.

## Not pursued
StepFun (dropped; a VLM may never decide physical state, and every candidate role duplicated a deterministic path), Cognition (network only; the checkbox is not selected), Paper, QNX, Espressif, Base44, Visa, Intuit, Photon, Browser Use, CREAO, veri.studio, and MLH platform prizes.

## Open questions for organizers (ask at check-in / opening / Discord)
1. Can a project select multiple company challenges? (A-08)
2. Overall prize, and whether exactly one organizer track must be selected.
3. Which Even rubric is authoritative (4 or 5 criteria)?
4. Number of G2 loaners available.
5. Rules page still says "8am Sunday April 26" (stale); confirm the deadline is Sun Oct 18 12:00 PM.
6. Fetch: does "workflow entirely in ASI:One" accept a technician executing on G2? (19 §12)
