# GhostBuild

**Quiet until it breaks. Silent once it's fixed.**

GhostBuild is a closed-loop repair copilot. The device being repaired runs its own tests. Even G2 shows one short cue only while a test fails, and the physical fix clears it. Nobody taps "done": the hardware confirms the repair and the glasses go dark.

**Team:** read [`docs/PIVOT_GHOSTBUILD.md`](docs/PIVOT_GHOSTBUILD.md). It is the only execution authority. Docs 00–21 are historical. Read them only for G2 platform notes, never for scope. Agent rules are in [`CLAUDE.md`](CLAUDE.md).

## Lanes

| Lane | Owner | Directory | Prove it without the other lanes |
|---|---|---|---|
| Phone page, README, demo, video | A | `web/`, `README.md`, `CLAUDE.md` | `/phone` against a recorded `/state` fixture |
| G2 plugin, Beta packaging | B | `g2/` | `make g2-sim` fed by D's stub server |
| Firmware, rig, wiring | C | `firmware/`, `hardware/WIRING.md`, `tools/`, `recordings/` | `python tools/serial_probe.py` |
| Contracts, core, knowledge | D | `core/`, `contracts/`, `knowledge/`, `Makefile`, `pyproject.toml` | `make test`, `make core` with `--simulate` |

## Developer quick start

Prerequisites: `uv` (Python 3.11 is pinned in `pyproject.toml`), Node ≥ 20, git. B also needs `npm i -g @evenrealities/evenhub-cli @evenrealities/evenhub-simulator` and a phone with the Even app. C needs Arduino IDE or `arduino-cli`.

| Question | Command | Green means |
|---|---|---|
| Is my environment working? | `make setup && make doctor` | every line under "everyone" is `ok` |
| Are contracts valid? | `make contracts` | `GREEN python …` and `GREEN ts …` |
| Can core start? | `make core` | `make health` shows core `/health` JSON |
| Can tests run? | `make test` | contracts, lints and every existing lane's tests pass |
| Any secret about to be committed? | `make check-secrets` | `check-secrets: ok` |

Targets for lanes that don't exist yet stop with `not yet: <path> missing (owner X)`. `make help` lists all targets.

Secrets: copy `.env.example` to `.env` (gitignored). Only `make compile` needs `ANTHROPIC_API_KEY`. Never put a key in `g2/`.

## Architecture

```
[Gate: Uno + HC-SR04 + SG90 + end-stop + POWER switch]  firmware/barrier/barrier.ino
   │ USB serial, one JSON line / 100 ms (raw observations)
[Laptop: python -m ghostbuild_core :8787]               core/ghostbuild_core
   serial → tests → engine → hud   (hud.py is the only HUD writer)
   WS /ws?role=g2 (physical G2 and simulator get the same frames) · /hud · /state · /card · /health · /phone
[Even app WebView → g2/ plugin]  renders hud frames; sends press / swipe
[Any browser: /phone]            wiring card, why and sources, evidence timeline
```

Runtime needs no internet. The Repair Card (`knowledge/cards/barrier.json`) is precompiled. Details are in PIVOT §5.

## Git workflow

- `main` is the integration branch. Run `make test` before merging.
- Short-lived branches per owner: `a/web`, `b/g2`, `c/firmware`, `d/core`. Rebase on `main` first. Keep PRs small.
- **Merge hotspots:** `contracts/` (D only; locked Sat 17:00, after that a shared-schema change needs D plus every consuming owner) · `Makefile` (one lane target per small commit) · `pyproject.toml` and `uv.lock` (D only; one dependency change per commit; `uv lock`, never hand-merge) · `README.md`, `CLAUDE.md` (A only).
- Pins live in `hardware/WIRING.md`. A pin change updates WIRING.md, the card and `web/assets/wiring.svg` together within 10 minutes.
- Freezes: P0 freeze Sun 02:00, product feature freeze Sun 04:00, deadline Sun 12:00 PDT.

## Acceptance

`docs/PIVOT_GHOSTBUILD.md` §8 is the live acceptance test (11 steps on physical G2). §8b is the judge handoff test. The simulator runs beside the glasses but never counts as a pass.
