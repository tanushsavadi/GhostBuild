# Even Hub listing: Open Palm

Text to paste into the developer portal (hub.evenrealities.com).

**Name:** Open Palm  (must match `app.json` and the name on the glasses)

**Short description:**
Say what you want to tell a Deaf person; your glasses show you how to sign it, one sign at a time, hands-free.

**Description:**
Signing needs both hands and eye contact, so a phone gets in the way. Open Palm puts each American Sign Language sign in your view: the handshape, two short how-to lines, and a small face showing the expression to hold (question brows, a head shake for "not", a smile). Signs move on by themselves; tap to pause, swipe down for the full step-by-step description.
Long-press for the menu: speak a sentence, prepare a conversation (describe the situation and get the sentences you'll likely need, ready in advance), or practise signs.
Open Palm is a phrasebook coach for beginners, not an interpreter. Sign data: ASL-LEX 2.0 (CC BY-NC 4.0) and Wiktionary (CC BY-SA 4.0).

**Release notes (version 0.1.0):**
Shows how to sign what you want to say to a Deaf person: one card per ASL sign with the handshape, how-to lines and facial expression.
Speak or type a sentence, or prepare a whole conversation in advance; signs advance hands-free.

**Permissions (as declared in the package):**
- G2 microphone: you choose "Speak a sentence" or "Prepare a conversation" in the menu, say it, and tap; the speech is turned into text. Nothing is recorded or stored.
- Network: the developer's server for speech-to-text, sign order and conversation prep (`https://likeness-cedar-deluxe.ngrok-free.dev`).

**Privacy policy:** g2/store/PRIVACY.md (link to its GitHub page).

**Assets** (greyscale only; colour is rejected):
- Icon: `icon_foreground.png` (white palm, transparent) on `icon_background.png` (dark grey); preview: `icon_preview.png`. Rebuild with `uv run tools/build_store_assets.py`.
- Screenshots (simulator, flattened on black): `screenshots/1_card_question.png`, `2_menu.png`, `3_how_description.png`, `4_prepared_sentences.png`.

**Upload steps** (from Even's docs):
1. `cd g2 && npm run pack` gives `open-palm.ehpk`. Bump `version` in `app.json` for every new upload.
2. hub.evenrealities.com → your project → **Builds** → upload `open-palm.ehpk` (Draft).
3. Promote to **Test**; in **Beta groups** create a group with your email and push the build.
4. On the phone: Even app → **Me → Beta tester** → Install. Test with the phone locked.
5. To publish: promote **Test → Submitted** (metadata locks). Reviewers use the checklist in Even's App Submission page.
