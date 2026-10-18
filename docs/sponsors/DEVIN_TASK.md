# Devin task — replay and reliability tests for the observation -> state -> HUD pipeline

Paste this to Devin (repo: tanushsavadi/GhostBuild, base branch `lead/hw-pivot`, work on `devin/replay-tests`, open a PR to `lead/hw-pivot`). Read `CLAUDE.md` and `docs/PIVOT_GHOSTBUILD.md` §0A first (the rest of PIVOT is obsolete history).

## Goal
Black-box end-to-end replay and reliability tests that prove, deterministically and without hardware or glasses, that a stream of Pi `Observation`s produces exactly the right `HudFrame` sequence.

## You own (write only here)
`tests/e2e/**`, `tests/fixtures/**`, `recordings/synthetic/**`, `docs/devin/REPORT.md`. Do NOT edit `core/`, `contracts/`, `g2/`, `pi/`, `Makefile`, `pyproject.toml` (ask in the PR if you need a change).

## Interface (stable)
Core runs as `uv run python -m ghostbuild_core --simulate --port 8799 --log-dir <tmp>` (the `--simulate` flag only enables `POST /sim/scenario`; your tests post their own observations).
- `POST /observation` takes `Observation` JSON (`contracts/models.py`, examples in `contracts/examples/`).
- `WS /ws?role=g2`: send a `G2Hello`, receive `HudFrame` JSON; send `G2Input` for press and swipes.
- `GET /state`, `GET /health`, `POST /session/goal`.
- `uv run python -m ghostbuild_core.replay <jsonl>` re-feeds recorded observations with a deterministic clock.

## Deliver
1. A fixture generator producing labelled synthetic recordings (JSONL, `source: "replay"`): healthy 60 s, 1 s flicker, sustained cover, cover then recovery, frozen feed, camera null, link loss and return, wave -> LED commanded, wave without LED command.
2. Golden-sequence tests: recording in -> expected HUD frame sequence out (modes, cue text, no duplicates, ttl clears).
3. Reliability tests: out-of-order and duplicate `seq`, backend restart mid-fault (session resumes, no second welcome), WS reconnect gets the current frame, two G2 clients get identical frames, 60 s healthy = zero frames.
4. Property tests: no `verified` frame without a measured pass; `camera: null` never yields success; a press never clears a fault.
5. `make test` stays green; add a single `tests/e2e/README.md` with the run command.
6. `docs/devin/REPORT.md`: what you built, what failed first, what you changed after seeing it. State plainly that this is Devin's work.

## Rules
Honest labels only; replay data is never described as live. No secrets. Small commits. Open the PR early and push as you go.
