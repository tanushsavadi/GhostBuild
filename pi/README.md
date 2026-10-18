# GhostBuild Pi station (`pi/`)

A Raspberry Pi + its camera + one LED. The Pi measures the camera view (features only, no images leave
the Pi), commands the LED on hand motion, and POSTs one `Observation` (contract v2) per tick to the core.
It does not decide what anything means. The core does.

**Not yet verified on real hardware.** Everything here is unit-tested with a fake camera and a dry-run
LED on a laptop. Step 3 (the spike) is how you find out what actually works on your Pi.

## Honesty rules (these are product rules, not style)

| Situation | What the Pi does | What it never does |
|---|---|---|
| Camera cannot open / read fails | `camera: null`, `error: camera_open_failed` / `camera_read_failed`, retries the camera every 2 s | repeat the last frame, or send made-up numbers |
| Camera frozen (no new frame) | `frame_seq` stays put, `frame_age_ms` grows | bump `frame_seq` for a frame it did not capture |
| LED | reports `commanded_on` (COMMANDED) | claim light was seen. A GPIO write is not light |
| `--dry-run-led` on live data | `led: null` (a log line is not an output) | report a dry-run command as a commanded LED |
| `--fake-camera` / `--replay` | `source` = `simulated` / `replay` | accept `--source pi_live` with them (exit 2) |
| LED pin | only from `--led-pin` (explicit) or an allowlisted `$GHOSTBUILD_LED_PIN` | guess a pin |

## 1. Set up a fresh Pi (Raspberry Pi OS Bookworm or Trixie assumed)

Replace `<...>` with your own values. Do not paste placeholders.

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-gpiozero python3-numpy python3-pil python3-venv git
# get the code onto the Pi, either:
#   git clone <repo-url> ~/ghostbuild         (if the Pi can reach the repo)
#   scp -r pi <user>@<pi-host>:~/ghostbuild/  (from the laptop, repo root)
cd ~/ghostbuild
python3 -m venv --system-site-packages ~/ghostbuild-venv     # --system-site-packages is required for picamera2
. ~/ghostbuild-venv/bin/activate
pip install -r pi/requirements.txt
export PYTHONPATH=$PWD/pi                                     # or cd pi before running python -m ghostbuild_pi
```

**Camera enabled?** On Bookworm/Trixie official camera modules are auto-detected by libcamera; there is no
"enable camera" switch. Check:

```bash
rpicam-hello --list-cameras        # Bullseye with libcamera: libcamera-hello --list-cameras
```

If it prints `No cameras available`: power the Pi **off**, reseat the camera ribbon at both ends
(contacts orientation is in the camera's official docs), power on, retry. Third-party sensors need a
`dtoverlay=<sensor>` line in `/boot/firmware/config.txt` (older images: `/boot/config.txt`), then reboot.
Bullseye "legacy camera" mode is not supported: picamera2 needs the libcamera stack.

**Laptop IP and reachability.** On the laptop (same Wi-Fi/LAN as the Pi):

```bash
ipconfig getifaddr en0     # macOS Wi-Fi (try en1 if empty)    |  Linux: hostname -I
```

The core must listen on all interfaces (for example `--host 0.0.0.0` on its port 8787). From the Pi:

```bash
curl -s http://<laptop-ip>:8787/health
```

If that hangs: wrong IP, different network (guest Wi-Fi often isolates clients), or the laptop firewall.

## 2. Look at what the Pi can do (no hardware needed to run)

```bash
python -m ghostbuild_pi --list-backends     # which camera libraries/tools were found
```

## 3. Run the hardware spike (once, a human at the Pi)

```bash
cd ~/ghostbuild
python3 pi/tools/spike.py --core http://<laptop-ip>:8787 --led-pin <BCM> --with-wave
```

It prints PASS / FAIL / WARN / SKIP for: Pi model, OS, Python, which camera backends import, camera
detected, camera opens (and which backend), 30 frames + measured fps, 3 JPEGs in `./spike_out/` (open
them!), three guided phases (`UNCOVERED`, `LENS COVERED`, `UNCOVERED AGAIN`, each waits for Enter), the
measured feature numbers and the thresholds those numbers suggest, an optional hand-wave phase
(`--with-wave`) that replays the LED rule over the measured motion, an LED blink test, `GET /health`, and
one `POST /observation` (labelled `source=simulated`, `dev=spike-<host>` so it can't pass for live data).

* The LED is `HUMAN CONFIRMED` only if you type `y` after watching it. No pin given means `SKIP`, never PASS.
* Last, it prints a block for `hardware/WIRING.md` (also saved to `spike_out/wiring_block.md`;
  full data in `spike_out/spike_report.json`). Paste it; anything it could not measure says `TODO`.
* Exit code 0 only if the camera opened, captured frames, and covered vs uncovered separated cleanly.
* Run the spike with the station client stopped (one camera owner at a time).

## 4. Run the station

```bash
# real camera + real LED (pin from hardware/WIRING.md, confirmed by the spike)
python -m ghostbuild_pi --core http://<laptop-ip>:8787 --led-pin <BCM> --dev pi-01 --hz 5

# no LED yet: camera only (led is reported as null)
python -m ghostbuild_pi --core http://<laptop-ip>:8787

# laptop development, labelled simulated. Scenarios: blocked clear flicker frozen disconnect wave
python -m ghostbuild_pi --core http://127.0.0.1:8787 --fake-camera flicker --dry-run-led

# record, then replay (source=replay) without any camera
python -m ghostbuild_pi --no-post --fake-camera wave --dry-run-led --record recordings/wave.jsonl --duration 10
python -m ghostbuild_pi --core http://127.0.0.1:8787 --replay recordings/wave.jsonl --loop
```

Useful flags: `--roi x0,y0,x1,y1` (fractions of the frame, motion only), `--no-led-on-motion`,
`--led-active-low`, `--camera-backend picamera2|opencv|rpicam`, `--print` (JSON lines on stdout),
`--no-post`, `--duration S`, `-v`. The LED rule: motion > 0.15 for 2 consecutive new frames lights the LED
for 2.0 s then off, never toggled faster than 5 Hz, and a lens being covered or uncovered (a big mean-luma
jump, `--scene-change-luma`, default 30) never counts as a wave. The LED is always driven off on exit
(Ctrl-C, SIGTERM, errors).

Start order for the demo: core first, then the station. The station survives a missing core and just keeps
trying (old observations are dropped, not queued).

`recordings/` is git-ignored except `.gitkeep`; keep recordings out of commits unless the lead asks.

### Optional: systemd unit

`/etc/systemd/system/ghostbuild-pi.service` (fill the `<...>` values from WIRING.md; the user must be in
the `video` and `gpio` groups):

```ini
[Unit]
Description=GhostBuild Pi station
After=network-online.target
Wants=network-online.target

[Service]
User=<user>
WorkingDirectory=/home/<user>/ghostbuild
Environment=PYTHONPATH=/home/<user>/ghostbuild/pi
ExecStart=/home/<user>/ghostbuild-venv/bin/python -m ghostbuild_pi --core http://<laptop-ip>:8787 --led-pin <BCM>
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now ghostbuild-pi && journalctl -u ghostbuild-pi -f
```

## 5. Finding the LED pin safely

Never guess a pin and never assume one from an old doc. This README does not ask you to build or change
any circuit. If the LED is not wired yet, ask whoever owns the kit.

1. Read the pin from the real wiring: follow the LED's signal wire to the header (or the label on a HAT or
   breakout board). `pinout` on the Pi prints the header diagram with BCM numbers.
2. Have a second person check it. Driving a pin that something else uses can misbehave or damage hardware.
3. Use the **BCM** (GPIO) number, not the physical header position. The code refuses 0, 1 and anything above 27.
4. Prove it with the spike blink and your own eyes, then record it in `hardware/WIRING.md`
   (a pin change updates WIRING.md and the Repair Card together).
5. LED stays dark but the log says ON? Wrong pin, or the LED is wired active-low (`--led-active-low`).

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `camera_open_failed` | `rpicam-hello --list-cameras` empty: reseat ribbon with power off. Another process (`rpicam-hello`, an old station) holds the camera: stop it. venv created without `--system-site-packages`, so picamera2 can't import: recreate it |
| `camera_read_failed` repeating | Camera unplugged or crashed. Station retries every 2 s. Power-cycle the Pi if it never recovers |
| `ImportError: picamera2` | `sudo apt install python3-picamera2`; use the venv from step 1 |
| LED log line "no GPIO library" / "Permission denied" / `GPIO busy` | `sudo apt install python3-gpiozero`; `sudo usermod -aG gpio $USER` then log out/in; make sure nothing else owns the pin. The station keeps running with `led: null` and says so loudly in the log |
| `refused ... allowlist` | the pin came from `$GHOSTBUILD_LED_PIN`; pass `--led-pin N` to confirm it explicitly |
| High CPU | lower `--hz`, use `--width 320 --height 240`, prefer picamera2 (the `rpicam` fallback spawns a process per frame and manages roughly 1 fps) |
| Core never receives anything | check the station log for `POST ... failed`; `curl http://<laptop-ip>:8787/health` from the Pi; same network; core bound to 0.0.0.0 |
| Core ignores observations after a restart | `seq` starts from a wall-clock-derived base so a restart always goes forward; a Pi with a wrong clock at boot (no RTC, before NTP) can break that, so wait for NTP before starting |
| Covered/uncovered not separating | scene too dark even when uncovered, or the cover lets light through. Re-run the spike with the real scene and the real cover |

## Tests

From the repo root on the laptop: `uv run pytest -q pi/tests`.
