# Final sprint status

## Latest: universal framework (06:40 PDT, Claude Opus 5.5) — see [FRAMEWORK.md](FRAMEWORK.md)

Branch `codex/final-sprint`, checkpoint commit `a4d0f14` (+ later commits; local only, nothing pushed). Operator :8787 reloaded 06:08 (backup `logs/backup-bench-0445-0608`).

| Capability | Label | Evidence |
|---|---|---|
| Branching action graph in the existing contract | ENGINE TESTED + SIMULATOR VERIFIED | additive `Step.kind/choices/next/expected/tools/risk`, `Card.task_kind/review`; G2 menu question, swipe/press answer, route-back, hazard double confirm, outcome/stop; `core/tests/test_branching.py` |
| Generic source adapter + verified compiler | LIVE VERIFIED | `knowledge/sources.py`, `knowledge/compile.py`, `knowledge/find_sources.py`; verbatim quotes, routes and glasses text checked in code; `knowledge/tests/test_compile.py` |
| Cached demos | CACHED, AI-COMPILED (not human-reviewed) | Mac display colours (6 Apple pages), flat bike tyre (4 Park Tool pages, 12 photos), Prusa MK4 extrusion (3 Prusa pages); all 0 validation errors |
| Uncached dynamic task | LIVE VERIFIED | "clean the filter on my Bosch dishwasher" → 3 official Bosch pages → 10-step guide on the glasses in **32.8 s** (2 Anthropic requests); `docs/evidence/adaptive/live-uncached-compile.json` |
| Interview → guide | LIVE (real assistant) | Mac: intake 3.3 s → guide; "only my external monitor…" answers the guide's question (0.01 s, no model); bike: "I'm not sure what kind of tire" → sourced identification step |
| Visuals | SIMULATOR + BROWSER | source photo + vision crop/highlight; comparison pictures whole; Mac menu-path drawings (labelled, not screenshots); "what should it look like" → CORRECT picture or the source's own expected text, else "not described" |
| Research while conversing | ENGINE TESTED | the assistant's question about an uncached task starts source search/fetch, keyed by task revision |
| Engine page (Act IV) | BROWSER VERIFIED | `/phone/engine.html` from `/engine/summary`: sources, quoted steps, questions, pictures per guide |
| Hot path | MEASURED | local HTTP medians: state 0.98 ms, G2 picture 1.29 ms, deterministic ask 1.55 ms (`docs/evidence/framework/hot-path-latency.json`) |
| Anthropic usage this phase | COUNTED | demo compiles 13 + 5 + 9 + 13 + 13 (bike v1–v3, Mac v2, Prusa incl. vision crops), Mac v1 2, live uncached 2, live assistant runs ≈10. CREAO 0. ElevenLabs 0 |
| Physical G2 / mic / BLE | NOT RUN | |

## Latest: adaptive assistant finished by Claude Opus 5.5 (05:35 PDT) — operator :8787 reloaded

Takeover of [CLAUDE_ADAPTIVE_TAKEOVER.md](CLAUDE_ADAPTIVE_TAKEOVER.md). Nothing committed or pushed by Claude (note: four commits at 05:05 on this branch were made outside this session). Evidence: `docs/evidence/adaptive/`.

| Capability | Label | Evidence |
|---|---|---|
| Full suite | PASS | `make test`: core 651, Pi 77, knowledge 257, assets 41, IKEA 82, G2 208 (+ `npm run build`), contracts 9 schemas / 22 Py + 22 TS examples, lint-generic, secret scan (824 files); web `node --test` 29; `git diff --check` clean |
| Four handoff failures | FIXED | Three were obsolete 4 s answer-TTL expectations → now sticky answer + explicit press return (measured-step uncertain TTL asserts kept); research fixture now supplies the tyre setup and `context_sufficient`; new test: a critical unknown blocks research |
| Full G2 answer pages | SIMULATOR + BROWSER VERIFIED | Official simulator: 4 pages ending "END OF ANSWER", swipes page and clamp at the end, press returns to step 14 with the same diagram, nothing confirmed; press during THINKING returns to the step and the late answer goes to the phone only. Chromium: same paging/return via phone buttons and typed "take me back to my step"; 390 px mobile, no overflow (mirror text overflow fixed). Answers came from a labelled delayed FakeBrain QA harness |
| Vague "building a white IKEA desk" → photo → manual | SIMULATOR + BROWSER VERIFIED | Real photo shortlist (MICKE/ALEX/IDANÄS), enlarge → choose → cabinet side (remembered if known) → official manual step 1/35 with diagram. Two MICKE sizes exist, so "It's the MICKE" asks which photo/article. Assistant never consulted for identity (FakeBrain calls = 0) |
| Conversation traces A–H | SCRIPTED (orchestration only) | `core/tests/test_conversation_traces.py`, `integrations/ikea/tests/test_conversation_ikea.py`; FakeBrain plays the model |
| Live model intake/step quality | LIVE (bounded) | `docs/evidence/adaptive/live-intake-eval.json`: 6 Anthropic requests, 1.9–4.3 s each (fast mode). One targeted question per turn, critical unknowns listed, "I don't know" got a practical check, step-14 explanation grounded in the manual card (3 G2 pages, step unconfirmed). Small sample, not a benchmark |
| Structured-output schema | FIXED (was broken live) | The enlarged reply models were rejected by the API (`400 Schema is too complex` after ~35 s). The model now fills flat all-required wire shapes (`IntakeWire`/`StepWire`) converted to the existing replies; `max_tokens` 1600; `max_tokens` stop = BrainError |
| Operator :8787 reload | DONE | Same command, log dir `logs/bench-0445`, `.env` config, stdout `/private/tmp/gb-core-8787.log`; backup `logs/backup-bench-0445-0532`. `/discovery/state` 200. The persisted unidentified CREAO desk draft now reopens as the real MICKE photo shortlist (previously a restart would have shown PI LINK LOST) |
| Paid calls this session | COUNTED | CREAO 0, ElevenLabs 0. Anthropic: 6 successful eval requests + 1 diagnostic success; the first eval and diagnostics hit the schema error (5 brain calls with fast→standard fallback and SDK retries, plus 2 diagnostic attempts; ≤22 failed HTTP requests); 1 web_search request (11.0 s, ikea.com) at operator startup. 0 since |
| Physical G2 / microphone / BLE | NOT RUN | Simulator/browser only |
| Authored MICKE human wording | PENDING HUMAN | Consistency pass restored two dropped quantities (step 33 "FIT 8 SHELF SUPPORT PINS", step 35 "PRESS IN 4 ROUND CAPS"). Steps 3/14/19/22/27 all read "ROUND METAL LOCKS" for three different lock IDs; exact IDs/warnings remain in PARTS/detail. Human PDF spot-check still required |

New flag: `GB_ANSWER_PAGES=0` restores the old short timed answer cue. Operator `.env` still has `GB_CREAO=1`, `GB_LIVE_RESEARCH=1` (max 3): any unfamiliar non-product request in a demo can start a paid CREAO run.

## Latest follow-up: fast reuse + same-step conversation

See [FLUID_ASSISTANT_REPORT.md](FLUID_ASSISTANT_REPORT.md). Generic completed-guide/product/grounded-answer caches now persist; saved matches do not force a new search. Phone instructions + diagram stay left, step-owned questions right; a small “Ask anytime — I’ll keep your place” link focuses input. G2 shows ASK ANYTIME beside the counter and displays each MICKE diagram automatically. Late answers remain on their original step.

Verification: `make test` passed (core 628, Pi 77, knowledge 257, assets 41, IKEA 79, G2 208); web 28. Official simulator 11/11, real Chromium desktop/mobile and offline recovery checked. Q&A orchestration used a labelled mock harness; zero new paid calls. Cached HTTP median 9.81 ms (10 samples). Physical hardware and the human MICKE text spot-check remain pending. All work stays uncommitted; no operator-service or agent-configuration changes.

## Latest: IKEA discovery completion (2026-10-18, Codex takeover)

All work remains uncommitted in `codex/final-sprint`; nothing pushed. See `docs/IKEA_DISCOVERY_REPORT.md` and `docs/IKEA_DISCOVERY_RUNBOOK.md` for full proof and exact interactions. Existing operator services and G2 package were preserved; isolated ports were used for verification.

| Capability | Label | Evidence |
|---|---|---|
| Generic product discovery inside existing request flow | CACHED / ENGINE TESTED | Exact article/URL first, cached ranking second, asynchronous official-site search third; remembered product/configuration and reconnect/restart |
| Phone shortlist | BROWSER VERIFIED | Five actual product photographs with names, colour/size/article, verified-manual badges and honest cache dates; 390 px mobile viewport, no overflow |
| G2 shortlist photographs (user's clarification) | SIMULATOR VERIFIED | Three numbered product photo thumbnails with names/highlight, then two on page 2; enlarged-photo confirmation, text fallback; existing SDK renderer unchanged |
| MICKE left/right manuals | CACHED / VALIDATED | Two 35-step cards; 62 guide sets; part-number/printed-quantity cross-check; exact manual crops; step 35's genuine per-configuration difference preserved |
| Exact demo utterance script | ENGINE TESTED | Description → MICKE → left → step 14 → eight 103430, avoid 110126 → closeup → confirmed step 15; no earlier steps confirmed by jump |
| Live product retrieval | LIVE VERIFIED | Anthropic web_search_20250305, claude-opus-5-5, ikea.com only; 2 new requests, 0 CREAO calls. Black glass-door description → 5 real validated candidates + PDF checks in 11.675 s; red-cabinet query honestly no-match in 14.309 s |
| Cached latency | MEASURED | Local HTTP 10 samples: 7.98–14.11 ms, median 9.08 ms; separate mobile first-five-photo render 385 ms (one sample). Not physical BLE timing |
| Complete suite | PASS | Core 617, Pi 77, knowledge 257, assets 41, IKEA 76, G2 207, web 24; contracts, generic lint and secret scan pass |
| Official simulator + actual core | SIMULATOR VERIFIED | 11/11 product/guide/gesture checks, actual SDK photo/manual image sends, zero console errors |
| Uncached-manual research | MOCK TESTED ONLY | Existing CREAO wiring accepts official doc URLs; GB_DISCOVERY_RESEARCH=0 by default; do not run live without new authorization |
| Authored MICKE step text | PENDING HUMAN | Human still needs to spot-check verbs/text against the official PDF |
| Physical G2 / on-glasses voice | NOT RUN | Simulator/browser evidence does not establish hardware legibility, BLE latency, or microphone capture |

`GB_DISCOVERY=1` enables this feature (default on when index exists); `GB_DISCOVERY_LIVE=0` is the reliable offline demo. Restart the operator backend from the updated worktree when ready to demonstrate. The welcome flow is unchanged, and manual completion remains HUMAN CONFIRMED.

---

Updated Sun 2026-10-18 ~01:10 PDT by Claude Opus 5.5 (took over from Codex at its 00:05 usage-limit stop). Deadline Sun 12:00 PDT; Devpost by 10:30, final Beta QA 11:00.

## Where the work is
- Integration branch `codex/final-sprint` in `.worktrees/final-sprint` (ahead of `origin/lead/hw-pivot` `cd83f6a`). `git log --oneline` is the truth. Nothing pushed. `b/voice` / PR #2 not merged.
- Codex worker branches final-g2 / final-voice / final-creao are already cherry-picked. Leftover (not integrated): uncommitted `g2/package*.json` edits + `g2/sim-shots/` in the final-g2 worktree.

## Verification (label = strongest evidence we have)
| Capability | Label | Evidence |
|---|---|---|
| `make test` | PASS | core 501, pi 77, knowledge 253, assets 41, g2 183, lint-generic, secret scan; web `node --test web/tests/*.mjs` 17 (not in make) |
| CREAO live run | LIVE VERIFIED | agent GhostBuild Intelligence, app-scoped `POST /api/v1/apps/{appId}/runs` (docs.creao.ai), run `f255860d-...` completed in ~3 min (status `completed`); raw saved (gitignored) at `knowledge/requests/creao_raw/` |
| CREAO output -> playbook | LIVE VERIFIED | playbook is a JSON artifact (`result.artifacts[]`, S3 redirect, key not forwarded) -> `attach_json_artifacts` -> normalizer -> `validate_envelope` OK: 7 steps, 7 sources (4 official/manufacturer type), troubleshooting branches mapped |
| Human review + approval of that card | PENDING HUMAN | draft `pi_gpio_led_blink-20261018T080246` (gitignored `knowledge/drafts/`); needs `python -m knowledge.approve <id> --reviewer "<name>"` by a human. Reviewer edits are in `/tmp/gbv/review.py` (curated checks, guides attached, title shortened) |
| ElevenLabs STT | LIVE VERIFIED | `/ws/voice` with consent: spoken "Where exactly is that?" (macOS `say`, 16 kHz PCM) -> transcript exact in 0.55 s -> task-aware `rt.ask` -> HUD switched to `cup_fold_half/where.png` |
| ElevenLabs TTS | LIVE VERIFIED | `/voice/speak` consent=true, voice Matilda `XrExE9yKIg1WjnnlVkGX` (premade, chosen via ElevenLabs MCP; API key lacks `voices_read`): HTTP 200, valid MP3 6.2 s, 0.63 s |
| Phone playback | SIMULATOR VERIFIED | Chromium: text question -> `speak()` -> `Audio.play()` resolved, duration 6.3 s (the real MP3, network-intercepted so no extra quota). Audible output NOT confirmed |
| WHERE / HOW / CORRECT | SIMULATOR VERIFIED | API on paper_cup + the LED card: press/ask opens the right image for the current step; "Wait, where exactly is that?" -> `led_pins/where.png`; CORRECT tested; confirm from inside a picture = 409 |
| Stateful troubleshooting | MOCK/ENGINE TESTED | "that didn't work" walks current-step checks, then already-confirmed steps (most recent first), never repeats, then NO MORE CHECKS HERE; never confirms a step; 4 new tests |
| `.ehpk` | BUILT, NOT INSTALLED | `g2/ghostbuild.ehpk` (no mic permission; LAN `172.22.171.236:8787`) |
| Physical G2 | NOT RUN beyond Codex's report | operator reported (earlier session) LAN + QR + first frame + BUILD/FIX. Images, gestures, voice: awaiting operator |

## First-run flow (changed 01:30 PDT on operator feedback)
- No BUILD/FIX question. Glasses: welcome `WHAT DO YOU NEED?` -> first screen lists every startable task (`HOLD TO SPEAK OR PICK` when voice is on). Spoken or typed goals match across all tasks; build/fix is only a hint (core retries the other mode). Phone: one box, no toggle.
- A fault-mode card (needs live Pi telemetry) is offered only while the Pi reports; fixes "STALE DATA / CHECK LINK" on a bench with no Pi (operator saw it after pressing the old FIX default). SIMULATOR VERIFIED + tests (core 507); physical re-test pending.
- Dev-server QR sideload: Vite is run with `VITE_FLAG_VOICE=1`; whether the sideloaded app gets the microphone permission is UNVERIFIED (a missing permission degrades to `VOICE UNAVAILABLE / USE TOUCH`).

## Gestures (one meaning everywhere, changed 02:25 PDT after the operator's first physical session)
- Physical G2 evidence from the operator log: welcome, task list, press-to-start, swipes and picture requests reached core on real glasses (first step-through of paper_cup). Pain points found there: 1.5 s swipe dead zone, swipes meaning different things inside pictures, blank dead end after completion.
- Now: swipe down = next step (confirms a manual step; refuses a measured one), swipe up = back, press = picture button (WHERE -> HOW -> CORRECT -> back). Swipe from a picture: up = back to its step, down = confirm + next. First step shows immediately (no title card). Any gesture skips the welcome. After "ALL STEPS DONE" the next press/swipe-down opens the task list. Settle guard 600 ms (was 1500). Core 509 tests; still NOT re-tested on the glasses.

## Live research (03:10 PDT, on operator request)
- An unmatched spoken/typed request now researches live instead of "QUEUED FOR RESEARCH": glasses show `RESEARCHING m:ss / <task>` (5 s steps), the phone shows a thinking panel, then the guide starts by itself with `AI RESEARCHED, UNREVIEWED`. Phone banner: AI-RESEARCHED · NOT HUMAN-REVIEWED. Opt-in `GB_LIVE_RESEARCH=1` (now set in `.env`), cap `GB_LIVE_RESEARCH_MAX=3` per server start, one at a time, >=2 words, same request is served from the finished draft for free.
- LIVE VERIFIED (1 real CREAO run, push button on a Raspberry Pi, run r-fb9f9298): thinking screen ticked 0:00-5:00, run ~5 min, card auto-started (6 steps, 5 sources). The agent drew a PNG diagram; picture pipeline (SVG or PNG -> 288x144 G2 image + phone image, labelled AI-generated diagram, not a photo) verified OFFLINE on that real artifact and in tests, not yet re-run live end to end.
- Deliberate change to the earlier rule that only reviewed cards reach the glasses: these cards pass the same validator but are not human-reviewed; they stay drafts on disk and in memory only until a human approves.
- Tests: core 519, knowledge 257, assets 41, g2 184, web 18.

## Quiet intelligence (03:45 PDT, operator design principle)
- Screens that only wait for the wearer rest (go dark): the front prompt after 20 s, the research wait after 10 s (env `GB_REST_PROMPT_S`, `GB_REST_RESEARCH_S`). A gesture wakes it (the first gesture only wakes, never acts), a hold to speak wakes it, and a finished guide / failure / answer always wakes it. Steps, answers (then 4 s auto-dismiss; now full pages until an explicit return, see the top) and pictures-on-press unchanged. Core 525 tests; not yet felt on the glasses.
- Research wait: estimated progress bar + time left (glasses `●●●○○○○○○○ ABOUT 40S`, phone determinate bar + stages), labelled as an estimate; learns from real run durations. Fast-mode research measured 105 s vs 295 s.
- Conversational intake (Claude brain) NOT built yet: needs `ANTHROPIC_API_KEY` (none present; ElevenLabs key lacks convai).

## Conversational assistant (04:30 PDT, operator request)
- Package `core/ghostbuild_core/assistant/` (schemas, cuefmt, prompts, brain, router, service). Brain = Claude via the official SDK, `claude-opus-5-5` at low effort with **fast mode** (measured 1-2 s per turn vs 5-6 s standard; `GB_BRAIN_MODEL`, `GB_BRAIN_FAST=0`, `GB_ASSISTANT=0` to switch). Needs `ANTHROPIC_API_KEY` (set). No key / any failure = the old deterministic behaviour.
- Intake (before a guide): asks one question at a time (max 3): what exactly / symptoms, device, experience, parts on hand; never assumes, never judges the person's parts; electronics/tool tasks ask experience once even for a ready guide, trivial crafts start at once. Question shows on the glasses (2 lines) + phone chat with tap-to-answer chips; profile (experience + facts) is remembered for the session and sent to research as "Who this guide is for".
- Step questions: commands/FAQ stay deterministic; real questions ("how do I identify the three servo wires") go to the assistant with the guide, current step, checks, confirmed steps, notes and profile as context. Answer cue on glasses (instant THINKING), full text on phone/earbuds, labelled FROM THE GUIDE / GENERAL KNOWLEDGE / NOT SURE. Useful answers are kept as notes on that step (phone shows "Extra help on this step"); "remind me what you said" replays the last note without the model.
- LIVE VERIFIED (real model through the real runtime, scripted user): LED request -> THINKING 2.7 s -> guide started; mid-step question -> answer in 1.9 s, correct, note kept. Intake quality checked on 6 varied requests. Wrong answers seen earlier from Haiku on a resistor question are why Opus is the default.
- Head shake (IMU) trigger + hands-free listen (silence endpointing): modules and tests done (g2/src/headshake.ts, endpointer.ts, imu.ts; 207 G2 tests). Flag `VITE_FLAG_HEADSHAKE=1` (needs voice). **NOT VERIFIED on hardware**: the SDK gives IMU x/y/z with no documented units/axes, so the detector self-calibrates; thresholds may need tuning (`VITE_HEADSHAKE_SWING`, `VITE_HEADSHAKE_DOMINANCE`).

## Not done / blocked
- Physical G2 image + gesture + reconnect test (operator). Voice on G2 needs a voice-build `.ehpk` (`VITE_FLAG_VOICE=1`, declares g2-microphone) and a real device test.
- Human approval of the LED card (above). Hero hardware (Pi / breadboard / LED / 330 ohm) availability unconfirmed with the operator.
- Second live CREAO task: not run (the one authorized run is spent). Generality is shown with hand-authored paper_cup + pi_camera_setup + the researched LED card on the same engine.

## Services (Claude)
- Operator-facing: core `:8787` (from `.env`: GB_VOICE/GB_TTS/GB_CREAO on) and Vite `:5173`, LAN `172.22.171.236`. QR: `make g2-qr`.
- Claude test instances: core `:8793` (cards in `/tmp/gbv/cards`), static server `:8899`. Stale Codex processes (:8788/:8789/:8791/:5174) idle.

## Next executable actions
1. Operator: physical G2 steps; approve the LED card.
2. Claude: voice-build `.ehpk`; demo runbook + backup path; screenshots; Devpost text and sponsor evidence; freeze by ~10:00.
