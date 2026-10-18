"""Raspberry Pi bench probe: can the Pi tell an LED path is correct / backwards / open with digital pins only?

The Pi has no ADC, so instead of measuring a voltage we test conduction in both directions:
  forward: pin A drives HIGH, pin B is an input with pull-down -> B reads HIGH only if current flows A -> B
  reverse: pin B drives HIGH, pin A is an input with pull-down -> A reads HIGH only if current flows B -> A
An LED conducts one way, so: fwd only = correct, rev only = backwards, neither = open (part missing), both = short.
Safe by construction: the only current path ends in a high-impedance input (~50 kΩ pull-down), so even a bare LED
or a direct wire draws well under 1 mA.

Margin to confirm by measurement: the input reads HIGH above ~1.3 V, so 3.3 V minus the LED's forward voltage
at a few µA must clear that. Red/yellow LEDs (~1.6-1.8 V) pass comfortably; some green/blue LEDs (~2.4 V+) may not.

Usage on the Pi (BCM numbers):
  python3 probe.py --pair 17:23 --pair 27:23 --pair 22:23   # traffic-light module: R,Y,G each vs module GND on BCM23
  python3 probe.py --pair 17:27                              # breadboard: resistor + LED between BCM17 and BCM27
  python3 probe.py --pair 17:23 --light 17:23                # also light that LED for 2 s (B driven LOW as ground)
Gate: every state you can make by hand (correct, backwards, unplugged) reads right 10 of 10.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import RPi.GPIO as GPIO
except ImportError:  # not on a Pi
    sys.exit("RPi.GPIO not found: run this on the Raspberry Pi (sudo apt install python3-rpi.gpio)")

SETTLE_S = 0.002


def release(*pins: int) -> None:
    for p in pins:
        GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


def conducts(drive: int, sense: int) -> bool:
    release(drive, sense)
    GPIO.setup(drive, GPIO.OUT, initial=GPIO.HIGH)
    time.sleep(SETTLE_S)
    high = GPIO.input(sense) == GPIO.HIGH
    release(drive)
    return high


def classify(a: int, b: int) -> str:
    fwd, rev = conducts(a, b), conducts(b, a)
    return {(True, False): "correct", (False, True): "backwards", (False, False): "open", (True, True): "short"}[(fwd, rev)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", action="append", required=True, help="A:B in BCM numbers (LED anode side : cathode side)")
    ap.add_argument("--light", help="A:B to light for 2 s after probing (A HIGH, B LOW)")
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--count", type=int, default=0, help="samples to take (0 = until Ctrl-C)")
    args = ap.parse_args()
    pairs = [tuple(int(x) for x in p.split(":")) for p in args.pair]

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    try:
        if args.light:
            a, b = (int(x) for x in args.light.split(":"))
            release(a, b)
            GPIO.setup(b, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(a, GPIO.OUT, initial=GPIO.HIGH)
            time.sleep(2)
            release(a, b)
        seq = 0
        while args.count == 0 or seq < args.count:
            reading = {f"{a}:{b}": classify(a, b) for a, b in pairs}
            print(json.dumps({"seq": seq, "ms": int(time.monotonic() * 1000), "pairs": reading}), flush=True)
            seq += 1
            time.sleep(1 / args.hz)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
