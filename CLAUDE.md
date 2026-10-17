# GhostBuild — project rules
24 h hackathon. Live-demo reliability > features. Read docs/20_FINAL_IMPLEMENTATION_BIBLE.md, docs/15_SONNET_HANDOFF.md, docs/05_CONTRACTS.md, then only your vertical's doc.
- Scope: only P0/P1 items in docs/03_MVP_SCOPE.md; P2 only after its gate; never build CUT items.
- Physical state is committed only by the P0 grid path (rocket) or adapters/spatial_pose (rover). No AI model commits state. Unknown state never yields a confident physical instruction.
- core/ and contracts/ are domain-agnostic: no LEGO terms (make lint-generic).
- Contracts: one lock Sat 12:45; shared-schema changes need D + every consuming owner; none after Sun 00:45. Run `make contracts`.
- One HUD writer: core/hud_arbiter.py. Answers are pure functions of an immutable snapshot. A G2 tap is a recheck, never a commit.
- Spatial: separate process, flag-guarded core additions, rocket snapshots byte-identical; never .resetTracking/.removeExistingAnchors after the first run.
- Sponsor code lives only in integrations/; never import it; never touch core/contracts/perception/g2/spatial from there.
- Honesty: label sources (TRACKED, MEASURED LIVE, CAD, TARGET, DETERMINISTIC, AI-EXTRACTED, AUTHORED DEMO METADATA, MANUAL EVIDENCE + origin, LAST SEEN, MANUAL OVERRIDE).
- Even G2: verify every SDK call via the everything-evenhub skills + hub.evenrealities.com/docs (SDK 0.0.16). No API keys in g2/.
- Claude API: official `anthropic` SDK + the claude-api skill; claude-opus-5-5; structured outputs, not forced tool_choice.
- `make test` before merging; every feature behind its flag. P0 freeze 02:00; product feature freeze 04:00.
