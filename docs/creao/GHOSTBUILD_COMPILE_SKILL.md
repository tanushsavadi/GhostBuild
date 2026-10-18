# GhostBuild compile skill (research → verified action graph)

One reusable workflow for any build/fix task. Kept in the repository because CREAO's public docs do not expose
programmatic skill registration (saving agents/skills/connectors is documented as browser-app only; the public surface we
verified is the app-scoped runs API used by `knowledge/creao.py`). The same rules are enforced in code by
`knowledge/compile.py`, so a run from either engine is checked the same way.

## Engines

| `GB_RESEARCH_ENGINE` | Path | Verification |
|---|---|---|
| `compile` (default) | `knowledge/find_sources.py` (Anthropic `web_search`, official/specialist pages first, `knowledge/source_trust.json`) → `knowledge/sources.py` (fetch page/PDF → numbered blocks + its own pictures) → `knowledge/compile.py` (structured output) | every step's quote verbatim in its source; routes valid; glasses text fits; one repair round; pictures only from the cited page |
| `creao` | existing CREAO "GhostBuild Intelligence" app run → `knowledge/creao_normalize.py` | quotes kept only when verbatim in supplied source texts; drafts unreviewed |

## Workflow (both engines)

1. Understand the objective and what the person already said (task profile facts with quotes).
2. Identify the product/model only when the procedure depends on it (product discovery adapters, e.g. IKEA).
3. Find trustworthy documentation: manufacturer first, established specialists next; no forums, shops or SEO pages.
4. Extract procedure and diagnostic content as numbered passages; keep the page's own pictures with alt text and nearby text.
5. Compile a graph of steps: `action`, `question` (2–4 choices, each `next`), `outcome`, `stop`; `expected`, `tools`, `risk`,
   `warnings`, `cites[].quote` (verbatim). Diagnosis: the one discriminating question first, safe checks before risky ones,
   never a claimed cause. Unknown answers ("not sure") lead to the source's own identification method.
6. Choose visuals: source photo/diagram → crop + one highlight (vision, cold path only) → GhostBuild path drawing for
   software menus → text fallback. Question steps show comparison pictures whole. AI-generated imagery is never used as
   proof of a specific part, orientation or finished state.
7. Validate and cache: `contracts.models.Card`; cached under `knowledge/compiled/<id>/` (demo) or
   `knowledge/live/compiled_cards/<id>/` (live); third-party pictures stay in gitignored `knowledge/live/`.

## Output contract

`contracts/models.py` `Card` v2 with the optional branching fields (`Step.kind/choices/next/expected/tools/risk`,
`Card.task_kind/review`). Labels: source kind (`MANUFACTURER DOC` / `WEB TUTORIAL`) as provenance, `review` states the
check performed; never `HUMAN-REVIEWED` without a human.
