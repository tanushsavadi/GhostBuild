#!/usr/bin/env bash
# Prints the exact copy-paste commands for the Pi and G2 operators with THIS laptop's IP filled in,
# and checks that core is reachable on it. Run on the laptop after `make core`.
cd "$(dirname "$0")/.."
PORT="${PORT:-8787}"
IP="${IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)}"
[ -n "$IP" ] || { echo "no LAN IP found (join Wi-Fi / hotspot first)"; exit 1; }
echo "laptop IP: $IP   (if this changes, rebuild the .ehpk)"
echo
if curl -s -m 3 "http://$IP:$PORT/health" >/tmp/gb_lan_health.json; then
  echo "core reachable at http://$IP:$PORT/health -> $(cat /tmp/gb_lan_health.json)"
else
  echo "core NOT reachable at http://$IP:$PORT  (is 'make core' running? firewall? see docs/OPERATORS.md section 0)"
fi
fw=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null)
echo "macOS firewall: ${fw:-unknown}  (if enabled, click Allow for Python on the first prompt)"
cat <<TXT

== PI OPERATOR (on the Pi) ==
  curl -s http://$IP:$PORT/health                      # must print JSON; if not: wrong network / client isolation
  python pi/tools/spike.py --core http://$IP:$PORT --led-pin <BCM pin from your wiring>
  cd pi && python3 -m ghostbuild_pi --core http://$IP:$PORT --led-pin <N>

== G2 OPERATOR (on the laptop, G2 + phone paired) ==
  cd g2 && npx evenhub login                           # once
  BACKEND=http://$IP:$PORT make g2-pack                # -> g2/ghostbuild.ehpk
  BACKEND=http://$IP:$PORT make g2-dev                 # in another terminal
  make g2-qr                                           # scan with the Even app; phone must reach http://$IP:5173 AND http://$IP:$PORT
TXT
