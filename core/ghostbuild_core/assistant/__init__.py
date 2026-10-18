"""Conversational assistant: clarifying intake before a guide exists, and answers about the step the wearer is on.

Modules (each importable and testable alone):
  schemas  - data shapes (profile, brain replies, chat messages, step notes)
  cuefmt   - fold model text into a safe two-line glasses cue
  prompts  - pure builders for the system prompts and the context sent to a brain
  brain    - the Brain protocol, the Anthropic-backed brain, and a scripted fake for tests
  router   - decides whether an utterance is a plain command (deterministic) or a real question (assistant)
  service  - the orchestrator: threads, per-session conversation state, notes; applies results on the main loop
The model never writes steps: guides still come from reviewed or validated cards. It asks, explains, and keeps notes."""
