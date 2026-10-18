# GhostBuild — authoritative adaptive-conversation handoff to Opus 5.5

**State (05:35 PDT, Claude Opus 5.5): implementation finished and verified; operator :8787 reloaded.** Sections 1–9 below are Codex's original handoff, kept for history; section 0 is current. Nothing was committed or pushed by Claude.

## 0. Current status after the Claude takeover

**Done and verified** (details and counts: `docs/FINAL_SPRINT_STATUS.md` top table; evidence `docs/evidence/adaptive/`):
- The four failing tests: three updated from the obsolete 4 s answer TTL to sticky answer + explicit press return (measured uncertain-TTL assertions kept); the research fixture now states the tyre setup and `context_sufficient`, plus a new critical-unknown-blocks-research test.
- §7 hazards resolved: answer ownership (an answer for another step is dropped on the next gesture and cleared when evidence advances — regression tests); THINKING is a `pending` flash: press returns to the step and `pending_dismissed` keeps the late answer phone-only; a new status/question replaces an older answer page; `_ready_card` also tries the clarified goal; `_begin` sends a clarified product-source goal through discovery; restart replays an open interview question (`Assistant.resume_question`); answer pages spell out units (Ω → OHM, ° → DEG, ± → +/-); TTS reads full answers in ≤480-char sentence parts (max 4, cancellable) instead of `.slice(0,500)`; `max_tokens` 1600 with a `max_tokens` stop treated as BrainError.
- Mid-step over-reaction fixed: `task_switch()` (explicit task change only) and `identity_correction()` (wrong/different model or product) replace `new_goal()`/`correction()` in `Runtime.ask`; "make sure it's tight?" or "actually it's the left side?" stay on the step. `returns_to_step()` no longer captures "show me step 14" or picture requests.
- **Live-API breakage found and fixed:** the enlarged `IntakeReply`/`StepReply` were rejected (`400 Schema is too complex`, ~35 s) — every live answer would have fallen back. The model now fills flat all-required `IntakeWire`/`StepWire` (schemas.py) converted inside `AnthropicBrain`; guarded by a unit test.
- Restart: a session whose card is not loadable shows the menu instead of falling through to the fault engine (was PI LINK LOST); a session on an on-disk researched draft reloads it (`LiveResearch.recover_draft`). With discovery attached, the persisted unidentified generic desk draft now reopens as the MICKE photo shortlist (verified on the real operator).
- Traces A–H as scripted tests; bounded live intake/step eval (6 Anthropic requests); official simulator + Chromium (desktop + 390 px) for paging/return and photo → manual; phone mirror overflow + gesture caption fixed.
- `GB_ANSWER_PAGES=0` kill switch restores the timed answer cue.

**Still open (not done):**
- Physical G2 legibility, BLE timing, on-glasses microphone; human PDF spot-check of the authored MICKE wording (two dropped quantities restored; steps 3/14/19/22/27 share "ROUND METAL LOCKS" across three lock IDs — reviewer should decide whether to distinguish them).
- STT confidence / uncertain-product confirmation path; `uncertain()` helper still unused.
- CREAO build-time request does not yet ask for `display_instruction` (a change breaks the pinned request-body tests and cannot be verified live without a new CREAO run). The importer accepts the field already.
- `knowledge/intake_references.json`, a bicycle identification visual and a Mac diagnostic card do not exist; C/D live answers rely on the model's general guidance and remain unsourced (labelled, never steps).
- Decision values SHOW_VISUAL / CONTINUE_GUIDE / TROUBLESHOOT are recorded and prompt-level only; they never dispatch new physical actions.
- Operator `.env` keeps `GB_CREAO=1`, `GB_LIVE_RESEARCH=1`.

Copy-paste prompt: [OPUS_55_TAKEOVER_PROMPT.md](OPUS_55_TAKEOVER_PROMPT.md).

## 1. Workspace, authority, and non-negotiable constraints

Work only in `/Users/tanushsavadi/Documents/Hackathons/LA_Hacks/.worktrees/final-sprint`, branch `codex/final-sprint`. Run commands there. Preserve every existing uncommitted change; feature work from several stages is mixed in this checkout. `git status --short` is authoritative. Do not commit/push unless asked. Never print `.env` values, secrets or provider bodies.

Read `CLAUDE.md`, `docs/FINAL_SPRINT_STATUS.md`, then `docs/PIVOT_GHOSTBUILD.md` §0A. Older docs 00–21 are historical. Latest user scope below explicitly expands the assistant; preserve onboarding and existing starter flow. Reliability beats features. Deadline Sun 2026-10-18 12:00 PDT, Devpost 10:30, QA 11:00.

Only `core/ghostbuild_core/hud.py` constructs HUD frames; all other owners submit `Screen`. Core/contracts remain generic; `make lint-generic` must pass. Changes to public contracts must remain additive/optional; run `make contracts`. Device-specific procedures and presentation wording are card data, not hardcoded core scripts. No runtime model on deterministic navigation/evidence paths.

A manual step can be HUMAN CONFIRMED by deliberate confirmation. A measured step can only complete from real evidence. Reading/dismissing an answer, choosing a product, or correcting context must never complete a step. Preserve existing Pi/CREAO/ElevenLabs integrations and G2 exit/reconnect behavior. G2 has no camera/speaker; optional TTS uses phone/earbuds. Preserve consent, committed transcripts only, push-to-talk and text/gesture fallback. Always-on G2 capture remains unverified.

Use official Even skills and installed SDK declarations for G2 changes. Images max 288×144, 16 grey levels, serialized bridge/image sends, text fallback. The current answer renderer uses the existing text container and introduces no SDK call.

IKEA retrieval: exact article/URL → validated cache → Anthropic `web_search_20250305`, `claude-opus-5-5`, restricted to ikea.com, then official-page/article/photo/manual-PDF validation. Never use undocumented private APIs or scrape ikea.com/search. Never label cache as a live search.

**No new live CREAO run is authorized.** The pre-authorized run is spent; do not enable or invoke another without asking. Implement/review research wiring with mocks. This continuation made **zero Anthropic model/search calls, zero CREAO calls, zero ElevenLabs calls**. Read-only web browsing checked official Even/Apple/Schwalbe/Anthropic docs. No paid cloud agent sessions. No subagents were spawned.

## 2. Latest user requirements (all still binding)

### A. Full answers and explicit return

The operator saw answers end in `...` and disappear before they could finish. Provide the full answer on G2, paginate if needed, keep it open until explicit return. Swipes on an answer page must read the answer, never advance/confirm the main step. Press or “take me back to my step” returns to the same step and image. Phone keeps current step+image consistent alongside conversation. Retain sources/uncertainty.

### B. Correct product identification and actual manual

“Building a white IKEA desk” is vague: show actual photo candidates, let the user identify the model/article, ask only relevant configuration, then use its official assembly manual. Never start generic “unbox, lay out and inventory every part” instructions for an unidentified product. Already-confirmed exact models should avoid redundant interviewing. Cached generic drafts must not bypass identity/manual gates.

### C. Adaptive specialist-style interviewing

Inside the EXISTING starter flow, select the single highest-value clarification based on what changes the procedure/diagnosis/configuration/tools/safety. Minimum sufficient context; no mandatory domain checklist, no repeated known facts, no arbitrary question cap, no forced start after three. Zero–three is only a target. Unknown critical facts must block unsuitable model-specific/unsafe instructions. Offer a practical identification method or reliable visual when the user does not know; avoid endless loops.

Persist a structured task profile: goal, identity/model/variant, symptoms, observations, tools/materials, configuration, experience, previous attempts, safety prerequisites, unanswered critical questions, sources, diagnostic branch/hypothesis and uncertainty. Keep user-confirmed facts distinct from model inferences. Update incrementally and restore across interruptions. Corrections/new goals invalidate mismatched in-flight work and sources while preserving historical progress/evidence.

Explicit decisions: ASK_QUESTION, IDENTIFY_PRODUCT, RESEARCH, START_GUIDE, CONTINUE_GUIDE, SHOW_VISUAL, EXPLAIN, TROUBLESHOOT, REQUEST_CONFIRMATION, ESCALATE_OR_STOP. No separate agent framework. Reuse session, assistant, CREAO and ElevenLabs architecture. Research only after enough context exists; safe asynchronous source discovery may overlap conversation. Do not regenerate a guide for each small clarification. Only grounded safe preliminary actions may start before a complete procedure exists; no invented disassembly.

Handle multi-sentence replies, multiple facts, uncertainty, corrections, nonessential skips, interruptions, unclear transcripts, failed audio and text fallback. Do not execute consequential actions from partial/low-confidence speech. Never infer physical success from the conversation.

### D. Plain English primary instructions (latest screenshot feedback)

The screenshot showed MICKE step14 “FIT 8 CAM LOCKS / PART 103430 ONLY.” Prioritize a human action/method rather than part numbers or jargon. Exact identifiers stay accessible in the dedicated PARTS/manual/details/warnings. Make it a reusable modular card/presentation mechanism for any task; no IKEA cases in core. Do not remove safety-relevant quantities, units, warnings or values merely to simplify wording. Example authored wording now is “FIT 8 ROUND METAL LOCKS / TURN EACH A QUARTER TURN.” It still needs human review against the PDF.

### E. Required conversation evaluation

A exact IKEA model → minimal clarification → guide.
B vague IKEA → real photo choices → selection → configuration → official guide.
C Mac screen issue → discriminate built-in/external/both → observation → appropriate sourced safe branch.
D bicycle tire type unknown → reliable visual identification help → applicable procedure.
E corrected earlier answer → update applicability/context/guide.
F “I don't know” → useful alternative, not repeat.
G audio fails → complete text fallback.
H new goal interrupts questions → no old-task leakage.

These examples are evaluations, not mandatory hardcoded question scripts. Run real tests, inspect traces, and distinguish scripted orchestration tests from live-model and hardware proof.

## 3. Important operational root cause

Read-only `GET http://127.0.0.1:8787/discovery/state` returned **404**. Operator port8787 is still an older loaded Python process, despite its cwd being this worktree. This explains the user's generic IKEA guide bypass: the existing discovery feature was not loaded in the process they were testing.

At stop:

| Surface | PID | Notes |
|---|---:|---|
| Operator backend :8787 | 26722 | cwd final-sprint; command `python -m ghostbuild_core --port 8787 --log-dir /Users/tanushsavadi/Documents/Hackathons/LA_Hacks/.worktrees/final-sprint/logs/bench-0445` |
| Isolated prior preview :8797 | 81276 | `/tmp/ghostbuild-fluid-preview`; also old loaded code relative to current adaptive edits |
| Official simulator automation :9897 | 78897 | Prior simulator connected to Vite5176/backend8797 |
| Isolated Vite :5176 | recheck | HMR reads current G2 source; backend counterpart remains old |

Recheck PIDs before acting. Do not kill unrelated processes. **Neither 8787 nor 8797 was restarted for these new changes.** No current live demo is proof of adaptive code. After finishing tests, back up relevant session JSON and safely restart the operator from this worktree using the SAME log directory; preserve progress/configuration. Do not run another CREAO request during smoke tests. Decide explicitly how to handle the persisted generic unidentified IKEA draft; migration code exists but is unverified. Do not silently erase user sessions.

## 4. What was already complete before this adaptive continuation

These are the earlier verified features, not evidence that current adaptive edits are finished:

- Generic product discovery and IKEA adapter; 54 real validated indexed products with local photographs.
- Phone top-five photo cards; G2 three numbered thumbnails then two on next page; enlarged photo confirmation; cabinet-side manual pictures.
- Two MICKE 35-step cards, 62 guide sets, exact official PDF crops, printed part IDs/quantities cross-checked. Navigation to manual step14, parts103430 vs avoid110126, closeup and manual next work.
- Persistent generic guide/product/standalone grounded-answer cache; unknown IDs, sides, counts, mode and negation stay distinct. Saved verified matches do not force live search. Local cache is ignored by git.
- Stable phone instructions+image left, step-owned conversation right; mobile vertical; hint “Ask anytime — I’ll keep your place” focuses input; dim ASK ANYTIME on G2.
- Late answers stay with their original step; conversations/notes/profiles persist. Browser Q&A used explicitly labelled delayed FakeBrain; not live answer-quality evidence.
- Earlier full suite was core628/Pi77/knowledge257/assets41/IKEA79/G2 208/web28, contracts nine schemas and22 Python+22 TS examples, lint/secrets clean. Earlier simulator11/11 and browser/mobile checked. See `docs/FLUID_ASSISTANT_REPORT.md`, `docs/IKEA_DISCOVERY_REPORT.md`, `docs/IKEA_DISCOVERY_RUNBOOK.md`, `docs/evidence/fluid/`.
- Earlier cached lookup median9.81ms/ten local HTTP samples. Earlier live unfamiliar glass-cabinet proof five validated candidates in11.675s; separate red-cabinet no-match14.309s; two earlier Anthropic searches. Do not claim those as new tests of adaptive code.
- Physical G2 legibility/BLE/microphone still unverified. **Authored MICKE step text still requires a human PDF spot-check.**

## 5. Current implementation: files and actual behavior

### Full-answer surface (implemented, backend tests pass; browser/simulator pending)

- `contracts/models.py`: optional `AnswerPage` on HudFrame (`text`, page index/count, grounding and evidence label), allowed only in ask mode. Optional `Step.instruction: Cue` for human-first primary copy. Existing fields retained. Generated schema/TS files updated (`hud`, `state`, `card`, `_all`, TS).
- `core/ghostbuild_core/hud.py`: Screen.answer, frame dedup includes answer, Hud stamps optional payload. Remains sole HUD writer.
- NEW `core/ghostbuild_core/answer.py`: deterministic ASCII typography folding and word wrapping, 38 chars × five lines/page, no tail truncation. Check unsupported-symbol semantics before shipping; ASCII folding currently drops non-ASCII symbols rather than using all cuefmt substitutions.
- `playbook.py`: persistent `answer_data`/`answer_index` in progress; show_answer emits sticky pages with no TTL. While active, swipes page/clamp at ends; press dismisses without confirmation. Explicit return phrase clears answer. Most nonvisual deterministic explanations and assistant answers use this surface. Existing short THINKING/error/status flashes remain.
- `assistant/service.py`: assistant answers/follow-up and recalled notes call show_answer; source/grounding retained. A short Cue remains for backward-compatible fallback.
- `intent.py` + `assistant/router.py`: “back/return/take me/show me … my/main/current/the step/instructions/guide” takes deterministic return path.
- `server.py`: phone actions answer_next/answer_previous, preserving session/sequence validation. Existing confirm restrictions remain.
- `g2/src/view.ts`: renders AnswerPage's full page lines in existing text view, footer ANSWER n/N + grounding + PRESS: BACK. No new SDK methods.
- `web/app.js` + style.css: full answer mirror, answer previous/next/back controls; does not use step confirmation buttons on answer pages.

### Structured adaptive policy (partial integration, needs review)

- NEW `assistant/adaptive.py`: Decision enum, TaskFact, TaskProfile, observation/correction/new-goal helpers, quoted user-fact validation vs inferred facts, critical-unknown checks, question-key dedupe/loop stop, traces and metrics.
- `assistant/schemas.py`: IntakeReply adds decision/context_sufficient/facts/critical_unknowns/question_key/question_reason/identification_help/branch/confidence; StepReply adds decision/facts/unknowns/branch. Message adds task_id. Existing action/profile/reply fields retained.
- `assistant/prompts.py`: minimum sufficient context and useful questions; no hard cap/mandatory experience; explicit uncertainty, source/identity gates, correction behavior, complete explanations. Step context uses the primary instruction field.
- `assistant/service.py`: MAX_QUESTIONS=None, force-start-after-three removed; tasks persist in assistant.json, current intake partially restored; accepted observations and structured context passed to model; stale task/revision worker results rejected. `_ready_card` requires unique content-covered match, no cands[0] fallback; failure blocks unresolved tasks rather than guessing. Task signatures added to answer-cache key. bind_card records sources/decision. `observe_goal` creates/revises task context.
- `runtime.py`: goal observation before source/cache/intake; generic source-specific cards filtered from startable pool and cached reuse; new-goal/correction handling from mid-step text/voice via Runtime.ask; explicit return calls dismiss. bind_card on actual activation.
- `live_research.py`: refuses starting research while known critical unknowns or confirmation remain.
- `discovery/service.py`: requires_identification guard; correction clears selected identity/config and re-ranks; selection binds confirmed product/config/manual sources into task context. Startup `integrations/product_discovery.py` attempts to reroute a persisted unidentified generic product draft into discovery.

### Human English presentation (implemented in data, not visually verified)

- NEW `core/ghostbuild_core/presentation.py`: `instruction(step)` selects optional authored human wording, else legacy cue. No runtime model, retailer rules, unsafe ID stripping or invented terminology.
- `playbook.py` main cue (with or without default image) and phone heading/cue use primary instruction.
- NEW `knowledge/products/ikea/80213074/instruction_copy.json`: authored human action/method for all35 steps. Both left/right cards populated; part IDs, detail and warnings retained. `build_manual.py` carries copy forward on regeneration. No assets regenerated (only copy/data changed).
- `knowledge/creao_normalize.py`: generic optional `display_instruction`/`instruction_cue` dict imported into Step.instruction; invalid supplied copy falls back to original cue with an uncertainty note. Full knowledge tests not yet rerun after this addition.

## 6. Exact verification at stop

| Check | Current result |
|---|---|
| `make contracts` | PASS, nine schemas,22 Python+22 TS examples |
| Targeted assistant/cache/all IKEA | **105 passed**; `/tmp/adaptive-checkpoint-targeted.log` |
| New checkpoint tests | **6 passed**; `/tmp/adaptive-new-tests.log` |
| Full `make test` | **FAILED at core:630 passed,4 failed**; later Pi/knowledge/assets/IKEA make stages were not reached |
| Web node tests | **28 passed**, `/tmp/adaptive-checkpoint-web.log` |
| G2 tests | **208 passed**,15 files, `/tmp/adaptive-g2-tests.log` |
| G2 build | PASS TypeScript+Vite, `/tmp/adaptive-g2-build.log` |
| lint-generic and secret scan | Passed at start of latest make run (800 files then); final docs were edited afterward |
| New small-module Ruff | Five issues fixed; answer/presentation/adaptive/checkpoint test modules formatted; no full-repo lint claim |
| `git diff --check` | Clean at stop |
| New browser/simulator/manual-copy visual checks | **NOT RUN** |
| New A–H conversation/live-model evals | **NOT RUN** |

New `core/tests/test_adaptive_checkpoint.py` covers full-text page concatenation (180 words), staying past60s, no step completion from paging, persisted page + spoken return, primary cue/fallback, fake user quote downgrade/correction, critical facts winning over start despite four previous questions, and five distinct clarifications without forced research/start.

### Four failing tests — inspect; do not just weaken assertions

1. `core/tests/test_live_research.py::test_a_clarified_request_reaches_research_with_the_persons_context` (~line199): legacy FakeBrain returns action=start with no `context_sufficient`; new policy correctly does not dispatch its mocked CREAO request. Fixture input says “fix my bike tyre” while mock goal is “replace a bicycle inner tube.” Update the fixture to explicitly supply sufficient, applicable facts (including known tire setup) and set context_sufficient only when warranted. Add the complementary critical-unknown-block test. Do not restore forced research.
2. `core/tests/test_playbook.py::test_overlay_returns_to_the_step_exactly_after_its_ttl` (~line326): still expects answer TTL4000 and automatic return. Preserve the measured uncertain-warning TTL assertions; replace only answer expectations with sticky answer + explicit press return.
3. `core/tests/test_playbook_runtime.py::test_ask_intents_answer_from_card_text_only` (~line400): same old answer TTL4000/auto-return assumptions; later confirm assumes overlay expired. Explicitly return before confirming, asserting no accidental step completion.
4. `core/tests/test_troubleshoot_state.py::test_current_step_first_and_tried_list_resets_when_a_step_is_confirmed` (~line39): swipe-down now pages the sticky troubleshooting answer rather than confirms, so it correctly stays on the same exhausted checks. Press to return first, then explicitly confirm and assert prior-step retry ordering. Do not let a reading swipe confirm.

No edits to those four tests were made after the stop request. `test_assistant.py` earlier obsolete max-three/force-start tests were replaced with loop-stop/no-guess checks and state max=None. Existing new six tests are in addition to that baseline.

## 7. Known integration gaps / review hazards

These are specific concerns observed by code review, not all proven failing tests:

- No current browser/simulator proof of paginated answers. Validate all pages, repeated swipes at ends, source footer fit, persistence and explicit return on step3/6; no clipped final lines. The native simulator's RGBA screenshot alpha must be composited on black for inspection.
- `show_ask(THINKING)` can leave a previous sticky answer under the transient flash; press during pending thinking is not yet wired to silence the later worker result. Verify/dismiss pending behavior.
- Clear an old answer if measured evidence automatically moves the playbook to another step. `_compute_screen` ignores an answer tied to another step, but handle_input currently checks non-null answer_data without verifying ownership; it may trap gestures after evidence-driven advancement. Add regression coverage.
- Direct gesture confirm is protected while reading, but deliberate spoken `next` leaves the answer and follows the existing explicit manual-confirm path. Make that distinction clear, preserve evidence restrictions.
- Task restore persists pending question and intake state, but replaying its glasses question on reconnect has not been exercised. SessionManager's `_convo` is not itself persisted. Restore should not ask a resolved fact again.
- Model schema additions raise structured-output size. Existing AnthropicBrain max_tokens=900 may be too small; investigate truncation/stop_reason and bounded output budget against the new schema. No live model test was run.
- `_ready_card` currently checks the ORIGINAL first_text and requested library_id, not always the fully clarified user goal. This may unnecessarily route a now-specific request to research. Use confirmed context carefully; do not reintroduce keyword-first matching. `_begin` should also send a newly recognized brand-specific clarified goal through discovery before generic resolution.
- The new generic policy relies on model-reported critical_unknowns/context_sufficient. Audit any direct resolver/cache path that could bypass known critical facts. Cached personalized guides still need full task applicability, not just text similarity.
- Some decision values (SHOW_VISUAL, CONTINUE_GUIDE, TROUBLESHOOT) are currently primarily traces/prompt outputs, not a complete adaptive graph transition. They must dispatch only existing sourced assets/procedures, never raw model-created physical actions.
- `reference_notes()` looks for `knowledge/intake_references.json`, but that file was **not created**. There is no new bicycle identification visual or Mac diagnostic card. Official references researched, not imported: https://www.schwalbe.com/en/technology-faq/tubeless/ and https://support.apple.com/en-us/102555 . Do not fabricate diagnostic specifics or equate tubeless-capable markings with confirmed installed setup. These cases still require grounded implementation/evaluation.
- No confidence metadata/uncertain-product-selection confirmation path was added to STT. Existing committed-only transport stays intact; do not claim low-confidence handling is finished. `uncertain()` helper exists but is not fully integrated.
- `web/audio.js` still truncates spoken text with `.slice(0,500)` and backend SpeakBody caps500. Full spoken-answer handling/chunking is still pending; do not add unbounded speech or lose cancellation/consent.
- Mid-step context correction/new-goal routing is new and not covered by A–H traces. Test stale worker cancellation, not leaking old history, preserving unrelated context and progress, product-model correction vs minor explanatory clarification. Avoid overreacting to every “actually.”
- The plain-wording field and copy importer exist, but CREAO build-time prompt has not been updated to request it. No new feature flags for adaptive/paged-answer behavior were added yet; review project flag policy.
- Startup migration for persisted generic IKEA draft and source-card filtering were not tested with `logs/bench-0445`. Preserve backup, inspect rather than erase. Manual verification flag/URL-to-bundle matching should be reviewed before auto-start.
- Recheck source/safety labels: AI explanations grounded in a guide remain INFERRED, never measured/manufacturer-authored answers. Printed manual diagrams retain manufacturer attribution. Source labels must not imply authored copy was human reviewed.

## 8. Recommended continuation order

1. Re-verify current code/test state from this file. Reproduce the four failures, align tests with intentional behavior, and fix genuine regressions. Add ownership/pending/measured-step edge cases for sticky answers. Get full suite green before live integration.
2. Finish/review adaptive context, dispatch, ready-card matching, corrections, uncertainty and persistence; add structured conversation traces A–H. Use domain data/reference adapters, not hardcoded example scripts.
3. Finish generic human-instruction authoring/import/presentation and review all35 MICKE human cues alongside the PDF. Keep exact part queries/reference correctness. The required HUMAN spot-check remains an operator responsibility.
4. Exercise new answer/identity/manual flows in Chromium and official simulator, including the exact phrase “building a white IKEA desk.” Optional bounded live brain tests may assess question quality; report call counts. Do not run live CREAO.
5. Reload the stale operator backend only after the implementation is safe, preserving its log dir/session state. Verify discovery endpoint exists, vague request gives real photo shortlist, selection loads the corresponding verified manual, and all return gestures work.
6. Update runbook/status/evidence with actual counts and remaining limits. No commits or pushes. Report what was verified in real UI vs mock vs hardware. Keep handoff current if another context limit approaches; account quota percentage is not visible to Codex.

## 9. Prompt preparation notes

The separate prompt follows Anthropic's current general and Opus5.5 guidance: clear task boundaries, concrete acceptance criteria, structured context, concise progress updates and an explicit completion condition. It does not ask for hidden chain-of-thought, max effort, or repetitive verification after checks pass. Sources:
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
