# GhostBuild — project rules
24 h hackathon. Live-demo reliability > features. **docs/PIVOT_GHOSTBUILD.md is the only execution authority**; docs/00–21 are historical (read them only for G2 platform notes, never for scope).
- Product: closed-loop repair copilot. Device tests → deterministic engine → one G2 cue → the physical fix clears it.
- Scope: only what PIVOT §5 builds; follow its cut order when behind; never build PIVOT §11 items (3D/CAD, spatial, LEGO, perception, voice, sponsor integrations, runtime LLM on the cue path).
- Only core/ghostbuild_core/hud.py writes HUD frames. No model output reaches G2 except through the reviewed Repair Card. A G2 press is a recheck, never a commit.
- Never show VERIFIED without the measured end-stop; never phrase a cue as a diagnosis (use CHECK …); unknown state never yields a confident physical instruction.
- core/ and contracts/ are device-agnostic (make lint-generic); device facts live in knowledge/cards/ and firmware/.
- Contracts: D owns; lock Sat 17:00; later shared-schema changes need D + every consuming owner. Run `make contracts`.
- Label sources: MEASURED LIVE, COMMANDED, DETERMINISTIC, MANUFACTURER DOC, AUTHORED PROJECT SPEC, AI-EXTRACTED · HUMAN-REVIEWED, AUTHORED DEMO METADATA, REPLAY, SIMULATED. Never demo replay/simulated data as live.
- Pins live in hardware/WIRING.md; a pin change updates WIRING.md, the card and web/assets/wiring.svg together.
- Even G2: verify every SDK call via the everything-evenhub skills + hub.evenrealities.com/docs (SDK 0.0.16). No API keys in g2/.
- Claude API: official `anthropic` SDK + the claude-api skill; claude-opus-5-5; structured outputs, not forced tool_choice; build time only (knowledge/).
- `make test` before merging; every feature behind its flag. P0 freeze Sun 02:00; product feature freeze 04:00.
