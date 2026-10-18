# Open Palm: design and decisions

Hackathon build on branch `test_sim`. Deadline Sun 2026-10-18 12:00 PDT. How to run and use it is in the [README](../README.md).

## Scope
- A hearing G2 wearer gets one card per sign for a sentence they want to say to a Deaf person.
- **Individual signs in a simplified ASL order.** It is not translation and not an interpreter.
- No Deaf reviewer. Cards are checked against reference videos and labelled with their check status.

## Lens design (agreed with the user; ask before changing)
- **Card:** hand picture 144×144 on the left; text on the right with the sign name, two how-to lines (≤ 36 chars each) and five time dots; face 64×64 at the top right. Status, progress and sources are on the phone only.
- **Face:** brows down = what/where/who question, brows up = yes/no question, arrows = head shake (negation). The mouth shows emotion: happy, sad or surprised. Drawn by `tools/build_faces.py`.
- **Hands-free:** cards advance by themselves.
  - 2.5 s per letter; about 5 s for a simple sign; up to 10 s for two hands or a complex movement.
  - Tap pauses or resumes; reading HOW pauses until you swipe back up.
  - The lens clears 5 s after the last sign. `?review=top` stays tap-to-advance.
- **Menu (long-press):** Speak a sentence, Prepare a conversation, Prepared sentences, Practice signs, Close. Swipes move the cursor and a tap chooses. Speaking from the menu ends with a tap; the phone keeps hold-to-talk.

## AI
The AI never writes sign instructions. It only picks signs from our vocabulary, their order, the face and the emotion. Anything it names that we don't have is fingerspelled.

**Live word order: local model.**
- Path: `/api/translate` → Ollama `qwen3.5:4b-q4_K_M`, kept loaded, about 1 s per sentence.
- Prompt: the same rules and 4 examples as the benchmark, plus an emotion rule.
- Server cleanup:
  - the question word goes last;
  - NOT-X is split into X NOT;
  - I → ME; NOT-LIKE → DONT-LIKE;
  - English filler words are dropped;
  - question brows are dropped unless the English is really a question.
- Plugin side: made-up compounds (TRAIN-TICKET) are split into signs we have, and words the model wanted spelled are signed if we have them.
- Skipped when reviewed content already covers the sentence. Falls back to word by word after 8 s.

**Model comparison** (`tools/bench_llm.py`): 18 sentences, the same prompt, RTX 3060 6 GB. Score = 0.4 signs present + 0.2 face + 0.2 order + 0.2 no filler. The references are AI-drafted, so this ranks the models rather than grading the ASL.

| Model | Score | Usable signs | Latency | On GPU |
|---|---|---|---|---|
| **qwen3.5:4b-q4_K_M** (used) | 0.94 | 97% | 3.2 s cold / ~1 s warm | fully |
| gemma4:e2b-it-qat | 0.93 | 91% | 2.8 s | fully |
| qwen2.5:7b-instruct-q4_K_M | 0.93 | 94% | 4.1 s | 82% |
| qwen3:8b (think off) | 0.86 | 93% | 5.5 s | partly |
| qwen3:4b-instruct-2507-q4_K_M | 0.81 | 94% | 3.1 s | fully |

On the same sentences, word by word without AI scores 0.82, and on casual sentences it scores 0.70 against the AI's 0.84.

**Conversation prep: CREAO.**
- Path: `/api/prepare` → the CREAO agent `CREAO_PREP_APP_ID`, whose instructions are in `tools/creao_prep_prompt.md`.
- The request asks for 6 sentences, at most 4 practice signs, and an emotion per sentence. It includes the opt-in history (`HISTORY`, `HARD SIGNS`).
- It runs in the background, about 40 s, and is polled every 3 s.
- The answer arrives as an attached JSON file. Its link redirects to a pre-signed S3 URL, which must be fetched **without** the CREAO Authorization header.
- CREAO isn't used for live translation: a single sentence takes 40–45 s. The API is undocumented. What works: `POST /api/v1/runs` with `appId` (the input is sent under several field names), `GET /api/v1/runs/{id}`, `Authorization: Bearer`.

**Speech: ElevenLabs.**
- Path: `/api/stt` → `scribe_v2`, sent as raw `pcm_s16le_16`, with `tag_audio_events=false`. Leftover sound tags like `[static]` are removed.
- About 0.5–0.8 s. Audio is never stored.

## Data and licences
- **ASL-LEX 2.0:** the word → sign mapping, coding and drawings, CC BY-NC 4.0. Its videos are © ASL-LEX and are linked, never bundled.
- **Wiktionary:** the descriptions, CC BY-SA 4.0, credited per sign.
- **Lifeprint:** not used. Its terms forbid use in apps.
- **ASL-LEX data quirks we handle:**
  - Four IDs carry stray spaces (`close `, `fry `, `murder `, `santa `).
  - Some words live under variant IDs; the most frequent variant is used.
  - Aliases cover common gaps: I → ME, he/she/it → POINT, store → SHOP, large → BIG, sugar → SWEET, how much → MANY.

## Status (Sun 05:00)
- **Done and simulator-checked:**
  - cards, faces, the timer and the menu;
  - typed and spoken input;
  - local AI order;
  - CREAO prep;
  - opt-in memory;
  - the review page.
- **Reviewed:** 50 signs confirmed; 18 fixed and waiting for a re-check.
- **Not done:**
  - **real-glasses test:** long-press, legibility, mic, timing;
  - Even Hub beta upload;
  - demo video;
  - Devpost write-up.
- **Risk:** if the glasses OS keeps long-press for itself, the menu needs another gesture. The phone page can do everything in the meantime.
