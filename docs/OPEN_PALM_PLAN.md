# Sign coach — plan (authoritative on branch test_sim, 2026-10-17)

## Product
A hearing person wearing Even G2 wants to talk to a Deaf person. They say an English phrase; the glasses show one card per sign: the ASL-LEX handshape image (pixelated to the lens) and two short lines on location and movement. They sign it. Hands stay free and eyes stay on the other person, which a phone cannot offer.

Scope is level A: individual signs from a checked vocabulary, in English order. It is not ASL translation, and nobody on the team is Deaf, so cards are checked against reference videos, not by a signer.

## Demo (about 30 s)
| Wearer says | Cards |
|---|---|
| "Hello, nice to meet you" | HELLO → NICE → MEET → YOU |
| "My name is Abdul" | MY → NAME → A·B·D·U·L (name from settings) |
| "Thank you" | THANK-YOU |

Vocabulary: HELLO, NICE, MEET, YOU, MY, NAME, THANK-YOU, PLEASE, YES, NO, HELP, SORRY, plus A–Z. All 12 signs are in ASL-LEX 2.0; they use 7 handshapes (closed_b, open_b, 1, h, a, flat_h, s).

## Lens layout
Handshape image 144×144 on the left; text on the right: sign name and n/N, two how-to lines, the status label. Tap = next card (auto-advance as an option). Double-tap = exit.

## Steps
| Step | Work | Done when | Status |
|---|---|---|---|
| 0 Go/no-go | Pixelated ASL-LEX handshapes on the real G2 at 144 px (thin / bold / 96 px bold): `/probe.html` | 5 of 5 handshapes named on the lens; send time recorded | Built; lens test pending |
| 1 Cards | Card layout, tap = next | Works on the G2 | Built, simulator-checked |
| 2 Deck | `g2/src/deck.json`: ASL-LEX phonology for the 12 signs; lines drafted by AI (Claude, in session) from it; a person checks each against its ASL-LEX video and sets `status` to `REF-CHECKED` | 12 signs + 26 letters, every sign card REF-CHECKED | Drafted; all UNCHECKED |
| 2b Full vocabulary | `g2/src/asllex.json` from `uv run tools/build_deck.py`: 2,311 words from all ASL-LEX 2.0 signs, lines composed from phonology coding (AUTO · UNCHECKED); aliases such as I → ME; plural/-ing/-ed handling; M and N drawings | Everyday phrases sign instead of fingerspelling | Built, simulator-checked |
| 2c Clear lines | `tools/howto.json`: hand-written lines for ~85 common signs (WANT, NEED, WHERE, EAT, ME…), merged by `build_deck.py` and attached to the sign, so aliases (I → ME) get them too; template lines now say when the fingers bend | No template lines in the common sample phrases | Built |
| 2d Full descriptions | `g2/src/wiktionary.json` from `uv run tools/fetch_wiktionary.py`: Wiktionary's step-by-step "Production" text (CC BY-SA 4.0) for ~290 glosses, incl. palm direction and facial expression. Swipe down on a card pages through it, swipe up goes back; the phone shows it with credit | Every sign in the demo phrases has one | Built, simulator-checked |
| 2e Sentences | `g2/src/phrases.json`: ~22 common sentences signed in ASL order with a face cue (e.g. "What's your name?" → YOUR NAME WHAT, brows down); contractions expanded ("can't" → CANNOT); matching ignores dropped words (is/are/do/the) | Common greetings and questions come out in ASL order | Built, simulator-checked |
| 3 Typed phrase | Phone page text box → `matcher.ts` on the phone → cards (no laptop needed) | The 3 demo phrases give the right cards | Built, simulator-checked |
| 4 Speech | Glasses mic → laptop Vosk → phrase → cards | 9/10 spoken phrases right; first card ≤ 2 s | 1.5 h |
| 5 Unknown words | Fingerspelling; AI · UNCHECKED behind a flag | No confident wrong sign | 1 h |
| 6 Demo | Rehearse; film through the lens | Script works 3 times in a row | 30 min |

Cut order if behind: the AI part of step 5, then step 4 (typing still works).

## Run
From `g2/`: `npm install` (then `npm rebuild @evenrealities/evenhub-simulator` if `npm run simulate` is not found), `npm run dev`, then either `npm run simulate` or `npx evenhub qr --url http://<laptop-wifi-ip>:5173`.
- `/` is the sign coach; `/?phrase=Thank%20you` starts a phrase on load; `/?style=thin|bold|bold96` picks the drawing style (default bold).
- `/probe.html` is the step 0 handshape test.
- Handshape PNGs: `uv run tools/build_handshapes.py --all` (writes `g2/public/handshapes/`). Vocabulary: `uv run tools/build_deck.py` (writes `g2/src/asllex.json`).
- Windows: the phone can only reach the dev server if port 5173 is allowed inbound (the venue network is Public).

## Decisions
- Solo branch; no Deaf reviewer; physical G2 available; no ring.
- Speech recognition: offline Vosk on the laptop (tools/keyword_server.py proved the path once).
- Unknown words: fingerspell names and numbers; others AI · UNCHECKED behind a flag, else fingerspell.
- ASL-LEX 2.0 data and handshape images: CC BY-NC 4.0 with credit. The images are served from aslcdi.website through the ASL-LEX visualization; credit both. Videos: © ASL-LEX.org, view only.
