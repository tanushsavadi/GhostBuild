# Open Palm

**Say what you want to tell a Deaf person; Even Realities G2 glasses show you how to sign it, one sign at a time, hands-free.**

Signing needs both hands and eye contact, so a phone is in the way. Open Palm puts each sign in your field of view: the handshape, two short how-to lines, and a small face showing the expression to hold.

It is a phrasebook coach for a hearing beginner, not an interpreter. Nobody on the team is Deaf; cards are checked against reference videos, not by a Deaf signer.

## Using it

On the glasses, each card shows the **hand picture**, the **sign's name**, **two how-to lines**, five **time dots**, and a small **face** (top right):

- **Brows down:** what / where / who question.
- **Brows up:** yes/no question.
- **Arrows:** head shake ("not").
- **Mouth:** the sentence's emotion (smile, frown, surprise).

Cards move on by themselves: 2.5 s for a fingerspelled letter, up to 10 s for a two-handed or complex sign.

| Gesture | Does |
|---|---|
| Tap | Pause / resume. While listening: done speaking. In the menu: choose |
| Swipe down / up | Full step-by-step description of the sign (pauses the card) / back. In the menu: move |
| Long-press | Menu: **Speak a sentence**, **Prepare a conversation**, **Prepared sentences**, **Practice signs**, Close |
| Double-tap | Exit |

The phone page (in the Even app) lets you:
- type a sentence or hold to talk;
- prepare a conversation;
- see each card with its sources, its check status and the reference video.

## Run it

**Needs:**
- Node 20+ and [uv](https://docs.astral.sh/uv/);
- [Ollama](https://ollama.com) with `ollama pull qwen3.5:4b-q4_K_M`;
- the Even Realities app and G2 glasses, or the simulator.

```bash
git clone https://github.com/tanushsavadi/GhostBuild.git && cd GhostBuild && git checkout test_sim
```

Create `.env` in the repo root (git-ignored; see `.env.example`). Typing works without any of these keys:

```
ELEVENLABS_API_KEY=...   # speech to text
CREAO_API_KEY=...        # conversation prep
CREAO_PREP_APP_ID=...    # the prep agent (instructions: tools/creao_prep_prompt.md)
```

Start the three terminals:

```bash
cd g2 && npm install && npm run dev        # 1. the app (port 5173)
uv run tools/open_palm_server.py           # 2. laptop server: speech, AI order, prep (repo root)
npm run simulate                           # 3. simulator (in g2/); if "not found": npm rebuild @evenrealities/evenhub-simulator
```

**On the glasses:** the phone must reach the laptop. The reliable way is an https tunnel, which needs no firewall rule and works on any Wi-Fi:

```bash
tmp/bin/cloudflared.exe tunnel --no-autoupdate --url http://localhost:5173   # cloudflared from github.com/cloudflare/cloudflared/releases
npx evenhub qr --url https://<printed-name>.trycloudflare.com               # in g2/; scan with the Even app
```

Keep the phone screen on. The tunnel address changes on every start, and anyone with it can use the app and its API credit, so don't share it publicly.

Same Wi-Fi without a tunnel also works: run `npx evenhub qr --url http://<laptop-ip>:5173`. On Windows, first allow the port in an administrator PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Open Palm dev 5173" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any
```

| URL option | Does |
|---|---|
| `?phrase=How%20are%20you` | Start a sentence on load (demos) |
| `?menu=1` | Open the menu on load |
| `?ai=off` | No AI word order (word by word) |
| `?style=thin` | Hand drawing style: `bold` (default), `thin`, `bold96` |
| `?review=top` | Tap through the 100 most-used signs |
| `/review.html` | Check signs against their videos (browser) |
| `/probe.html` | Hand picture legibility and send-time test |

## How it works

```
glasses ◄─BLE─► phone: Even app WebView (g2/)                       laptop (tools/open_palm_server.py)
                 sentence ─► matcher.ts ─► cards ─► main.ts         /api/stt       → ElevenLabs scribe_v2
                     │  phrases.json, deck.json, asllex.json,       /api/translate → Ollama qwen3.5:4b
                     │  wiktionary.json (all on the phone)          /api/prepare   → CREAO prep agent
                     └─ via the Vite /api proxy (one port) ─────►   /api/history   (opt-in, text only)
```

A sentence is turned into cards in this order:
1. **Prepared** by CREAO: instant.
2. **Covered by reviewed content** (hand-written ASL sentences, demo signs, fingerspelling): instant, no AI.
3. **Anything else of 2+ words:** the local model picks the sign order, face and emotion (about 1 s). The server cleans its slips: question word last, NOT-X split, made-up compounds split, question brows only on real questions.
4. **Word by word** if the AI is off, slow (over 8 s) or down.

**The AI only chooses which signs, in what order, and the face.** Every picture and instruction comes from the data below, and a word without a sign is fingerspelled, never invented.

- **Speech:** menu → Speak, or the phone's Hold to talk. The glasses-mic audio (16 kHz PCM) goes once to ElevenLabs and is never stored.
- **Conversation prep:** describe the situation, by voice or on the phone. The CREAO agent plans 6 likely sentences in ASL order with faces, plus up to 4 signs to practise (about 40 s), and saves them as the phrasebook.
- **Memory (opt-in):** with *Remember my sentences* on, the laptop also keeps the sentences you signed and the signs you opened HOW for (`tmp/open_palm/`), and prep can use them.

## Content and licences

| Content | Source | Licence | Built by |
|---|---|---|---|
| Word → sign mapping, handshape/location/movement coding, reference videos (linked only) | [ASL-LEX 2.0](https://asl-lex.org) | CC BY-NC 4.0 | `uv run tools/build_deck.py` → `g2/src/asllex.json`, `top.json` |
| Hand drawings (58) | ASL-LEX visualization (aslcdi.website) | CC BY-NC 4.0 | `uv run tools/build_handshapes.py --all` |
| M and N drawings | wpclipart.com (Wikimedia Commons) | Public domain | same |
| Full descriptions (swipe down), reworded in plain English | [Wiktionary](https://en.wiktionary.org/wiki/Category:American_Sign_Language_lemmas) | CC BY-SA 4.0 | `uv run tools/fetch_wiktionary.py` |
| Two-line instructions for ~150 common signs, sentence orders, letter tips | Written by AI (Claude) from ASL-LEX coding | this repo | `tools/howto.json`, `g2/src/deck.json`, `g2/src/phrases.json` |
| Faces | drawn by code | this repo | `uv run tools/build_faces.py` |

ASL-LEX is for non-commercial use. Wiktionary text is credited per sign and adaptations stay CC BY-SA. Lifeprint is not used: its terms forbid apps.

**Check status** (shown on the phone):

| Status | Meaning |
|---|---|
| REF-CHECKED | A person compared it with the video |
| UNCHECKED | Hand-written, not compared yet |
| AUTO · UNCHECKED | Template text from ASL-LEX coding |
| FINGERSPELL | A letter |
| AI ORDER | The sign order came from the AI |

**Checking signs:**
1. Open `/review.html` and compare each sign with its video. Mark it right or wrong.
2. Press **Export**, then paste the result into `g2/src/checked.json`.
3. Fix the wrong ones in `tools/howto.json`, then run `uv run tools/build_deck.py`.

So far, 50 signs are confirmed (46 of the top 100), and 18 were fixed and need a re-check.

## Editing

| To | Edit | Then |
|---|---|---|
| Fix a sign's two lines or its drawing | `tools/howto.json` (≤ 36 chars a line; "palm facing up", not "palm up"; optional 3rd item = drawing id) | `uv run tools/build_deck.py` |
| Map a word to another sign | `ALIASES` in `tools/build_deck.py` | same |
| Add an ASL sentence | `g2/src/phrases.json` | nothing |
| Fingerspell a word letter by letter | `"spell"` in `g2/src/deck.json` | nothing |
| Compare local models | — | `uv run tools/bench_llm.py <ollama models>` |

## Layout

```
g2/                       Even G2 plugin (Vite + TypeScript, SDK 0.0.16)
  index.html, src/main.ts phone page + glasses UI (cards, faces, timer, menu, speech, prep)
  src/matcher.ts          sentence -> cards (pure)
  src/*.json              phrases, deck, asllex, wiktionary, top, checked
  public/handshapes/, public/faces/   generated pictures
  review.html, probe.html checking tools
tools/                    open_palm_server.py, data builders, bench_llm.py, creao_prep_prompt.md
docs/OPEN_PALM_PLAN.md    design decisions, AI details, status
```

## Status

- Everything above has been checked in the Even simulator. **The real glasses still need testing:** long-press reaching the app, picture and face legibility, real mic, and timing.
- About 2,200 rarer signs have template instructions only.
- Some Wiktionary descriptions show a different variant of the sign than the drawing.
- Even Hub app `Open Palm` (`com.openpalm.openpalm`) is not uploaded yet.
