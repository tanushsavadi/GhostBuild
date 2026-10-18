# GhostBuild live acceptance (Raspberry Pi + physical G2)

Supersedes PIVOT §8/§8b. Each line is pass/fail with the session-log filename. The simulator runs beside the glasses but never counts.

**Pre-flight (30 s):** `/health` → `pi_link: up`, `source: pi_live`, `camera: ok`; simulator visible and labelled; G2 battery > 30%.

1. New session on G2: `GHOSTBUILD` welcome once, then `BUILD OR FIX?`; swipe + press selects FIX; goal resolves to the Pi camera card. Reconnecting the plugin does NOT show the welcome again.
2. Healthy: HUD blank for 60 s (session log: 0 frames).
3. Obstruct the camera: within 3 s `CAMERA VIEW LOST / CHECK CAMERA LENS`. A 1 s flicker produces nothing.
4. After the offer delay, one `PRESS FOR PICTURE` line (once). Press → WHERE image on G2 (or text fallback if the image failed). Swipe → HOW → CORRECT; swipe up/press returns to the cue without losing context.
5. Remove the obstruction: measured frames recover → one `● CAMERA VIEW BACK`, then blank. No press was needed or accepted as a commit.
6. Wave in the camera's field of view: the LED lights (human-visible); G2 shows `● LED COMMANDED` (never "verified"), then blank.
7. Press while healthy: `ALL TESTS PASSING` (LIVE), blank in 3 s.
8. Kill the Pi process: `PI LINK LOST` error within 6 s, never a stale OK. Restart: recovers without reopening the app.
9. Kill the backend: plugin shows `GHOSTBUILD OFFLINE`; restart recovers.
10. Double press: system exit dialog; cancel keeps the app working.
11. Unsupported goal (phone text): honest `NOT SUPPORTED YET`, no invented diagnostic.
12. Second judge after reset (<= 30 s): first frame reflects the new real state, no stale success.

Pass = all of the above with no phone glance in 3-6.
