You are taking over implementation of GhostBuild's adaptive conversational assistant. Resume the engineering task from the handoff; the previous agent stopped because I explicitly asked for an Opus 5.5 takeover.

<context>
Workspace: /Users/tanushsavadi/Documents/Hackathons/LA_Hacks/.worktrees/final-sprint
Branch: codex/final-sprint
Authoritative current handoff: docs/CLAUDE_ADAPTIVE_TAKEOVER.md
Deadline: Sun 2026-10-18 12:00 PDT; Devpost 10:30, final QA11:00. Live-demo reliability takes priority.
Everything is uncommitted. The latest full core run is 630 passed /4 failed. New answer/policy checkpoint tests6 passed, targeted assistant/cache/IKEA105 passed, G2 208 passed + build, web28 passed. New adaptive browser/simulator checks and conversation evals have not been run.
The operator backend on8787 is still old loaded code and returned404 for /discovery/state. Do not confuse its behavior with current files or restart it with incomplete changes.
</context>

<read_first>
Read in order: CLAUDE.md, docs/FINAL_SPRINT_STATUS.md, docs/PIVOT_GHOSTBUILD.md §0A, and docs/CLAUDE_ADAPTIVE_TAKEOVER.md completely. Inspect git status and the relevant implementation before editing. The handoff distinguishes earlier verified features, new partial work, four exact failing tests, known hazards and remaining tasks. Older success reports do not establish that the latest edits work.
</read_first>

<objective>
Finish the existing app's adaptive task understanding without a new onboarding flow or agent framework:
1. Full, persistent G2 answer pages: swipe to read, press or natural “back to my step” to return to the same step/image; no reading gesture completes a step.
2. Vague product descriptions identify actual products through photos and the existing source adapter; only then choose configuration and the correct official assembly manual. Never start generic assembly steps for an unidentified IKEA product.
3. Interview only for minimum sufficient context. Use the single most useful question, all details already supplied, natural replies and helpful identification alternatives. Critical unknowns block inappropriate start/research. No arbitrary question cap or forced start.
4. Persist structured facts, sources, uncertainties, branches and unanswered requirements. Separate quoted user facts from inferences; handle corrections, new goals, stale work and interruptions without losing progress.
5. Primary instructions use human English; exact part identifiers remain available in parts/manual details. Use the new generic card/presentation mechanism, not retailer-specific core conditions.
</objective>

<constraints>
Preserve all uncommitted work. Do not commit/push or expose credentials. Only hud.py emits HUD frames. Core/contracts stay generic, public contract changes additive and optional. Manual completion remains HUMAN CONFIRMED; measured completion requires actual evidence. Preserve G2 gestures/system exit, image constraints, CREAO/ElevenLabs integrations, consent, committed-only transcription, push-to-talk and text fallback. G2 has no camera/speaker.
No further live CREAO run is authorized. Use mocks to verify research wiring and report paid-provider call counts. Use official IKEA pages/manuals and the documented existing search provider; no private API/search-page scraping. Protect the working demo and back up operator session state before any necessary reload.
</constraints>

<execution>
Start by reproducing the four failures listed in the handoff. Fix actual regressions and update obsolete behavior expectations without weakening physical-evidence tests. Review the documented answer ownership, pending worker, measured-step, restore, ready-card, source, confidence and TTS-truncation hazards. Finish the smallest robust policy and UI integration that meets the objective.

Test conversation cases A–H from the handoff, inspect their traces, and distinguish scripted orchestration from live-model quality. Verify full-answer paging/explicit return and photo→manual flow in a real browser and official G2 simulator. Use installed SDK declarations and official skills when touching G2. Do not invent model-specific repairs or visual references.

Run focused checks as changes require, then the full verification suite once the implementation stabilizes. Once checks pass, continue to necessary integration and documentation rather than repeating them without a new concern. Safely reload the stale operator process only after the new code is ready, preserving its existing log directory, progress and configuration.

Give brief progress updates at meaningful milestones. Continue authorized work without stopping merely to announce the next step. Ask only when an actual missing decision blocks progress or an action requires authorization. If something truly cannot be completed, preserve a precise checkpoint and explain the blocker.
</execution>

<acceptance_and_report>
The task is complete when required behavior works in the existing flow, relevant tests and full checks pass, browser/simulator evidence is captured, and the operator uses the correct code. Update docs/FINAL_SPRINT_STATUS.md, the runbook and handoff with current evidence. Report exact test counts, provider calls, cache/live latency separately where measured, exact user interactions, and what remains unverified. State that physical G2/microphone/BLE checks and the authored MICKE text's human PDF spot-check remain pending unless actually performed. Keep the final report concise and factual.
</acceptance_and_report>
