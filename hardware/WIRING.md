# Pi station wiring and spike results

Status: **TEMPLATE. Nothing below is verified.** Every `TODO` must be filled by a human from the physical
build or from `pi/tools/spike.py` output (`spike_out/wiring_block.md`). Do not invent values and do not
copy values from other documents. A pin change updates this file and the Repair Card together.

Source labels: MEASURED LIVE (spike measured it) · HUMAN CONFIRMED (a person looked) · HUMAN-ENTERED
(a person typed it from the physical build).

## Station

| Item | Value | Source |
|---|---|---|
| Filled in by / date | TODO | HUMAN-ENTERED |
| Pi model | TODO | MEASURED LIVE (`/proc/device-tree/model`) |
| OS | TODO | MEASURED LIVE (`/etc/os-release`) |
| Python | TODO | MEASURED LIVE |
| Pi hostname / IP on the demo network | TODO | HUMAN-ENTERED |
| Laptop (core) IP and port | TODO | HUMAN-ENTERED |
| Pi can reach core `/health` | TODO | MEASURED LIVE (spike) |

## Camera

| Item | Value | Source |
|---|---|---|
| Camera module / sensor as the system reports it | TODO | MEASURED LIVE (`rpicam-hello --list-cameras`) |
| Backend that opened (picamera2 / opencv / rpicam) | TODO | MEASURED LIVE (spike) |
| Measured new-frame rate (fps) | TODO | MEASURED LIVE (spike) |
| Mount and aim (what the fixed field of view shows) | TODO | HUMAN-ENTERED |
| The obstruction used in the demo (paper flap / lens cover) | TODO | HUMAN-ENTERED |
| Reference photo of the camera view | `spike_out/frame_*.jpg` TODO attach | MEASURED LIVE |
| Lens-covered thresholds (mean_luma / luma_std / detail), this scene and light | TODO | MEASURED LIVE (derived by spike; re-measure at the venue) |
| Hand-wave motion vs idle motion | TODO | MEASURED LIVE (spike `--with-wave`) |

## LED

| Item | Value | Source |
|---|---|---|
| GPIO pin (BCM number) | TODO | HUMAN-ENTERED, read from the physical wiring |
| Physical header position or label | TODO | HUMAN-ENTERED |
| Active level (high / low) | TODO | HUMAN-ENTERED |
| Blink seen by a person | TODO (YES / NO) | HUMAN CONFIRMED |
| Anything else wired to that pin? | TODO | HUMAN-ENTERED |

LED state in observations is **COMMANDED** (a GPIO write), never measured light.

## Pin table (filled only from the build)

| BCM | Header position | Connected to | Direction | Confirmed by |
|---|---|---|---|---|
| TODO | TODO | LED signal | output | TODO |

## Evidence rules for this station

* `camera: null` or a stuck `frame_seq` is an error, never success.
* LED reports COMMANDED only. A dry-run LED is never reported on live data.
* Fake or replayed observations carry `source` `simulated` / `replay`.

## Change protocol

Pin or camera change: edit this file, the Repair Card in `knowledge/cards/`, and `web/assets/wiring.svg`
(owner A) in the same change set, then re-run `pi/tools/spike.py`.
