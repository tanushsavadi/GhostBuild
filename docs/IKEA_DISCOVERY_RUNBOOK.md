# Product-discovery demonstration

Worktree: `.worktrees/final-sprint`, branch `codex/final-sprint`. Everything remains uncommitted. The welcome screen and existing task flow are unchanged.

## Start

Run from this worktree. Keep the working G2 package; this feature adds backend frames and phone UI, with no new SDK calls.

```sh
# Reliable cached demonstration, with paid research disabled.
PYTHONPATH=.:core:pi GB_DISCOVERY=1 GB_DISCOVERY_LIVE=0 GB_LIVE_RESEARCH=0 \
  uv run python -m ghostbuild_core --port 8787
# Existing G2 dev transport, if needed. Use the laptop's reachable LAN address.
BACKEND=http://<laptop-ip>:8787 make g2-dev
```

**05:32 PDT:** the operator backend :8787 was reloaded from this worktree (same command, `--log-dir logs/bench-0445`, `.env`, stdout `/private/tmp/gb-core-8787.log`; backup `logs/backup-bench-0445-0532`). It now serves discovery, full answer pages and the reply-schema fix. Phones that had the page open should hard-reload once to pick up the new CSS/JS. The operator `.env` keeps `GB_CREAO=1` / `GB_LIVE_RESEARCH=1`: an unfamiliar non-product request can start a paid CREAO run. Phone: `http://<laptop-ip>:8787/phone/`. Existing G2 connection settings point to that same backend. This manual demonstration needs no Pi telemetry.

For a fresh rehearsal only, use a fresh `--log-dir /tmp/ghostbuild-discovery-rehearsal-<unique-name>`. This avoids erasing any existing progress. A normal later conversation remembers the chosen cabinet side and correctly skips that question.

`GB_DISCOVERY_LIVE=1` enables the Anthropic provider (backend key required); fresh saved choices that fit appear immediately without forcing a live query. New descriptions search when enabled; “Search the official site again” explicitly refreshes. With `GB_LIVE_RESEARCH=1`, confirming a product that has no prepared guide compiles one from its official manual with the Anthropic compile engine (never CREAO): the glasses show RESEARCHING with progress, then the guide starts. `GB_DISCOVERY_RESEARCH=0` opts out.

## Exact interaction

On physical G2, use phone text plus gestures until the real microphone path has been verified. Voice variants below use the existing consent-gated hold-to-talk path and are **not physically verified**.

1. Any gesture dismisses the unchanged welcome. On the phone, enter **“I have a white IKEA desk with a drawer and cabinet.”** in the existing request box. Voice variant: hold to speak, say it, release. (The vaguer **“building a white IKEA desk”** also works: the shortlist then mixes MICKE, ALEX and IDANÄS, and “It's the MICKE” asks which of the two MICKE sizes — pick photo 1 / say “number one”.)
2. Phone shows up to five photo cards, names, colour/size, article number, verified manual badge, attribute matches/unverified attributes and cached date. G2 shows **three numbered product photographs with names**, with a border around the current choice. It initially highlights MICKE 802.130.74.
3. G2 swipe down moves the highlight through candidates 1, 2, 3, then MORE. Press MORE for photos 4–5; page 2 also offers BACK and NONE OF THESE. Swipe up at the top leaves discovery. The phone's None of these / Refine and number/link field are always available while choosing.
4. Say/type **“It's the MICKE.”** The described drawer/cabinet distinguishes 802.130.74 from the other MICKE variant; genuine name ambiguity asks for a specific article/photo. Gesture alternative: press the first thumbnail to enlarge the photo; press the full photo again to choose it. Swipe down in full-photo focus shows the next candidate; swipe up returns to the photo shortlist. A phone photo card is also one tap to select.
5. On a fresh configuration, phone shows the manual's two cabinet-side pictures. Type/say **“Cabinet on the left.”** Gesture alternative: the CABINET SIDE menu initially highlights CABINET ON THE LEFT; press. Swipe down then press chooses RIGHT. Left/right follows the sitter's side and the manual's pictured arrangement.
6. Step 1 starts immediately with its official diagram. A dim ASK ANYTIME cue sits beside the G2 counter. On the phone, “Ask anytime — I’ll keep your place” focuses the question box; the current step and picture stay beside the conversation. Type in the current-step question box, or say, **“Show me step 14.”** No earlier steps are confirmed by this jump. This is manual page 13 for left / page 28 for right.
7. Ask **“Which fastener do I use?”** The answer is **eight cam locks 103430; do not use crossed-out 110126**. The exact step's PARTS diagram opens. Phone shows the high-resolution official crop; G2 gets the optimized monochrome crop.
8. Ask **“Show me a closer look.”** The parts closeup stays open. G2 shows WHERE by default; press opens PARTS, then press returns to the default step diagram (step 32 also has ADJUST from manual page 40). Swipe up returns to the same step.
9. After actually doing the step, say/type **“Okay, done. What's next?”** or G2 swipe down. Step 14 records **HUMAN CONFIRMED** and moves to step 15. It never says VERIFIED for a manual confirmation. A normal step swipe has the existing 600 ms settle guard.
10. Reconnect or start a later conversation with the same product: article, cabinet side and manual step progress are retained according to the existing session rules. The remembered side prevents a redundant question.

For an explanatory question, ask “How do these round metal locks work, and how far do I turn them?”: glasses show THINKING, then the **full** answer as pages (`ANSWER 1/3 · PRESS: BACK`). Swipe down/up reads the next/previous page (never confirms the step, stops at the last page); the answer stays open until you return. Press, the phone's “Back to my step”, or saying/typing **“take me back to my step”** returns to the same step and picture. Pressing during THINKING also returns, and the late answer then appears on the phone only. After returning, a swipe down confirms the step as usual. The phone mirror shows the same pages with Previous/Next answer page buttons. Saved grounded answers can respond immediately and are labelled saved. `GB_ANSWER_PAGES=0` restores the old short timed cue.

Double press goes Home from a task and is the system exit on the root screen; discovery does not intercept it. G2 has no camera or speaker. Optional spoken output goes through the phone/earbuds.

## Fallbacks

- Exact fallback: enter `802.130.74` or `https://www.ikea.com/us/en/p/micke-desk-white-80213074/`, confirm the product once, choose a cabinet side if not remembered.
- No match / no internet: use the article/link field. The MICKE pre-index, photographs and manual bundle work offline; do not call that a live search.
- An uncached manual: the confirmed product and official PDF remain available on the phone, with a plain notice that its offline step guide has not been prepared. No new runtime playbook is fabricated.
- A failed image: text cue remains available. Physical image legibility, BLE timing, touch behaviour and microphone capture still require the operator's hardware check.

## Reproduce simulator verification

Use isolated backend/log directory, voice and paid research disabled:

```sh
PYTHONPATH=.:core:pi GB_ASSISTANT=0 GB_VOICE=0 GB_DISCOVERY_LIVE=0 GB_LIVE_RESEARCH=0 \
  uv run python -m ghostbuild_core --port 8797 --log-dir /tmp/ghostbuild-g2-product-check
# g2/
npx vite --host 127.0.0.1 --port 5176 --strictPort
npx evenhub-simulator 'http://127.0.0.1:5176/?surface=simulator&backend=http://127.0.0.1:8797' --automation-port 9897
```

From the repository root, run `node integrations/ikea/tools/simulator_check.mjs` after the simulator is ready. `CORE`, `SIM` and `OUT` can override its isolated defaults.

The latest automatic-diagram/ASK ANYTIME 11-check capture is in `docs/evidence/fluid/simulator-result.json`. The earlier photo-shortlist capture remains in `docs/evidence/ikea/simulator-result.json`. `sim-*-visible.png` composites the simulator's alpha channel onto black for inspection; original RGBA captures are alongside them. These prove the simulator/actual-core path, not physical hardware.

**Before presenting authored assembly instructions, a human still needs to spot-check the MICKE step text against the official PDF.**
