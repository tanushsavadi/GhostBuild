# GhostBuild — START HERE

> **v2 (Sat 2026-10-17 evening): read [`CLAUDE.md`](CLAUDE.md) first — it supersedes everything below, including docs/PIVOT_GHOSTBUILD.md.** Quick try: `make setup && make core-sim`, then `make g2-cli`.

## Read these first

Do NOT read all of the historical planning docs.

Everyone should read:

1. `docs/20_FINAL_IMPLEMENTATION_BIBLE.md`
2. `docs/21_HACKATHON_CHECKLIST.md`

These are the operational source of truth.

Open older docs only when your implementation task needs additional detail.

Most useful references:

- `docs/05_CONTRACTS.md` — shared schemas, messages, endpoints and fixtures
- `docs/19_SPONSOR_AND_TRACK_STRATEGY.md` — Even / Sentry / Fetch implementation details

## Source-of-truth priority

1. `20_FINAL_IMPLEMENTATION_BIBLE.md`
2. `21_HACKATHON_CHECKLIST.md` for clocks and gates
3. `19_SPONSOR_AND_TRACK_STRATEGY.md` for sponsor work
4. `05_CONTRACTS.md` for shared interfaces
5. Older docs for supporting detail only

## Owners

A — Phone web page, wiring diagram, captain/demo/video

B — G2/plugin/network/Beta

C — Hardware rig, Arduino firmware, telemetry

D — Contracts, core, world/diff/planner, knowledge/answers, integration authority, gate decisions

Devin — `integrations/sentry_bridge/` and `integrations/fetch_agent/` only

## Non-negotiable execution rules

- Contracts lock once at SAT 12:45.
- After that, shared schema changes require D + every affected consumer owner.
- After SUN 00:45, no schema changes.
- P0 must always remain independently runnable.
- Unknown physical state means abstain — never guess.
- No AI model commits physical state.
- Sponsor code stays inside `integrations/`.
- Even / core reliability outrank sponsor stretch work.
- "Almost green" at a gate = RED.
- When a feature is killed, it stays killed.
- Do not revive cut features.
- Do not casually refactor somebody else's lane.

## Before asking an AI coding agent to work

Tell it:

- your owner letter;
- the task you are working on;
- the next gate/deadline;
- which directories you own.

Then paste the standard AI handoff prompt below.

## If an AI proposes a new feature or architecture

Ignore it unless the current task genuinely cannot be implemented under the frozen plan.

We are executing now, not redesigning.