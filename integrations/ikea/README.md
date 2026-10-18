# IKEA product discovery

This adapter adds product discovery to GhostBuild's existing request → guide flow. It does not add a mode or change welcome/onboarding. Core knows only the generic `ProductSource` protocol; retailer URLs, article rules, pre-index data and manual authoring stay here and in `knowledge/products/ikea/`.

## Provider and lookup order

1. Exact article number or official product URL: saved fresh record first, otherwise official-page lookup; one confirmation.
2. Deterministic ranking over verified cached product records. The 54-product pre-index includes local official photographs. Learned records are stored separately in the ignored runtime cache.
3. Fresh saved matches that cover the description return without an automatic live search. A genuinely new description or explicit refresh uses optional asynchronous official-site search: **Anthropic `web_search_20250305`, `claude-opus-5-5`, `allowed_domains=["ikea.com"]`, `max_uses=1`**, through the official Python SDK. The model proposes URLs only. Its answer text is discarded.

See [Anthropic's documented tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool). No undocumented search API or `ikea.com/search` scraping is used. Search does not use CREAO.

Every candidate must validate against the official product page: matching article identity and canonical URL, name, photo, official URL. An assembly PDF counts as verified only after HTTP 200 with a PDF content type. Image captions from related products cannot supply this product's features. Missing attributes remain unverified; scores order results and are never displayed as confidence. Search can return other markets; the official URL and article identify the actual listing, so check region before ordering.

Cached records are always labelled cached with the page-read date, including records originally learned through a live search. Live results never replace the current numbered list while the wearer is selecting; Show more can expose the merged pool. Unavailable, timeout and no-match states offer the number/link fallback. Network workers never write HUD frames.

## Configuration

From the repository root:

```sh
PYTHONPATH=.:core:pi GB_DISCOVERY=1 GB_DISCOVERY_LIVE=0 \
  uv run python -m ghostbuild_core --port 8787
```

- `GB_DISCOVERY`: defaults on when the pre-index exists; `0` disables it.
- `GB_DISCOVERY_LIVE`: defaults `1`; `0` keeps the demonstration offline. Live search needs backend `ANTHROPIC_API_KEY`; no credential belongs in the browser or G2 package.
- `GB_DISCOVERY_RESEARCH`: defaults to the value of `GB_LIVE_RESEARCH`. When a confirmed product has no prepared guide, the compile engine (Anthropic) builds one from that product's validated manual and product page only (no web search); the glasses show the research progress screen and the guide starts itself, labelled AI-compiled and not human-reviewed. A second selection of the same product reuses the compiled guide. Set `0` to opt out. It never starts a CREAO run.
- `GB_DISCOVERY_MODEL` / `GB_DISCOVERY_SEARCH_TOOL` override the documented search defaults for explicit experiments; the verified combination is the one above.

`GB_SMART_CACHE=0` disables the app-wide reuse cache; otherwise completed generic guides, successful queries and standalone grounded answers persist beside session logs. See [reuse and conversation details](../../docs/FLUID_ASSISTANT_REPORT.md). `GB_STEP_IMAGES=0` disables automatic MICKE step pictures; manual progress rules stay the same.

`discovery.json` next to `sessions.json` stores per-session state and remembered configuration by source/article. Product cards resolve on reconnect/restart but stay out of the general task catalogue. Manual progress keeps the existing HUMAN CONFIRMED / measured-evidence rules.

## Rebuild and re-index

```sh
# Existing authored steps, official PDF crops, two configurations; no model call.
PYTHONPATH=.:core uv run python -m integrations.ikea.tools.build_manual
# Or use an existing source PDF; cross-check failures stop the build.
PYTHONPATH=.:core uv run python -m integrations.ikea.tools.build_manual --pdf /path/to/manual.pdf

# Explicit paid provider requests. Run only for chosen new queries.
PYTHONPATH=.:core uv run python -m integrations.ikea.tools.preindex "white computer desk"
```

The builder caches the original PDF under the system temporary directory, outside git. It emits 35 steps per configuration, 62 distinct guide sets, configuration pictures, citations and `bundle.json`. Part IDs are checked against PDF text, including adjacent rotated digit fragments; printed quantities are checked in the step band. Step 32 explicitly reuses the hinges from step 31. A human still needs to spot-check authored verbs/text against the PDF. Configuration B's printed step-35 quantities differ from A and are preserved.

All display images are 288×144, grayscale levels in multiples of 17; phone crops preserve source detail. The G2 shortlist composes three real product photos and numbered names per page (then two on page 2), with a selection border; press enlarges one before confirmation. Each MICKE step also displays its WHERE diagram automatically; press opens PARTS and the next press returns. The dim ASK ANYTIME hint and phone invitation make mid-step questions discoverable. Text remains the fallback. The existing G2 renderer serializes SDK image sends; no SDK or package changes were needed.

## Evidence and verification

See [the demo runbook](../../docs/IKEA_DISCOVERY_RUNBOOK.md) and [verification report](../../docs/IKEA_DISCOVERY_REPORT.md). The unfamiliar glass-cabinet proof contains exact official listings, photos, manual URLs and timings. There were **two** live search calls in this takeover; **zero CREAO calls**. The red-cabinet query returned unrelated categories, which the ranker rejected honestly.

```sh
make test
node --test web/tests/*.mjs
```

`make test` now includes this adapter's offline tests, the contracts check, generic lint, secret scan and G2 TypeScript/Vitest checks. Do not claim the physical glasses or microphone work from simulator evidence.

## Rights

IKEA owns the product photographs and manual pages. This demo caches and crops them with links and manufacturer attribution. Check rights before wider distribution. These are reference images, never a live view of the wearer's surroundings.
