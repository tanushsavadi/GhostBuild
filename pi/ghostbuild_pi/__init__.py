"""GhostBuild Pi station: camera features + one LED -> Observation JSON -> core.

Honesty rules (see pi/README.md):
  * camera null (open/read failure) is an error, never success; stale values are never substituted.
  * the LED state is COMMANDED, never measured light.
  * fake or replayed data is never labelled pi_live.
"""

__version__ = "0.1.0"
