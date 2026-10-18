"""python -m ghostbuild_pi --core http://<laptop>:8787 [...]"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from . import __version__
from .camera import FAKE_SCENARIOS, FakeCamera, detect_backends, make_backend
from .client import ObservationClient, Recorder, normalize_core_url
from .clock import Clock
from .features import FeatureExtractor, parse_roi
from .led import (ENV_ALLOWLIST, ENV_PIN, LedController, LedPinError, LedUnavailable, MotionLedRule,
                  open_driver, parse_allowlist, resolve_led_pin)
from .replay import load_jsonl, run_replay
from .runner import SEQ_RATE_CEILING_HZ, Station, dumps, run_loop

log = logging.getLogger("ghostbuild_pi")


class CliError(Exception):
    """Refusal or bad configuration; exit code 2."""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ghostbuild_pi", description="GhostBuild Pi station")
    p.add_argument("--core", help="core base URL, e.g. http://192.168.1.20:8787 (required unless --no-post)")
    p.add_argument("--dev", default="pi-01", help="device id (default pi-01)")
    p.add_argument("--hz", type=float, default=5.0, help="observations per second (0 < hz <= %d)" % SEQ_RATE_CEILING_HZ)
    p.add_argument("--source", choices=["pi_live", "simulated", "replay"], default=None,
                   help="override label; pi_live is refused with --fake-camera or --replay")
    p.add_argument("--roi", help="motion ROI as fractions of the frame: x0,y0,x1,y1 (default whole frame)")
    cam = p.add_argument_group("camera")
    cam.add_argument("--fake-camera", metavar="SCENARIO", choices=FAKE_SCENARIOS,
                     help="synthetic camera (%s); output is labelled simulated" % "|".join(FAKE_SCENARIOS))
    cam.add_argument("--replay", metavar="FILE.jsonl", help="replay a recording; output is labelled replay")
    cam.add_argument("--loop", action="store_true", help="loop the replay")
    cam.add_argument("--camera-backend", default="auto", choices=["auto", "picamera2", "opencv", "rpicam"])
    cam.add_argument("--camera-index", type=int, default=0)
    cam.add_argument("--width", type=int, default=640)
    cam.add_argument("--height", type=int, default=480)
    cam.add_argument("--motion-pixel-threshold", type=float, default=25.0,
                     help="abs luma diff (0..255) that counts as a changed pixel")
    cam.add_argument("--scene-change-luma", type=float, default=30.0,
                     help="mean-luma jump that stops motion counting (lens cover/uncover); tune from the spike")
    led = p.add_argument_group("led")
    led.add_argument("--led-pin", type=int, help="BCM GPIO number. Read it from the real wiring; never guess.")
    led.add_argument("--led-allowlist", help="comma list of BCM pins allowed when the pin comes from $%s" % ENV_PIN)
    led.add_argument("--led-active-low", action="store_true")
    led.add_argument("--dry-run-led", action="store_true", help="log LED commands instead of driving GPIO")
    led.add_argument("--led-on-motion", action=argparse.BooleanOptionalAction, default=True,
                     help="motion > 0.15 for >= 2 frames -> LED on for 2 s (default on)")
    out = p.add_argument_group("output")
    out.add_argument("--record", metavar="recordings/NAME.jsonl", help="append every observation to this JSONL")
    out.add_argument("--print", dest="print_obs", action="store_true", help="print each observation to stdout")
    out.add_argument("--no-post", action="store_true", help="do not contact a core")
    out.add_argument("--duration", type=float, help="stop after this many seconds")
    out.add_argument("--list-backends", action="store_true", help="print camera capability detection and exit")
    out.add_argument("-v", "--verbose", action="store_true")
    out.add_argument("--version", action="version", version=__version__)
    return p


def resolve_source(args: argparse.Namespace) -> str:
    """The honesty gate: fake data can never be pi_live."""
    if args.fake_camera and args.replay:
        raise CliError("--fake-camera and --replay are mutually exclusive")
    natural = "simulated" if args.fake_camera else "replay" if args.replay else "pi_live"
    if args.source is None:
        return natural
    if args.source == "pi_live" and natural != "pi_live":
        raise CliError("refusing --source pi_live with %s: that data is %s, not live"
                       % ("--fake-camera" if args.fake_camera else "--replay", natural))
    return args.source


def validate(args: argparse.Namespace) -> None:
    if not (0 < args.hz <= SEQ_RATE_CEILING_HZ):
        raise CliError("--hz must be > 0 and <= %d" % SEQ_RATE_CEILING_HZ)
    if not args.core and not args.no_post:
        raise CliError("--core is required (or pass --no-post)")


def build_led(args: argparse.Namespace, clock: Clock) -> Optional[LedController]:
    try:
        pin = resolve_led_pin(args.led_pin, os.environ.get(ENV_PIN),
                              parse_allowlist(args.led_allowlist or os.environ.get(ENV_ALLOWLIST)))
    except LedPinError as e:
        raise CliError(str(e))
    if pin is None and not args.dry_run_led:
        log.info("no LED pin configured: LED disabled, observations report led=null")
        return None
    try:
        driver = open_driver(pin, dry_run=args.dry_run_led, active_high=not args.led_active_low)
    except LedUnavailable as e:
        log.error("LED unavailable, continuing WITHOUT led: %s", e)
        return None
    return LedController(driver, clock)


def build_station(args: argparse.Namespace, source: str, clock: Clock) -> Station:
    roi = parse_roi(args.roi) if args.roi else None
    if args.fake_camera:
        camera = FakeCamera(args.fake_camera, clock)
    else:
        camera = make_backend(args.camera_backend, clock, (args.width, args.height), args.camera_index)
    led = build_led(args, clock)
    rule = MotionLedRule(led, enabled=args.led_on_motion) if led else None
    # A dry-run LED is not a real output: never report it as commanded GPIO on live data.
    report_led = bool(led) and (led.real or source != "pi_live")
    extractor = FeatureExtractor(roi=roi, motion_threshold=args.motion_pixel_threshold)
    return Station(camera, extractor, source, dev=args.dev, led=led, rule=rule, clock=clock,
                   report_led=report_led, scene_change_luma=args.scene_change_luma)


def _on_pi() -> bool:
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return b"Raspberry" in f.read()
    except OSError:
        return False


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if args.list_backends:
        print(json.dumps(detect_backends(), indent=2))
        return 0
    try:
        validate(args)
        source = resolve_source(args)
        if args.roi:
            parse_roi(args.roi)
    except (CliError, ValueError) as e:
        print("ghostbuild_pi: %s" % e, file=sys.stderr)
        return 2

    if source == "pi_live" and not _on_pi():
        log.warning("source is pi_live but this does not look like a Raspberry Pi; "
                    "do not present this as the Pi's camera")
    clock = Clock()
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    client: Optional[ObservationClient] = None
    if not args.no_post:
        client = ObservationClient(normalize_core_url(args.core), clock=clock)
        client.start()
    recorder = Recorder(args.record) if args.record else None

    def sink(obs: Dict[str, Any]) -> None:
        if client:
            client.submit(obs)
        if recorder:
            recorder.write(obs)
        if args.print_obs:
            print(dumps(obs), flush=True)

    station: Optional[Station] = None
    try:
        log.info("ghostbuild_pi %s source=%s dev=%s hz=%s core=%s", __version__, source, args.dev, args.hz,
                 args.core if client else "(none)")
        if args.replay:
            records = load_jsonl(args.replay)
            if not records:
                print("ghostbuild_pi: no usable observations in %s" % args.replay, file=sys.stderr)
                return 2
            n = run_replay(records, sink, clock, args.dev, stop.is_set, loop=args.loop, duration_s=args.duration)
        else:
            try:
                station = build_station(args, source, clock)
            except CliError as e:
                print("ghostbuild_pi: %s" % e, file=sys.stderr)
                return 2
            st = station.status()
            log.info("camera backend=%s open=%s error=%s led=%s", st["backend"], st["camera_open"], st["error"],
                     (station.led.driver.name if station.led else "none"))
            last_status = [time.monotonic()]

            def step_and_report() -> Dict[str, Any]:
                obs = station.step()
                if time.monotonic() - last_status[0] > 10:
                    last_status[0] = time.monotonic()
                    log.info("status %s core=%s", station.status()["backend"], client.stats() if client else "-")
                return obs

            n = run_loop(step_and_report, sink, clock, args.hz, stop.is_set, args.duration)
        log.info("emitted %d observations%s", n, ("; client %s" % client.stats()) if client else "")
        return 0
    finally:
        if station:
            station.close()  # LED is always driven off here
        if client:
            client.stop()
        if recorder:
            recorder.close()
