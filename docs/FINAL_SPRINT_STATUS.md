# Final sprint status

- Branch/worktree: `codex/final-sprint`, `.worktrees/final-sprint`; base remote verified `cd83f6a` (2026-10-17 23:44 PDT). Existing worktrees untouched. Current commit: use `git rev-parse HEAD`.
- Milestone: Gate 1 first frame passed; implementing generic phone controls, grounded visual help, ElevenLabs, CREAO reliability.
- Authority: latest user sprint explicitly expands general-purpose guidance and sponsor integration; overrides historical Pi-required/sponsor-cut wording narrowly. Keep deterministic HUD, reviewed cards, evidence labels and manual/measured distinction. No contract change planned.
- Baseline: `make test` PASS: Python core 453, Pi 77, knowledge 244, assets 40; G2 172; Python/TS 22 contract examples; generic lint + secret scan. Dependencies installed in isolated worktree. npm audit reports dev-tool vulnerabilities, review before release.
- Physical: **PASS (operator reported)** phone LAN access + QR launch → GHOSTBUILD → BUILD/FIX. Image/gesture/voice/Beta tests **NOT RUN**; operator requested later testing. No claim of measured hardware success.
- Services: backend :8787 (exec session 92307), Vite :5173 (3504), current LAN `172.22.171.236`. Restart backend after integration; preserve logs/sessions. Browser regression should use separate :8788.
- Workers: `codex/final-g2` owns g2; `codex/final-voice` voice/intent + integrations/elevenlabs; `codex/final-creao` knowledge + research/cards APIs. Cherry-pick reviewed checkpoints; never wholesale merge b/voice or PR2.
- Provider credentials absent at bootstrap. User authorized ONE CREAO research run + ONE short STT + ONE short TTS after local keys available. Do not retry ambiguous paid starts. No real provider evidence yet.
- Next: implement usable phone onboarding/catalog/navigation/audio fallback; safely serve high-res/manifest images; verify actual browser flows; integrate workers, full tests, .ehpk + physical runbook/demo evidence.
