# Open Palm (branch test_sim): rules for coding agents
Hackathon build on Even G2; deadline Sun 2026-10-18 12:00 PDT; live-demo reliability over features. Design and decisions: docs/OPEN_PALM_PLAN.md. Usage: README.md.

- Product: one card per sign for a sentence a hearing wearer wants to say to a Deaf person. Individual signs in simplified ASL order; never call it translation or an interpreter.
- Signs come only from g2/src/deck.json (hand-written, wins) and g2/src/asllex.json (built by tools/build_deck.py from ASL-LEX + tools/howto.json). Anything else is fingerspelled. AI (local Ollama via /api/translate, CREAO via /api/prepare) only chooses signs, order, face and emotion; it never writes sign instructions.
- Lens design was agreed with the user (see the plan): ultra-minimal card, face top right, auto-advance with dots, long-press menu. Ask the user before changing it.
- Card wording: "palm facing up/down/out", "palm facing you", never "palm up"; two lines of at most 36 characters.
- Check status shown on the phone: REF-CHECKED, UNCHECKED, AUTO · UNCHECKED, FINGERSPELL, AI ORDER. No card claims a Deaf signer checked it.
- Licences: ASL-LEX CC BY-NC 4.0 (non-commercial, credit it; videos linked only, never bundled); Wiktionary CC BY-SA 4.0 (credit per sign; adaptations stay CC BY-SA); M/N drawings public domain. Never copy Lifeprint.
- Privacy: audio is forwarded to ElevenLabs and never stored; history is opt-in, text only, on the laptop (tmp/open_palm).
- Secrets only in .env on the laptop; never in g2/, the repo, logs or chat. Run scripts/check_secrets.sh before committing.
- Even G2 SDK 0.0.16: verify calls against the everything-evenhub skills and node_modules/@evenrealities/even_hub_sdk/dist/index.d.ts (the .d.ts wins). updateImageRawData takes PNG bytes, one call at a time; images ≤ 288×144, 4-bit. Double-tap always exits.
- Test on the simulator, then on the real G2, before calling anything done.
