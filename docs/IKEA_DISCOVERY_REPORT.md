# IKEA discovery completion and evidence

**Latest follow-up:** [persistent reuse, automatic step images and same-step conversational help](FLUID_ASSISTANT_REPORT.md). The measurements and test counts below describe the earlier discovery completion; the linked follow-up has the current counts and captures.

Work: `.worktrees/final-sprint`, `codex/final-sprint`, 2026-10-18. Nothing committed or pushed. The working G2 package, CREAO agent and ElevenLabs integrations were preserved. Existing operator services were not restarted; verification used isolated backend ports 8796–8798 and simulator/Vite ports 9896–9897 / 5176.

## Result

The existing request flow now supports product discovery, photo selection, refinement, exact lookup and remembered configuration. Welcome/onboarding is unchanged. Phone shows up to five real product photo cards. Following the user's clarification, **G2 also shows photos in the shortlist itself**: three numbered thumbnails with names and a highlight border, then two on page 2. A press enlarges one before selection. There are text fallbacks throughout.

MICKE 802.130.74 has two offline 35-step cards, 62 distinct guide sets, manual-side configuration pictures, source-page citations, printed parts and phone/G2 crops. Cards stay outside the normal task catalogue. Step N corresponds to manual step N. The builder checks part IDs (including adjacent rotated text fragments) and printed quantities against the official PDF; configuration B's different step-35 quantities are preserved. Step 32 references hinges already fitted in step 31. **Authored MICKE step text still needs a human spot-check against the PDF.** Manufacturer provenance describes the source, not completion of human review.

## Search provider and real retrieval

Provider: **Anthropic `web_search_20250305` on `claude-opus-5-5`, `allowed_domains=["ikea.com"]`, `max_uses=1`**, using the official SDK. [Official tool documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool). Only returned URLs are considered; model answer text is discarded. Each candidate is validated against the official page, with article/canonical identity, actual photo and official manual URL. A manual badge requires a successful PDF HEAD check. No undocumented IKEA API or search-page scraping is used.

Order: exact article/URL → saved verified records → optional asynchronous official-site search. Cached origin is normalized even for records previously learned live. A live search never silently renumbers choices while the wearer is selecting.

**Two live Anthropic search requests were made in this takeover, zero CREAO requests.**

1. “Help me assemble a small IKEA red metal cabinet with two doors”: three real pages validated, but their categories were drawer unit / storage unit / open storage. No candidates were shown. This is an honest no-match, not a claim of success. [Raw proof](evidence/ikea/live-proof.json).
2. “Help me assemble an IKEA black metal glass-door cabinet”: five real candidates, all with photos and successful manual-PDF validation. [Complete state and timing proof](evidence/ikea/live-proof-glass-cabinet.json).

| Product | Article | Official listing |
|---|---|---|
| BLÅLIDEN | 005.205.19 | [US product page](https://www.ikea.com/us/en/p/blaliden-glass-door-cabinet-black-00520519/) |
| BRIMNES | 003.006.64 | [US product page](https://www.ikea.com/us/en/p/brimnes-cabinet-with-doors-glass-black-00300664/) |
| BRIMNES | 104.098.71 | [US product page](https://www.ikea.com/us/en/p/brimnes-glass-door-cabinet-black-10409871/) |
| BLÅLIDEN | 606.166.89 | [Australian product page](https://www.ikea.com/au/en/p/blaliden-glass-door-cabinet-black-60616689/) |
| HAVSTA | 005.292.61 | [US product page](https://www.ikea.com/us/en/p/havsta-glass-door-cabinet-black-00529261/) |

These are candidate listings, not proof that every requested property matches. In particular, material may remain unverified. The provider returned an Australian listing as well as US listings; its actual region and article are retained rather than relabelled as US stock. The 54-record shipped pre-index remains unchanged; these eight learned articles are in the ignored runtime cache.

## Measured latency

| Path | Measurement | Scope |
|---|---|---|
| Cached description → shortlist | **7.98–14.11 ms; median 9.08 ms**, 10 samples | Warm local HTTP POST `/session/goal`; includes persistence and G2 thumbnail composition; live provider disabled. [Samples](evidence/ikea/cache-http-latency.json). |
| Phone first five photos | **385 ms**, one mobile browser run | Form submit through five loaded photo elements, including polling/rendering. Not a distribution or hardware timing. |
| Live black glass-door query | **11.675 s service total** | Search 9.127 s + page/PDF/photo validation 2.529 s, main-loop overhead; 11.725 s observed wall clock. |
| Live red-cabinet no-match | **14.309 s service total** | Search 10.338 s + validation 3.932 s; 14.335 s observed wall clock. |
| Earlier handoff pre-index | **8.0–16.2 s/query**, 11 queries | Earlier operator-reported evidence, not new calls in this takeover. |

No physical BLE or microphone latency was measured. The live measurements are separate from the cached path.

## Verification

| Check | Result |
|---|---|
| Required baseline before changes | 660 core + adapter tests passed |
| `make test` | PASS: core **617**, Pi **77**, knowledge **257**, assets **41**, IKEA adapter/service/manual **76**, G2 **207** |
| `make contracts` (also part of `make test`) | PASS: 9 schemas, 22 Python and 22 TypeScript example validations |
| `make lint-generic` / `make check-secrets` | PASS |
| G2 `npx tsc --noEmit && npx vitest run` | PASS, **207** tests in 15 files (run by `make test`) |
| `node --test web/tests/*.mjs` | PASS, **24** tests |
| New-file Python static checks / `git diff --check` | PASS |
| Official G2 simulator 0.9.5 + actual core | **11/11 PASS**, successful SDK image sends, zero simulator console errors. [Result](evidence/ikea/simulator-result.json). |
| Real Chromium phone UI | PASS: five loaded photos; one-tap product choice; two configuration pictures; step 14; 103430/110126 parts answer; high-resolution closeup; deliberate next → step 15. Normal-flow console: zero errors; requests successful. |
| Mobile UI | PASS at 390×844, no horizontal overflow; all five photos loaded. |
| Browser fallback checks | PASS: no saved match offers article/link; controlled 503 disables selection/input, then reconnect restores interaction. The forced 503 deliberately produces a browser resource error, separate from the clean happy-path capture. |
| Physical G2, BLE image legibility/timing, on-glasses voice | **NOT RUN / NOT VERIFIED** |
| Uncached-manual CREAO branch | **MOCK TESTED ONLY**, disabled by default; no live run authorized |

Service tests cover exact-before-search ordering, variants/ordinals/name selection, refinement, none/more, unavailable/timeout/stale worker completion, persistence across sessions/restart, cached/live labelling, endpoint/asset boundaries, photo shortlist, configuration and assistant context. The full exact demo utterance sequence passes through the real runtime and cached bundle. Only the deliberate manual-step confirmation records HUMAN CONFIRMED; navigation and product selection confirm no assembly steps.

Representative captures:

- [G2 photo shortlist](evidence/ikea/sim-01-photo-shortlist-visible.png)
- [G2 enlarged product](evidence/ikea/sim-03-full-product-photo-visible.png)
- [Phone photo cards, mobile](evidence/ikea/browser-shortlist-mobile.png)
- [Cabinet configuration pictures](evidence/ikea/browser-config.png)
- [Parts answer](evidence/ikea/browser-parts.png)
- [Phone manual closeup](evidence/ikea/browser-step14.png)
- [Normal phone console](evidence/ikea/browser-console.txt), [requests](evidence/ikea/browser-network.txt)

## Demo and limits

[Exact G2 gestures, phone/voice utterances, startup commands and fallbacks](IKEA_DISCOVERY_RUNBOOK.md). The reliable path is cached MICKE with phone text plus gestures; on-glasses microphone capture remains a hardware check. Live product search is implemented and proven separately. Uncached products retain their validated official PDF link, with an honest “offline step guide not prepared” message; fully generalized manual ingestion was cut. No runtime playbook is invented.

Before a public physical assembly demonstration, a human still needs to spot-check the authored MICKE step text against the PDF. Physical hardware checks and further CREAO authorization are the remaining operator actions.
