# Operator runbook — laptop, Pi, G2 (live hardware only)

For the current general BUILD/FIX product, use [SETUP.md](SETUP.md) and [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md). This page retains the optional Pi-station network/wiring checklist; its unfilled matrix is not physical release evidence. Simulated runs do not count. Record each result in the matrix at the bottom. Laptop IP below is an example; get yours with `ipconfig getifaddr en0`.

## Quick start (3 terminals, in this order)
1. **Laptop:** `git checkout main && git pull && make setup && make core` (leave running). Then in a second tab: `make lan` — it prints the exact Pi and G2 commands with this laptop's IP and says whether core is reachable.
2. **Pi operator:** run the "PI OPERATOR" lines `make lan` printed. First one must print JSON, otherwise stop and fix the network (section 0).
3. **G2 operator:** run the "G2 OPERATOR" lines. First goal: the real welcome frame on the glasses, then press, then the WHERE picture.

**Report the first live result exactly like this** (paste logs): `Pi->core: PASS/FAIL (/health JSON)`, `Core->G2: PASS/FAIL (what the glasses showed)`, plus the first error line from the Pi terminal, `make core` terminal, or the phone/Even app.

**Network ladder** (go down only when the rung above fails): (1) venue Wi-Fi, http://LAN IP; (2) phone hotspot or laptop Internet Sharing for all three devices; (3) HTTPS tunnel (e.g. `tailscale funnel 8787`) — then rebuild with `BACKEND=https://<name>.ts.net make g2-pack` (a packaged app may block cleartext http to a LAN IP; this is unverified until the first device test).
**macOS firewall:** the first time Python listens, click Allow. If you missed it: System Settings -> Network -> Firewall -> allow Python, or `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$(uv run python -c 'import sys;print(sys.executable)')" --unblockapp "$(uv run python -c 'import sys;print(sys.executable)')"`.

## 0. Network (do first)
Laptop, Pi and phone must be on the SAME network that allows device-to-device traffic. Venue/campus Wi-Fi often isolates clients. If `curl http://<laptop-ip>:8787/health` from the Pi fails, use a phone hotspot or the laptop's Internet Sharing for all three. When the laptop IP changes, rebuild the `.ehpk` (section 3). macOS will ask to allow incoming connections for Python the first time: Allow.

## 1. Laptop (D / lead)
```
git fetch && git checkout main && git pull
make setup                       # python + node deps (g2, contracts)
make test                        # expect: GREEN python, GREEN ts, lint-generic ok, all pytest/vitest pass
make core                        # Manual guidance needs no Pi; the telemetry demo needs live Pi observations.
make health                      # or: curl http://<laptop-ip>:8787/health
```
Expected before the Pi connects: `"pi_link":"down"`. After the Pi connects: `"pi_link":"up","source":"pi_live","camera":"ok"`. Open `http://<laptop-ip>:8787/phone` on a laptop browser: source badge LIVE, no red SIMULATED banner.

## 2. Raspberry Pi (C)
```
git clone https://github.com/tanushsavadi/GhostBuild && cd GhostBuild && git checkout main
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
npm ci --prefix g2
(cd g2 && npm rebuild @evenrealities/evenhub-simulator && npx evenhub login)                                   # human step: your Even developer account
BACKEND=http://<laptop-ip>:8787 make g2-pack        # writes g2/ghostbuild.ehpk (NOT committed)
```
Install on the phone: (a) fastest: `BACKEND=http://<laptop-ip>:8787 make g2-dev` then `make g2-qr`, scan with the Even app (dev sideload); (b) Beta: upload `ghostbuild.ehpk` at hub.evenrealities.com -> project -> Builds, push to a Beta group, phone: Me -> Beta tester -> Install. Do (a) first to find problems, (b) as soon as (a) shows frames.
Do not enable voice yet (`VITE_FLAG_VOICE` unset).
Device checklist: see `g2/README.md` ("Physical device checklist"). Key checks: text legible and centered; `●` renders (else the plugin substitutes); single press arrives once; swipe direction; double press mid-task returns to the task list and double press on the root screen shows the system exit dialog (cancel keeps the app); guide picture legible; phone locked 5 min; kill/restart core recovers.
Troubleshooting: blank G2 + `GHOSTBUILD OFFLINE` -> phone cannot reach `http://<laptop-ip>:8787` (open it in the phone browser; if it fails it is the network); app installs but never connects -> `.ehpk` whitelist has a different IP (rebuild); no frames after connect -> `curl .../state`, then check `g2_clients` in `/health`.

## 4. Acceptance run
Follow `docs/ACCEPTANCE.md` on physical G2 with the Pi live. Record below.

| Check | Result (PASS/FAIL/NOT RUN) | Who/when/evidence (log file, photo) |
|---|---|---|
| Pi camera | NOT RUN | |
| Pi LED | NOT RUN | |
| Pi -> core | NOT RUN | |
| Core -> physical G2 | NOT RUN | |
| Welcome / task request | NOT RUN | |
| Fault cue | NOT RUN | |
| Touch press | NOT RUN | |
| WHERE image | NOT RUN | |
| HOW / CORRECT press cycle | NOT RUN | |
| Recovery -> automatic HUD clear | NOT RUN | |
| Beta package | NOT RUN | |
