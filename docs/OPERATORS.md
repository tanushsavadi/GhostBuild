# Operator runbook — laptop, Pi, G2 (live hardware only)

Simulated runs do not count. Record each result in the matrix at the bottom. Laptop IP below is an example; get yours with `ipconfig getifaddr en0`.

## 0. Network (do first)
Laptop, Pi and phone must be on the SAME network that allows device-to-device traffic. Venue/campus Wi-Fi often isolates clients. If `curl http://<laptop-ip>:8787/health` from the Pi fails, use a phone hotspot or the laptop's Internet Sharing for all three. When the laptop IP changes, rebuild the `.ehpk` (section 3). macOS will ask to allow incoming connections for Python the first time: Allow.

## 1. Laptop (D / lead)
```
git fetch && git checkout lead/hw-pivot && git pull
make setup                       # python + node deps (g2, contracts)
make test                        # expect: GREEN python, GREEN ts, lint-generic ok, all pytest/vitest pass
make core                        # LIVE mode, port 8787 (needs the Pi). Never use core-sim for judging.
make health                      # or: curl http://<laptop-ip>:8787/health
```
Expected before the Pi connects: `"pi_link":"down"`. After the Pi connects: `"pi_link":"up","source":"pi_live","camera":"ok"`. Open `http://<laptop-ip>:8787/phone` on a laptop browser: source badge LIVE, no red SIMULATED banner.

## 2. Raspberry Pi (C)
```
git clone https://github.com/tanushsavadi/GhostBuild && cd GhostBuild && git checkout lead/hw-pivot
sudo apt update && sudo apt install -y python3-picamera2 python3-gpiozero python3-numpy python3-httpx python3-venv
python3 -m venv --system-site-packages ~/gbvenv && . ~/gbvenv/bin/activate && pip install -r pi/requirements.txt
rpicam-hello --list-cameras      # must list a camera; if not: power off, reseat the camera ribbon (contacts toward the correct side per Raspberry Pi docs), enable camera
python pi/tools/spike.py --core http://<laptop-ip>:8787 --led-pin <BCM number from YOUR wiring>
```
Read the LED pin from the physical wiring (never guess; `pinout` prints the header). The spike prints PASS/FAIL per check, saves 3 JPEGs to `spike_out/` (look at them: is it the station?), prompts UNCOVERED / LENS COVERED / UNCOVERED AGAIN, prints suggested thresholds, blinks the LED three times (answer y/n), and prints a block for `hardware/WIRING.md`. Paste that block into `hardware/WIRING.md` and send the threshold numbers to the lead (cards use mean_luma < 25 and luma_std < 8 as placeholders).
Run the station:
```
cd pi && python3 -m ghostbuild_pi --core http://<laptop-ip>:8787 --led-pin <N>
```
Expected: log lines `sent N, failed 0`; laptop `/health` flips to pi_link up, source pi_live. Cover the lens: within ~2 s `/state` engine=FAULT. Wave a hand: LED lights ~2 s.
Troubleshooting: camera not detected -> reseat ribbon, `rpicam-hello`, check `dmesg | grep -i imx`/`ov5647`; GPIO permission denied -> add user to `gpio` group, relogin; `failed` counts rising -> wrong IP/firewall/client isolation; high CPU -> `--hz 3`; LED never lights -> wrong pin or polarity (spike asks you).

## 3. G2 plugin and Beta (B)
```
cd g2 && npm ci && npm rebuild @evenrealities/evenhub-simulator
npx evenhub login                                   # human step: your Even developer account
BACKEND=http://<laptop-ip>:8787 make g2-pack        # writes g2/ghostbuild.ehpk (NOT committed)
```
Install on the phone: (a) fastest: `BACKEND=http://<laptop-ip>:8787 make g2-dev` then `make g2-qr`, scan with the Even app (dev sideload); (b) Beta: upload `ghostbuild.ehpk` at hub.evenrealities.com -> project -> Builds, push to a Beta group, phone: Me -> Beta tester -> Install. Do (a) first to find problems, (b) as soon as (a) shows frames.
Do not enable voice yet (`VITE_FLAG_VOICE` unset).
Device checklist: see `g2/README.md` ("Physical device checklist"). Key checks: text legible and centered; `●` renders (else the plugin substitutes); single press arrives once; swipe direction; double press shows the system exit dialog and cancel keeps the app; guide picture legible; phone locked 5 min; kill/restart core recovers.
Troubleshooting: blank G2 + `GHOSTBUILD OFFLINE` -> phone cannot reach `http://<laptop-ip>:8787` (open it in the phone browser; if it fails it is the network); app installs but never connects -> `.ehpk` whitelist has a different IP (rebuild); no frames after connect -> `curl .../state`, then check `g2_clients` in `/health`.

## 4. Acceptance run
Follow `docs/ACCEPTANCE.md` on physical G2 with the Pi live. Record below.

| Check | Result (PASS/FAIL/NOT RUN) | Who/when/evidence (log file, photo) |
|---|---|---|
| Pi camera | NOT RUN | |
| Pi LED | NOT RUN | |
| Pi -> core | NOT RUN | |
| Core -> physical G2 | NOT RUN | |
| Welcome / BUILD / FIX | NOT RUN | |
| Fault cue | NOT RUN | |
| Touch press | NOT RUN | |
| WHERE image | NOT RUN | |
| HOW / CORRECT swipe | NOT RUN | |
| Recovery -> automatic HUD clear | NOT RUN | |
| Beta package | NOT RUN | |
