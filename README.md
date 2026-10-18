# Open Palm for Even G2

**Say what you want to tell a Deaf person; the glasses show you how to sign it, one sign at a time.**

You can't hold a phone and sign at the same time: signing needs both hands, and eye contact matters. Open Palm puts the instructions in your field of view on Even Realities G2 glasses, so your hands stay free and your eyes stay on the person you're talking to.

> Branch `test_sim`. This repository started as GhostBuild; the other files under `docs/` describe that earlier project and are historical. The plan for this project is [`docs/OPEN_PALM_PLAN.md`](docs/OPEN_PALM_PLAN.md).

---

## What it does

1. You **long-press, choose *Speak a sentence*, say it and tap** (or type it on the phone): *"What's your name?"*
2. It becomes ASL signs in ASL order: **YOUR → NAME → WHAT**, with a small face showing the expression to hold (*brows down: it's a what-question*).
3. The glasses show one card per sign:

```
┌──────────────────────────────────────────────────────────┐
│   ┌──────────┐   WHAT   3/3                               │
│   │  (open   │   Both hands open, palms facing up         │
│   │   hand   │   Shake slightly side to side              │
│   │  drawing)│   FACE: Brows down (what-question)         │
│   └──────────┘   UNCHECKED · ▼ HOW                        │
│                  LAST · TAP TO REPEAT                     │
└──────────────────────────────────────────────────────────┘
```

| On the glasses | Does |
|---|---|
| (nothing) | **Hands-free:** each sign stays 2.5–10 s (simple signs and letters shorter, two-handed or complex ones longer), five dots ●●●○○ show the time left, then the next sign comes up. After the last sign the lens clears 5 s later. |
| Tap | Pause / resume (while listening: done speaking; in the menu: choose; in `?review=top`: next sign) |
| Swipe down | Full step-by-step description of this sign, in pages; the timer waits while you read (in the menu: move down) |
| Swipe up | Back to the card (in the menu: move up) |
| Long-press | Open / close the menu: **Speak a sentence**, **Prepare a conversation**, **Prepared sentences**, **Practice signs**, Close |
| Double-tap | Exit |

Each card is kept minimal: the hand picture, the sign's name, two how-to lines, and a small **face** at the top right that shows the ASL grammar (brows down for what/where/who questions, brows up for yes/no questions, arrows for a "no" head shake) and the sentence's emotion (smile, frown, surprise). Sign status, progress and sources are on the phone page.

The phone page shows the same card, the full description, and a link to a reference video of the sign.

### What it covers

- **About 2,300 English words** with an ASL sign, from the ASL-LEX 2.0 database.
- **About 22 everyday sentences** signed as real ASL sentences, not word by word: *How are you? · What did you say? · Where is the bathroom? · I don't understand · Can you repeat that? · Please sign slower · Are you deaf?* and more.
- **Fingerspelling A–Z** for names and words without a sign (*"My name is Abdul"* → MY · NAME · A-B-D-U-L).
- **ASL grammar basics:** words ASL drops (*is, are, the, do*) are skipped, contractions are understood (*can't* → CANNOT), and *I* is signed ME.

### What it is not

It is a phrasebook coach for a hearing person's first conversations, not an interpreter. ASL is its own language with its own grammar; this shows individual signs in a simplified order. Nobody on the team is Deaf, and no Deaf signer has reviewed the cards yet; every card says so (see [Labels](#labels-on-the-cards)).

---

## Quick start

**Needs:** Node 20+, [`uv`](https://docs.astral.sh/uv/) (for the laptop server and the data tools), the Even Realities app on a phone, and G2 glasses (or just the simulator).

**Get the code** (Open Palm lives on the `test_sim` branch):

```bash
git clone https://github.com/tanushsavadi/GhostBuild.git
cd GhostBuild
git checkout test_sim
```

**Keys** (only for speech): create a file named `.env` in the repo root with your own key. It is git-ignored; never commit it.

```
ELEVENLABS_API_KEY=your-elevenlabs-key
```

**Run the app** (first terminal):

```bash
cd g2
npm install
npm rebuild @evenrealities/evenhub-simulator   # only if "npm run simulate" says not found
npm run dev                                    # leave running
```

**Laptop server** (needed for speech and AI word order; repo root, second terminal). For AI word order also install [Ollama](https://ollama.com) and run `ollama pull qwen3.5:4b-q4_K_M` once:

```bash
uv run tools/open_palm_server.py
```

**Simulator** (another terminal, in `g2/`):

```bash
npm run simulate
```

**Real glasses:**

1. Phone and laptop on the same Wi-Fi (or the laptop on the phone's hotspot).
2. In `g2/`: `npx evenhub qr --url http://<laptop-ip>:5173` (find the IP with `ipconfig` / `ifconfig`).
3. Scan the QR code in the Even Realities app. Keep the phone screen on.

**Windows:** the phone can only reach the dev server if inbound port 5173 is allowed. In an administrator PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Open Palm dev 5173" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any
```

Test it by opening `http://<laptop-ip>:5173` in the phone's browser first.

**If the phone needs https, or can't reach the laptop** (venue Wi-Fi often blocks devices from talking to each other), use a free Cloudflare tunnel instead. No account, no firewall rule. Download `cloudflared-windows-amd64.exe` from [Cloudflare's releases](https://github.com/cloudflare/cloudflared/releases/latest) (saved here as `tmp/bin/cloudflared.exe`, git-ignored), then, with `npm run dev` running:

```bash
tmp/bin/cloudflared.exe tunnel --no-autoupdate --url http://localhost:5173
```

It prints an address like `https://some-words.trycloudflare.com`; use that in `npx evenhub qr --url <address>`. The address changes every time the tunnel starts, and anyone who has it can use the app (and its speech credit) while it runs, so don't post it publicly.

**Useful URLs**

| URL | Does |
|---|---|
| `/` | Open Palm |
| `/?phrase=How%20are%20you` | Starts that sentence on load (demos, testing) |
| `/?style=thin` | Handshape drawing style: `bold` (default), `thin`, `bold96` |
| `/probe.html` | Handshape legibility test: shows each drawing in 3 styles and the image send time |
| `/review.html` | Review page for the 100 most-used signs (in a browser) |
| `/?review=top` | Step through the 100 most-used signs on the glasses |

## Checking the signs

Nobody has checked the cards against real signing yet. To check the most-used ones:

1. Open `http://localhost:5173/review.html` in a browser (or the laptop's IP on a phone). It lists the 100 most-used signs (ASL-LEX frequency ratings), or switch the list to the signs used in the sentence list.
2. For each sign: open **▶ Reference video**, compare it with the picture and the two lines, and press **✓ Right** or **✗ Wrong** (with a note on what's wrong). Marks are saved in that browser; the filter shows what's left.
3. Press **Export** and paste the result into `g2/src/checked.json`. Signs marked right then show **REF-CHECKED** on the glasses. Fix the wrong ones in `tools/howto.json` and run `uv run tools/build_deck.py`.
4. To see how the cards look on the lens, open `/?review=top` on the glasses and tap through.

Common problem to look for: the full description (from Wiktionary) sometimes describes a different variant of the sign than the picture and the two lines (e.g. EAT one-handed vs two-handed).

---

## How it works

```
 phone (Even app WebView, g2/)                               glasses
 ┌───────────────────────────────────────────────┐
 │ sentence ──► matcher.ts ──► cards ──► main.ts ─┼── BLE ──►  handshape image + text
 │               │                               │          ◄── tap / swipe
 │   phrases.json  (sentences in ASL order)      │
 │   deck.json     (hand-written demo signs)     │
 │   asllex.json   (2,300 words → signs)         │
 │   wiktionary.json (full descriptions)         │
 └───────────────────────────────────────────────┘
```

Typed sentences are handled entirely on the phone. Speech goes glasses mic → phone → laptop server (`tools/open_palm_server.py`, through the Vite `/api` proxy, so only port 5173 is needed) → ElevenLabs speech-to-text (`scribe_v2`, raw 16 kHz PCM) → text → the same matcher. API keys stay in `.env` on the laptop; audio is not stored.

`g2/src/matcher.ts` turns a sentence into cards, in this order of preference:

1. **Known sentence** (`phrases.json`): ASL order plus a face cue.
   - **Any other sentence of 2+ words** goes to the laptop's local AI (`POST /api/translate`, Ollama `qwen3.5:4b`, about 1 s once loaded). It returns only sign names, their ASL order and a face cue; a cleanup step moves question words last and fixes known slips; the cards are then built from our data and marked **AI ORDER**. If the AI doesn't answer within 8 s, the sentence falls back to the steps below. `?ai=off` turns it off.
2. **Multi-word sign** (*thank you*, *I love you*, *sign language*).
3. **Single word**: hand-written demo sign (`deck.json`) first, then ASL-LEX (`asllex.json`); plurals and *-ing*/*-ed* forms are handled.
4. **Anything else is fingerspelled.** It never makes up a sign.

**Conversation prep (CREAO).** On the phone page, describe an upcoming conversation ("Ordering coffee from a Deaf barista") and press *Prepare with CREAO*. A CREAO agent plans the 6 sentences you'll most likely need, in ASL order with face cues, plus up to 4 signs to practise (about 40 s). They become one-tap buttons, and saying any of them later shows its cards instantly. With *Remember my sentences* on (off by default), the laptop keeps the sentences you sign and the signs you opened HOW for, as text, and *Use what I signed before* lets CREAO reuse them. Needs `CREAO_API_KEY` and `CREAO_PREP_APP_ID` in `.env`; the agent's instructions are in `tools/creao_prep_prompt.md`.

`g2/src/main.ts` draws the cards: one image container (144×144 handshape, 4-bit green) and one text container, one bridge call at a time, and the image is only resent when the handshape changes.

### Where the content comes from

| Content | Source | Licence | Built by |
|---|---|---|---|
| Which sign a word uses; handshape, location and movement coding; reference videos (linked, not copied) | [ASL-LEX 2.0](https://asl-lex.org) | CC BY-NC 4.0 | `uv run tools/build_deck.py` → `g2/src/asllex.json` |
| Handshape drawings (58) | ASL-LEX visualization, served by aslcdi.website | CC BY-NC 4.0 | `uv run tools/build_handshapes.py --all` → `g2/public/handshapes/` |
| Letters M and N drawings | wpclipart.com via Wikimedia Commons | Public domain | same script |
| Full step-by-step descriptions (swipe down), rewritten in plain words | [Wiktionary](https://en.wiktionary.org/wiki/Category:American_Sign_Language_lemmas) ASL entries | CC BY-SA 4.0 | `uv run tools/fetch_wiktionary.py` → `g2/src/wiktionary.json` |
| Short two-line instructions for ~100 common signs; letter tips; sentence orders and face cues | Written by AI (Claude) in this project, from ASL-LEX's coding | This repo | `tools/howto.json`, `g2/src/deck.json`, `g2/src/phrases.json` |
| Two-line instructions for the other ~2,200 signs | Generated from ASL-LEX coding by a template | (derived from ASL-LEX) | `tools/build_deck.py` |

The ASL-LEX data is for non-commercial use. Wiktionary text must be credited and anything adapted from it shared under CC BY-SA. The phone page shows these credits. Lifeprint (ASL University) is **not** used: its terms forbid use in apps.

### Labels on the cards

| Label | Means |
|---|---|
| `REF-CHECKED` | A person compared the card with the sign's reference video |
| `UNCHECKED` | Hand-written by AI, not yet compared with a video |
| `AUTO · UNCHECKED` | Generated from ASL-LEX coding; may be vague, check the video |
| `FINGERSPELL · UNCHECKED` | Letter of a fingerspelled word |
| `▼ HOW` | A full Wiktionary description is available (swipe down) |

To mark a sign checked: watch its reference video (linked on the phone page), fix the two lines if needed, and set `"status": "REF-CHECKED"` in `g2/src/deck.json` (move it there from `tools/howto.json` if needed).

---

## Editing the content

| To | Edit | Then |
|---|---|---|
| Fix or add a common sign's two lines | `tools/howto.json` (≤ 36 characters per line; write "palm facing up", not "palm up") | `uv run tools/build_deck.py` |
| Add a sentence signed in ASL order | `g2/src/phrases.json`: English variants, signs in order, face cue | nothing (the dev server reloads) |
| Change a demo sign or a letter tip | `g2/src/deck.json` | nothing |
| Refresh Wiktionary descriptions | — | `uv run tools/fetch_wiktionary.py` (a few batched requests) |

Raw downloads are cached in `tmp/` (git-ignored).

## Project layout

```
g2/                     Even G2 plugin (Vite + TypeScript, SDK 0.0.16)
  index.html            phone page (type a sentence, see the card and credits)
  src/main.ts           glasses UI: cards, paging, gestures
  src/matcher.ts        sentence -> cards (pure, no network)
  src/phrases.json      sentences in ASL order + face cues
  src/deck.json         hand-written demo signs, letters, skipped words, credits
  src/asllex.json       generated: ~2,300 words -> ASL-LEX signs
  src/wiktionary.json   generated: full sign descriptions
  public/handshapes/    generated: 4-bit 144x144 handshape PNGs
  probe.html, src/probe.ts   handshape legibility test
  review.html, src/review.ts review page for the most-used signs
  src/top.json          generated: the 100 most-used signs
  src/checked.json      signs a person marked right (REF-CHECKED)
tools/                  data builders (run with uv)
docs/OPEN_PALM_PLAN.md plan, steps and decisions
CLAUDE.md               rules for AI coding agents on this branch
```

## Status and limits

- Built and checked in the Even simulator. **Not yet verified on the physical glasses:** handshape legibility, image send time and gesture mapping need the `/probe.html` test and a real run.
- No AI runs in the app yet; the AI part (Claude turning any sentence into ASL order, and speech input) is the next step. The version before it is tagged `pre-ai`.
- Facial grammar is only a text cue; the cards show the dominant hand's shape only, and two-handed signs describe the other hand in text.
- About 2,200 rarer signs only have template instructions; some Wiktionary descriptions may describe a different variant than the ASL-LEX drawing.
- Even Hub app: `Open Palm` (`com.openpalm.openpalm`), not yet uploaded.
