# GhostBuild

**Quiet until it breaks. Silent once it's fixed.**

GhostBuild is a closed-loop repair copilot for Even G2. A Raspberry Pi + camera observes a real physical station; a deterministic engine turns measured evidence into one short cue, offers real annotated pictures (WHERE / HOW / CORRECT) on request, and goes blank when measured evidence shows the problem is fixed. Nobody taps "done".

**Team:** read [`docs/PIVOT_GHOSTBUILD.md`](docs/PIVOT_GHOSTBUILD.md). It is the only execution authority; its **§0A (Sat 18:30 PDT) hardware/UX amendment wins** — the Arduino kit is not available, the hardware is Raspberry Pi + camera + LED. Docs 00–21 are historical. Read them only for G2 platform notes, never for scope. Agent rules are in [`CLAUDE.md`](CLAUDE.md).

## Lanes

| Lane | Owner | Directory | Prove it without the other lanes |
|---|---|---|---|
| Visual help, phone page, assets, demo, submission | A | `web/`, `assets/`, `knowledge/guides/` | `/phone` against a recorded `/state` fixture |
| G2 plugin, Beta packaging | B | `g2/` | `make g2-sim` fed by `make core-sim` |
| Raspberry Pi, camera, LED | C | `pi/`, `hardware/WIRING.md`, `recordings/` | `python -m ghostbuild_pi --fake-camera` |
| Contracts, core, knowledge writer | D | `core/`, `contracts/`, `knowledge/`, `Makefile`, `pyproject.toml` | `make test`, `make core-sim` |

## Developer quick start

Prerequisites: `uv` (Python 3.11 is pinned in `pyproject.toml`), Node ≥ 20, git. B also needs `npm i -g @evenrealities/evenhub-cli @evenrealities/evenhub-simulator` and a phone with the Even app. C needs a Raspberry Pi with Pi OS, the camera module and an LED (see `pi/README.md`).

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
[Raspberry Pi + camera + LED]   pi/ghostbuild_pi: frame features (MEASURED), LED (COMMANDED) -> HTTP/WS Observation
   │ LAN
[Laptop: python -m ghostbuild_core :8787]   core/ghostbuild_core
   observation -> tests -> engine -> hud   (hud.py is the only HUD writer)
   session/menu/goal resolver · guide images /guides/<id>/<view>.png · WS /ws?role=g2 · /state · /health · /phone
[Even app WebView -> g2/ plugin]  renders hud frames (text + 288x144 images); sends press / swipe / hello
[Any browser: /phone]             evidence timeline, source links, text goal fallback, mirrored HUD
```

Runtime needs no internet (voice/LLM Q&A is optional and flagged). The Repair Card (`knowledge/cards/camera_lens.json`) and guide images are precompiled. Contract: `contracts/models.py`. Plan: PIVOT §0A.

## Git workflow

- `main` is the integration branch. Run `make test` before merging.
- Short-lived feature branches (`feat/g2-hud`, `feat/pi-vision`, `feat/core-runtime`, `feat/visual-help`, `feat/knowledge`), one git worktree each under `.worktrees/`. Rebase on `main` first. Keep PRs small.
- **Merge hotspots:** `contracts/` (D only; locked Sat 17:00, after that a shared-schema change needs D plus every consuming owner) · `Makefile` (one lane target per small commit) · `pyproject.toml` and `uv.lock` (D only; one dependency change per commit; `uv lock`, never hand-merge) · `README.md`, `CLAUDE.md` (A only).
- GPIO/pin facts live in `hardware/WIRING.md` and record only what was actually wired and tested.
- Freezes: Devpost done by Sun 10:30, final Beta QA by 11:00, deadline Sun 12:00 PDT.

## Acceptance

`docs/ACCEPTANCE.md` is the live acceptance test (Pi + physical G2). PIVOT §8/§8b are Arduino-era and superseded. The simulator runs beside the glasses but never counts as a pass.
