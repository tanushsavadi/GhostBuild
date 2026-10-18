# Thresholds: placeholders

Status: PLACEHOLDER. Not calibrated.

- camera.mean_luma lt 25 (dark frame)
- camera.luma_std lt 8 (flat frame; the failing window needs both)
- camera.luma_std gt 8 (contrast, used by the "dark but with contrast" check)
- camera.motion gt 0.15 (LED demo wave)

TODO: calibrate every value above from the Pi spike, using measured frames from the real station, lens covered and uncovered, and a hand wave. Update the cards and the `why` notes in the same commit.
