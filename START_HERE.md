# GhostBuild — START HERE

Read [`docs/PIVOT_GHOSTBUILD.md`](docs/PIVOT_GHOSTBUILD.md) **§0A first** and [`CLAUDE.md`](CLAUDE.md). That is all. PIVOT is the only execution authority and §0A wins over the Arduino-era text below it (hardware is now Raspberry Pi + camera + LED). Docs 00–21 are historical: open them only for G2 platform notes (08 §2–§6) and the honesty labels, never for scope.

Product direction is frozen: a closed-loop repair copilot. *The fix is the input.*

## Owners

- **A:** visual help assets, phone page (`web/`, `assets/`, `knowledge/guides/`), demo, video, Devpost
- **B:** G2 plugin (`g2/`), gestures, images, Beta packaging, device custody
- **C:** Raspberry Pi (`pi/`), camera, LED, `hardware/WIRING.md`, real recordings
- **D:** contracts, core, knowledge writer, Makefile, integration authority

## Non-negotiable execution rules

- Live-demo reliability beats features.
- Contracts locked Sat 17:00. After that a shared-schema change needs D plus every consuming owner.
- Only `core/ghostbuild_core/hud.py` writes HUD frames. No model output reaches G2 except through the reviewed Repair Card.
- A G2 press is a recheck, never a commit.
- Never show a recovery/verified frame without measured camera evidence. GPIO high is COMMANDED, not verified light. Cues say `CHECK …`, never a diagnosis.
- Never demo replay or simulated data as live.
- Do not build anything in PIVOT §11. Follow PIVOT §5.10 cut order when behind.
- "Almost green" at a gate is red. A killed feature stays killed.
- Do not casually refactor somebody else's lane.

## Before asking an AI coding agent to work

Tell it your owner letter, the task, the next gate, and the directories you own. If it proposes a new feature or architecture, ignore it unless the task cannot be done under PIVOT. We are executing, not redesigning.
