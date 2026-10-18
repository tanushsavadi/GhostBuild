# CLAUDE.md — GhostBuild v2

Read this before doing anything in this repo. It overrides older planning docs wherever they conflict, including `docs/PIVOT_GHOSTBUILD.md` (the broken-gate repair copilot is superseded; the previous rules are archived in `docs/CLAUDE_v1_gate_pivot.md`).

## What we're building (v2, pivoted Sat Oct 17)

GhostBuild guides a person through a hands-on build on Even G2 glasses, one step at a time, and **verifies the steps it can measure**. The user talks to it; the glasses show only the next step and go dark when the work is done.

Three parts:
1. **Step engine (core, our code):** an explicit state machine that runs any procedure file. It alone decides what the glasses show.
2. **Electrical test jig (M5StickC PLUS2):** probes the breadboard so a step can be `● VERIFIED` by measurement.
3. **Creao compiler agent:** turns any tutorial into our procedure format, ahead of time (runs take minutes).

Two modes, always labeled on the glasses:
- **VERIFIED:** a jig check measured it → `● VERIFIED`
- **GUIDED:** the user said "done" or tapped → `✓ DONE (you confirmed)`

**Team brief (source of truth):** https://claude.ai/code/artifact/d5222426-c380-4b3f-93be-a84c0e55c113
Old docs (`docs/00–21`) are history. Their principles still apply; their camera, spatial and CAD plans do not.

## Dead — do not build, revive, or "fix"

Camera perception, ArUco, LEGO rocket/rover rigs, `perception/`, `spatial/`, the iPhone spatial app, LiDAR, CAD/LDraw compiler, three.js twin, hand detection, Fetch agent. Leave those directories alone; don't delete them without D's OK.

## Non-negotiable rules

- **No AI model decides physical state.** Only the jig (measured) or the user (confirmed) completes a step.
- **Unknown state means abstain.** Show `CHECKING` or `ASK A MENTOR`, never a confident guess.
- **The live loop never waits on an LLM or Creao.** Step changes and HUD updates are our own code, under a second.
- **Answers come only from the current procedure.** Out of scope → say so; never invent wiring or values.
- **Never call a GUIDED step "verified".**
- Gates are binary: "almost green" = red. Killed work stays killed.
- Don't refactor another owner's lane. Small PRs.
- If an AI (including you) proposes a new feature or architecture, stop and ask the owner. We are executing, not redesigning.

## Owners and directories

| Owner | Lane | Directories (merge rights) |
|---|---|---|
| A | Captain, Creao agent, review page, demo/video/Devpost, user study | `compiler/` (Creao client + review page), `README.md` |
| B | G2 plugin, speech-to-text, HUD, Even Beta, live mirror page support | `g2/` |
| C | Test jig wiring, firmware, serial adapter | `jig/firmware/`, `jig/adapter/` |
| D | Core: step engine, answer engine, troubleshooting, endpoints, contracts, gate calls | `core/`, `contracts/`, `knowledge/` |
| Designer | Live mirror page (glasses view + circuit diff) | `mirror/` |
| Devin | Sentry bridge only (optional) | `integrations/sentry_bridge/` |

Create a missing directory in its own small PR. `contracts/` changes are D-only.

**Before helping anyone, ask:** their owner letter, their task, the next gate, and which directories they own. Stay inside those directories.

## The procedure contract (D owns)

Every procedure is one JSON file; nothing about the LED circuit is hardcoded anywhere else.

Key fields:
- `origin`: `authored` | `agent_compiled`
- `review.status`: only `approved` procedures can be published to the glasses
- `steps[].hud`: ≤ 28 characters, uppercase, one action
- `steps[].check.type`: `jig` (VERIFIED) | `user_confirm` (GUIDED). `jig` only names checks the firmware actually implements.
- `steps[].troubleshoot`: ordered checks, most likely cause first
- `steps[].faq` / `why` / `where`: the only material the answer engine may use
- Jig facts live in a jig profile (`knowledge/jigs/*.json`: checks, faults, edge checks), never in core

The schema lives in `contracts/models.py` with examples in `contracts/examples/procedure_*.json`; real procedures in `knowledge/procedures/`. Validate with `make contracts`. No schema changes after **Sun 00:45**.

## Endpoints and ports (D confirms final names)

- Core HTTP + WebSocket on `:8787`; `/health` for status
- `ws ... /ws?role=g2` — plugin ↔ core (voice text and taps in, HUD out)
- Jig adapter → core: serial JSON lines → core over the local WebSocket (`role=jig`)
- `POST /procedures/validate` — the Creao agent calls this until its output passes
- `POST /agent/webhook` — Creao delivers a compiled procedure here
- `/review` — review and approve page; `/mirror` — live mirror page

## G2 constraints (B)

- Mic in, **text out**: the G2 has no speaker.
- 576 × 288 per eye, 16 greens, one font, no font sizes.
- Glyph test on real G2 before trusting `· ● ━ ─ °` (`GB_ASCII_HUD=1` is the fallback). The step counter is its own line; the action line stays ≤ 28.
- Max 4 image containers (≤ 288 × 144 each) + 8 other containers per page.
- ≤ 4 HUD updates per second; image sends spaced ≥ 100 ms.
- HUD per screen: action line (≤ 28 chars), step counter, mode label, `━` progress bar.
- Commands matched directly: next, back, repeat, done, help. Free questions → answer engine. Tap and the contextual menu are always a fallback.
- Run on our own hotspot if venue Wi-Fi blocks phone ↔ laptop.

## Test jig (C)

M5StickC PLUS2 is the jig; the Raspberry Pi 3 is the backup (digital two-way conduction test, `jig/pi/probe.py`; it cannot tell resistor-missing from LED-missing). Starting design, confirm every threshold by measurement:
- G26 → row 10 (drive A), G25 → row 20 (drive B), **G33** (Grove) → row 15 (analog sense) + 100 kΩ pull-down to ground, G32 → button (`INPUT_PULLUP`), other side to ground. Not G36: on the StickC Plus G36 and G25 share one header pin.
- Classify the resistor first: with the resistor missing, a backwards LED leaks through the pull-down and the reverse test is not ≈ 0 V.
- Avoid G0 (mic). Run on USB; on battery, hold G4 high or the stick powers off.
- Forward and reverse tests tell resistor missing / LED missing / LED correct / LED backwards apart. Button reading "pressed" while untouched → rotated 90°.
- Emit JSON lines over serial ~5 Hz; change a reported state only after 3 matching readings.
- **Catch speed matters:** a backwards LED should reach the glasses in under a second.

## Creao agent (A)

- Built and saved on agent.creao.ai with Create Agent (installed packages only persist when saved).
- Triggered from our backend via the API Trigger; runs are async (minutes, no streaming). Never block a request waiting on a run.
- The agent must call `/procedures/validate` and fix its output until it passes, then deliver via `/agent/webhook`.
- One run per compile. The agent never starts itself. Watch credits.
- README must include a share link to one agent run and the agent ID. Devpost: select the CREAO track (Best AI-First Disruptor).

## Secrets

Copy `.env.example` → `.env` (gitignored), only keys your lane needs. Never commit a key, never put one in `g2/` plugin code or the mirror page.
- `CREAO_API_KEY` (a `capi_` key) — server-side only
- `ELEVENLABS_API_KEY` — server-side only

Run `make check-secrets` before every push.

## Commands

| Question | Command |
|---|---|
| Environment working? | `make setup && make doctor` |
| Contracts valid? | `make contracts` |
| Core running? | `make core`, then `make health` |
| Try the loop without hardware? | `make core-sim`, then `make g2-cli` |
| Tests pass? | `make test` |
| Secrets about to leak? | `make check-secrets` |

Add your lane's Make target in its own small commit.

## Gates (PDT; red → the fallback fires, no debate)

| Clock | Gate | Owner | Red → |
|---|---|---|---|
| Sat 18:00 | Spoken words appear as text on the real G2 | B | Tap + menu become main input |
| Sat 19:00 | Procedure schema locked, examples validate | D | Lock moves; no one codes against a partial schema |
| Sat 20:00 | **Floor:** one procedure end to end with tap and voice | D + B | All hands on the floor |
| Sat 22:00 | Jig reads every state 10/10 | C | GUIDED only; drop "verified" claims |
| Sat 22:00 | One real tutorial compiles → approved → runs on glasses | A | Drop the Creao entry |
| Sun 00:45 | Core merge cutoff; no schema changes after | D | — |
| Sun 02:00 | 5 clean runs of the hero flow | All | Nothing merges into the hero path |
| Sun 04:00 | Feature freeze | All | Bugs and rehearsal only |
| Sun 06:45 | Even Beta QA on real G2 | B | Fixes only |
| Sun 08:30 | Video exported, study numbers final | A | Rough cut; delete unmeasured claims |
| Sun 11:00 | Devpost + Even Beta submitted | A + B | Deselect incomplete prizes |

## Git workflow

- `main` must always run the floor; `make test` green before merging.
- Short-lived branches per owner: `a/…`, `b/…`, `c/…`, `d/…`, `design/…`. Rebase on `main`, small PRs, merge within hours.
- `pyproject.toml` / `uv.lock`: one dependency change at a time; after a rebase run `uv lock`, never hand-merge the lockfile.

## Claims (README, Devpost, pitch)

Allowed: "VERIFIED means the circuit measured it; GUIDED means you told us." · "It answers only from the procedure." · "Remove the agent, and we only know the procedures we wrote by hand." · numbers only if measured, with n.

Not allowed: "AI checks your work" · "works on any physical task" · "the agent guides you live" · any unmeasured number · a recording presented as live.

## Personal preferences

Put your own working preferences (how much code to write for you, how to explain things) in `CLAUDE.local.md`, which is gitignored. Keep this file team-wide.
