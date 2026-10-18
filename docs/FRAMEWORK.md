# GhostBuild framework: trusted sources → verified action graph → one guidance runtime

Built Sun 2026-10-18 (05:45–06:15 PDT). Evidence: `docs/evidence/framework/`, `docs/evidence/adaptive/`.

```
 Official pages / PDFs / product records          COLD PATH (once per task, cached)
   Apple Support · Park Tool · Prusa · Bosch · IKEA manuals · any manufacturer
        │  knowledge/find_sources.py   web_search, manufacturer & specialists first (knowledge/source_trust.json)
        │  knowledge/sources.py        fetch → numbered text blocks + the page's own pictures (cached)
        │  integrations/ikea/…         product identity + official manual (photo shortlist)
        ▼
 knowledge/compile.py  — Claude structured output → VERIFIED ACTION GRAPH
        every step quotes its source verbatim (checked in code) · routes valid · glasses text fits
        one repair round · unverifiable steps dropped or the guide is refused · pictures only from the cited page
        visuals: source photo → AI-vision crop + one highlight · comparison pictures whole · menu-path drawing · text
        ▼
 contracts.models.Card v2 (+ optional kind/choices/next/expected/tools/risk, task_kind, review)
        cached: knowledge/compiled/<id>/card.json (demos) · knowledge/live/compiled_cards/<id>/ (live) · pictures gitignored
        ▼                                                  HOT PATH (no model on navigation or pictures)
 core PlaybookEngine — one runtime for assembly, repair and diagnosis
        question steps = G2 menu (swipe/press), phone buttons or plain speech (deterministic match)
        observations recorded as HUMAN CONFIRMED reports · back follows the route taken · hazard steps confirm twice
        outcome/stop end branches honestly · interview answers pre-answer a guide's opening question
        ▼
 assistant (adaptive interview + grounded answers, paged on G2) · G2 plugin · phone companion
```

Nothing above knows about Macs, bikes, printers or desks. Those live only in card data and source adapters.

## Engines for an uncached request
`GB_LIVE_RESEARCH=1` plus `GB_RESEARCH_ENGINE=compile` (default) or `creao` (the existing CREAO app run). CREAO's public API is
the app-scoped runs surface. Skill/agent registration is browser-only per its docs, so the reusable skill definition lives in
`docs/creao/GHOSTBUILD_COMPILE_SKILL.md`.

## Measured
| What | Result |
|---|---|
| Uncached live task "clean the filter on my Bosch dishwasher" through the real Runtime | **32.8 s** request → guide on glasses; 3 official bosch-home.com pages; 10 steps incl. a question; 2 Anthropic requests (search + compile, 1 round); `docs/evidence/adaptive/live-uncached-compile.json` |
| Cached demo compiles (build time) | Mac 6 Apple pages 84.9 s / bike 4 Park Tool pages 118 s / Prusa 3 Prusa pages 112 s; all 0 validation errors |
| Hot path (local HTTP, median of 10) | state 0.98 ms · catalog 2.19 ms · G2 picture 1.29 ms · phone picture 1.28 ms · deterministic ask 1.55 ms |
| Live assistant on the Mac guide | intake 3.3 s → guide started; spoken branch answer 0.01 s (deterministic); expected-state answer 2.9 s (3 G2 pages) |

## Cached demos (same runtime as IKEA)
| Guide | Sources | Shape |
|---|---|---|
| `mac_display_colors` (diagnosis) | 6 Apple Support pages | which display? → colour filters / profile / reconnect + cable → fixed? → safe mode → result? → Apple Diagnostics → STOP contact Apple (hazard). Never claims a cause. |
| `bike_flat_tire` (repair) | 4 Park Tool pages | tube or tubeless? (NOT SURE → find "tubeless ready" marking → ask again; TUBELESS → STOP, plugs not patches) → valve type → deflate → remove → find hole → inspect tire → patch or new → refit → inflate/check line. 11 real step photos. |
| `prusa_mk4_not_extruding` (diagnosis) | 3 Prusa KB pages | symptom (loud click / light click / gaps / nothing) → branches; hot-nozzle steps are hazard (double confirm); STOP when the nozzle needs replacing. |
| IKEA MICKE (assembly) | official manual PDF + product records | unchanged |

Reviews applied (`knowledge/review_compiled.py`, recorded in each card's `review`): the valve comparison picture is shown whole, Mac software
steps use path drawings, a CORE One photo was removed from the MK4 guide, and titles were shortened for the glasses.
**Human review of these guides is still pending.**

## Operator test (≈5 min, phone + G2 on :8787)
1. Hard-reload `http://<laptop-ip>:8787/phone/`. Say/type **"My MacBook screen suddenly turned green."** The assistant starts the Mac guide (or asks one question). G2: any tap shows **WHICH SCREEN IS WRONG?** as a menu. Swipe to EXTERNAL DISPLAY, press. Or say "only my external monitor, the laptop screen is fine".
2. On the step, ask **"what should it look like when this works?"**: the full answer pages on G2, press to return. Swipe down confirms (HUMAN CONFIRMED).
3. **Change task**: "I have a flat tire on my bicycle". At TUBE OR TUBELESS? pick NOT SURE → the Park Tool marking photo → back to the question → INNER TUBE → valve photos → … Press shows the step's picture.
4. Optional: "My Prusa MK4 isn't extruding" → LOUD CLICKING → hot-nozzle step asks you to swipe twice.
5. Optional live (paid, ~35 s): an unfamiliar safe task such as "descale my Breville espresso machine" → RESEARCHING → COMPILED FROM SOURCES.
6. IKEA: "building a white IKEA desk" still opens the photo shortlist and MICKE manual.

## Five-minute judge script
- **0:00 Hook (20 s)**: "Manuals don't know where you are. GhostBuild turns trusted documentation into a procedure you can execute, one step and one picture at a time, hands-free."
- **0:20 Act I, Assemble (60 s)**: "I've got a white IKEA desk" → real photo shortlist → MICKE → cabinet side → step 14 → "which screw?" → official crop with part numbers.
- **1:20 Act II, Diagnose (70 s)**: "My Mac screen has gone green." One question as a G2 menu → "only my external monitor" → external branch. "What should it look like?" → full answer, labelled general knowledge. Point at the phone: what you reported (HUMAN CONFIRMED), the Apple quote under every step, STOP before any repair.
- **2:30 Act III, Repair (60 s)**: "Help me fix a flat bicycle tire." "Not sure" → how to tell → valve photos from Park Tool → patch → inflate check. Note the honest tubeless stop.
- **3:30 Act IV, Reveal the engine (60 s)**: show this diagram. Then live: an unfamiliar task → ~35 s later a cited, branching guide on the glasses, from the manufacturer's own pages. "Different sources, one verified compiler, one adaptive runtime, one G2 experience."
- **4:30 Close (30 s)**: honesty. The glasses have no camera, so progress is the wearer's confirmation unless a sensor measures it. Every step cites its source, and nothing is called human-reviewed until a human reviews it.

## Limits (truthful)
- Physical G2 legibility/BLE/microphone not verified by Claude; simulator and browser only.
- Compiled guides are AI-compiled with code-checked quotes, **not human-reviewed**. Third-party pictures are cached locally (gitignored) and not redistributed.
- AI image generation is not used: there is no verified CREAO API path for it, and generated images would not be valid proof of parts, orientation or finished states.
- CREAO skill registration is not available via API, and no new CREAO run was made in this sprint.
- Live compile quality depends on what the found pages contain. It refuses (NO RELIABLE GUIDE) instead of guessing.
