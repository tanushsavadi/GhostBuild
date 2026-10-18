# GhostBuild final release status

Updated October 18, 2026. Submission deadline: noon PDT; target Devpost completion: 10:30 AM. This is the current release record. Earlier sprint details remain in Git history and the linked evidence reports.

## Release candidate

- Integration: `codex/final-sprint`, `.worktrees/final-sprint`. Correction implementation: `e816740` plus subsequent release-label/documentation commits.
- Existing sprint history and authorship are preserved. The unrelated Open Palm/ASL branch and voice PR #2 are not broadly merged.
- Operator backend `:8787` reloaded at 06:57 and 07:09 PDT from the corrected checkout, preserving `logs/bench-0632` and a timestamped backup. Health returned HTTP 200. Its existing optional provider configuration was retained.
- GitHub publication/CI/merge: in progress; verify the remote PR and `main` before treating this record as a completed merge.

## Fresh verification

`make test` on the combined integration checkout: **1,161 Python tests** (core 688, Pi 77, knowledge 267, assets 41, IKEA 88), **32 phone tests**, **208 G2 tests**. Nine schemas and 22 examples in each language validate; TypeScript, generic lint and secret-pattern checks pass. Knowledge emits six existing PyMuPDF/Pillow deprecation warnings. The final combined run includes the three review-label regressions and two ready-guide/discovery switch regressions.

| Scope | Result and evidence |
|---|---|
| Corrections | 30 focused regression cases: negated clauses, affirmative outcome sentences, changed/uncertain reports, route-back, downstream-question invalidation, preserved completed actions, stale assistant cancellation, model variants and product re-identification. [Tests](../core/tests/test_corrections.py), [IKEA tests](../integrations/ikea/tests/test_corrections.py), [deterministic traces](evidence/framework/corrections-deterministic.json). |
| Fresh browser | Chromium desktop/mobile: no horizontal overflow at 390 px; Mac diagram routes HTTP 200; correction to BOTH, answer return, bike uncertainty/readiness, MICKE-to-MALM manual fallback. Exact ready-guide selection now exits unfinished discovery. Zero console errors in the final focused flow. Captures/logs are local at `/tmp/ghostbuild-release-final/`. |
| Official simulator | 15 checkpoints through two real generic cards, three successful SDK image sends, help return, HUMAN CONFIRMED completion and a final blank frame. Simulated gestures, not performed physical tasks. Local evidence: `/tmp/ghostbuild-release-qa/simulator/`. |
| Live IKEA retrieval | Correction to MALM removed MICKE; official listings/photos and manual links retrieved. Selecting a listing offers its manual, with no invented prepared guide. |
| Live Prusa compilation | MK4-to-MK3S+ correction removed old guide and compiled 13 steps from two official Prusa pages. Wall time 111.63 s in one bounded run; not a latency guarantee. AI-compiled, not human-reviewed. [Live correction record](evidence/framework/release-live-corrections.json). |
| Physical G2 | **Operator-reported PASS** for this voice-disabled build: readable cue/image, press/swipes, answer return, reconnect. Detailed record still pending; not an independent automated device test. Mic/head-shake/Pi telemetry not established by this report. |
| Provider history | Earlier sprint notes report real CREAO artifact normalization and ElevenLabs synthetic-audio STT/TTS. Not re-run during this release. Live correction tests here used Anthropic, not CREAO. Fresh bounded ElevenLabs checks: TTS HTTP 200, valid 3.019 s MP3 in 1.391 s; STT provider startup failed after 5.013 s, without a transcript. Guidance/progress recovered unchanged. [Voice evidence](evidence/release/elevenlabs-live.json). [Earlier status record](https://github.com/tanushsavadi/GhostBuild/blob/65ce651/docs/FINAL_SPRINT_STATUS.md). |

## Packages and security

- LAN build: `g2/ghostbuild.ehpk`, also `/tmp/ghostbuild-release-artifacts/ghostbuild-lan.ehpk`; 47,035 bytes; SHA-256 `eb5859301a5fc7d0287b3225fde735b9ba385d4d2af05ee98e58b447295aa90a`. Built for the presenting laptop's current backend origin; rebuild if its IP changes. G2 mic permission is absent.
- Portable build: `/tmp/ghostbuild-release-artifacts/ghostbuild-portable.ehpk`; 47,015 bytes; SHA-256 `beca3e146f7e4904446b594205ea46e3742d1f0b1a674887463afa3da7c5bf6f`. Uses localhost; this is a software/CI artifact, not a phone-ready network configuration.
- Python locked dependency audit and `npm audit --omit=dev`: PASS, no known advisories in the audited production dependencies. Repository secret-pattern scan: PASS; this is a pattern check, not a proof that every historical object is safe.
- Full npm development audit: **FAIL: six affected development dependencies** (two critical, one high, three moderate). Vite/Vitest major upgrades are deferred during the freeze. Exact advisories and disposition are in [release verification](evidence/release/VERIFICATION.md). Do not treat this debt as a clean full dependency audit.
- Three original Mac diagrams are bundled with reproducible sources. Third-party bike/Prusa photos remain optional local caches with source-link/text fallbacks; no new third-party images were added to make portability tests pass. Existing manufacturer content keeps its attribution; wider distribution rights still need review.

## Acceptance matrix

PASS means the stated scope was exercised; it does not silently imply physical or live-provider verification.

| Required check | Status | Evidence / limit |
|---|---|---|
| Git work and contributions preserved | PASS | Existing history retained; isolated lanes cherry-picked; unrelated branches untouched. |
| No unexpected dirty changes | NOT RUN | Final documentation commit/remote verification pending. Root checkout's pre-existing untracked agent configuration is preserved. |
| Coherent architecture and generic BUILD/FIX | PASS | One card/action-graph runtime, single HUD writer; contracts and generic lint pass. |
| Existing onboarding | PASS | Single WHAT DO YOU NEED prompt/catalog; cached requests and manual tasks work. Obsolete BUILD/FIX toggle is not restored. |
| IKEA identity/manual guidance | PASS | Cached browser flow, matching MICKE orientation and step diagrams. Human wording spot-check remains required before physical assembly instructions. |
| Contextual questions preserve state | PASS | Tests, simulator and final browser answer-return check. |
| WHERE/HOW/CORRECT | PASS | Three actual SDK image sends in official simulator; operator reports image readable. Optional external-cache failures retain fallback. |
| Diagnostic branches/corrections | PASS | Regression suite and final browser Mac/bike/product checks. |
| Appropriate safety behavior | PASS | Hazard confirmations, stop branches, no manual completion of measured steps tested. Expert review of compiled repair content remains pending. |
| Voice/non-voice fallback | PASS | Text/gestures and audio lifecycle pass; fresh TTS provider generation passes. Fresh STT startup FAIL; physical mic NOT RUN. Voice remains optional and the staged G2 package disables it. |
| Phone polish/usability | PASS | Fresh desktop/mobile, context/label/caption fixes, 390 px no overflow. |
| G2 build/package | PASS | Portable and LAN archives above. |
| Physical G2 status honest | PASS | Operator-reported checks distinguished from independent verification; details pending. |
| Tests/lint | PASS | Counts and scope above; remote CI still pending. |
| Secret/security checks | PASS | Secret-pattern/Python/production npm checks pass. Full dev audit remains FAIL and disclosed above. |
| README/docs/setup | PASS | Real captures, exact commands, linked setup/architecture; locked bootstrap exercised. |
| Demo script | PASS | Five-minute IKEA + Mac walkthrough with cached text fallback; physical/manual review preflight remains. |
| Submission copy / sponsor evidence | PASS | All four official tracks and seventeen challenge entries assessed; claims bounded. |
| Integration branch pushed | NOT RUN | Initial HTTPS push timed out; retry/remote confirmation in progress. |
| Main merged and remote verified | NOT RUN | Await remote branch publication and CI. No branch-protection bypass authorized or used. |
| Release-blocking defects concealed | PASS | Hardware scope, human content review, missing publication assets and dev advisories explicitly recorded. |
| Even Beta / video / Devpost | NOT RUN | Package built; official Even Hub portal is signed out in the available browser, so Beta upload requires account sign-in. No video URL or submission receipt established. |

## Presentation and remaining human work

Use **IKEA identity + exact part lookup**, then **Mac branching/correction**, with prepared text/diagram fallback. Bicycle and Prusa are optional follow-ups, not extra five-minute segments. [Five-minute script and 120-second filming plan](DEMO_RUNBOOK.md). [Ready-to-copy submission and official track/prize curation](HACKATHON_SUBMISSION.md).

Remaining human records/actions: supply physical test details; spot-check MICKE stage wording against the official PDF; review compiled repair content before practical use; upload the correct LAN package to Even Hub Beta; record/upload the two-minute video; confirm team/provenance/asset rights; satisfy the event's public-source/judge-access requirement (repository currently private); complete Devpost and verify its receipt. Voice capture and Pi evidence need their own physical tests before claiming them.
