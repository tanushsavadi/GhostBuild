#!/usr/bin/env python3
"""GhostBuild Pi hardware spike. Run ON the Pi, by a human, with the camera and LED connected.

    python3 pi/tools/spike.py --core http://<laptop-ip>:8787 --led-pin <BCM> [--with-wave]

It prints a PASS / FAIL / WARN / SKIP report, saves 3 JPEGs and a JSON report to ./spike_out/, and
ends with a block to paste into hardware/WIRING.md. Nothing is assumed: every value is either
measured here, typed by you, or left as TODO. The LED result is HUMAN CONFIRMED only if you say so.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np  # noqa: E402

from ghostbuild_pi.camera import CameraError, _can_import, make_backend  # noqa: E402
from ghostbuild_pi.client import default_get, default_post  # noqa: E402
from ghostbuild_pi.clock import Clock  # noqa: E402
from ghostbuild_pi.features import FeatureExtractor, summarize  # noqa: E402
from ghostbuild_pi.led import LedController, LedPinError, LedUnavailable, open_driver, resolve_led_pin  # noqa: E402
from ghostbuild_pi.runner import initial_seq  # noqa: E402

FEATURES = ("mean_luma", "luma_std", "detail")
PHASES = (
    ("UNCOVERED", "Leave the lens UNCOVERED and aim the camera at the normal scene."),
    ("LENS COVERED", "COVER the lens completely (the paper flap / lens cover you will use in the demo)."),
    ("UNCOVERED AGAIN", "UNCOVER the lens again. Same scene as phase 1."),
)


class Env:
    """Everything that touches the outside world, replaceable in tests."""

    def __init__(self):
        self.ask: Callable[[str], str] = input
        self.out: Callable[[str], None] = lambda s: print(s, flush=True)
        self.clock = Clock()
        self.read_text: Callable[[str], Optional[str]] = self._read_text
        self.run_cmd: Callable[[List[str]], Optional[str]] = self._run_cmd
        self.which = shutil.which
        self.can_import = _can_import
        self.make_camera: Callable[[str], Any] = lambda backend: make_backend(backend, self.clock)
        self.open_driver = open_driver
        self.http_get = default_get
        self.http_post = default_post
        self.hostname = socket.gethostname()
        self.today = lambda: datetime.date.today().isoformat()

    @staticmethod
    def _read_text(path: str) -> Optional[str]:
        try:
            with open(path, "rb") as f:
                return f.read().decode("utf-8", "replace").strip("\x00\n ")
        except OSError:
            return None

    @staticmethod
    def _run_cmd(cmd: List[str]) -> Optional[str]:
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=20)
            return (p.stdout + p.stderr).decode("utf-8", "replace").strip()
        except Exception:
            return None


class Report:
    def __init__(self, env: Env):
        self.env = env
        self.items: List[Dict[str, str]] = []
        self.facts: Dict[str, Any] = {}

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.items.append({"name": name, "status": status, "detail": detail})
        self.env.out("[%s] %s%s" % (status, name, (" - " + detail) if detail else ""))

    def status_of(self, name: str) -> Optional[str]:
        for i in self.items:
            if i["name"] == name:
                return i["status"]
        return None


# --------------------------------------------------------------------------- steps
def step_system(env: Env, rep: Report) -> None:
    model = env.read_text("/proc/device-tree/model")
    osr = env.read_text("/etc/os-release") or ""
    pretty = next((l.split("=", 1)[1].strip('"') for l in osr.splitlines() if l.startswith("PRETTY_NAME=")), None)
    rep.facts.update(pi_model=model, os=pretty, python=platform.python_version(), kernel=platform.release())
    rep.add("Pi model", "PASS" if model and "Raspberry" in model else "WARN", model or "no /proc/device-tree/model (not a Pi?)")
    rep.add("OS", "PASS" if pretty else "WARN", pretty or "no /etc/os-release PRETTY_NAME")
    rep.add("Python", "PASS" if sys.version_info >= (3, 9) else "WARN", platform.python_version())


def step_imports(env: Env, rep: Report) -> None:
    mods = {m: env.can_import(m) for m in ("picamera2", "cv2", "numpy", "PIL", "gpiozero", "RPi.GPIO", "httpx")}
    exes = {e: env.which(e) for e in ("rpicam-hello", "libcamera-hello", "rpicam-still", "libcamera-still")}
    rep.facts.update(imports=mods, executables=exes)
    rep.add("camera backend: picamera2 importable", "PASS" if mods["picamera2"] else "WARN",
            "" if mods["picamera2"] else "sudo apt install python3-picamera2; venv needs --system-site-packages")
    rep.add("camera backend: OpenCV importable", "PASS" if mods["cv2"] else "WARN", "optional fallback")
    rep.add("camera backend: rpicam/libcamera-still on PATH", "PASS" if (exes["rpicam-still"] or exes["libcamera-still"]) else "WARN",
            "optional slow fallback")
    rep.add("LED library (gpiozero or RPi.GPIO)", "PASS" if (mods["gpiozero"] or mods["RPi.GPIO"]) else "FAIL",
            ", ".join(k for k in ("gpiozero", "RPi.GPIO") if mods[k]) or "sudo apt install python3-gpiozero")
    rep.add("httpx importable", "PASS" if mods["httpx"] else "WARN", "" if mods["httpx"] else "urllib fallback will be used")


def step_detect(env: Env, rep: Report) -> None:
    listing = None
    for exe in ("rpicam-hello", "libcamera-hello"):
        if env.which(exe):
            listing = env.run_cmd([exe, "--list-cameras"])
            rep.facts["list_cameras_cmd"] = exe
            break
    p2 = None
    if env.can_import("picamera2"):
        try:
            from picamera2 import Picamera2  # type: ignore

            p2 = [{k: str(v) for k, v in dict(i).items()} for i in Picamera2.global_camera_info()]
        except Exception as e:
            p2 = "error: %s" % e
    rep.facts.update(list_cameras_output=listing, picamera2_global_camera_info=p2)
    found_cli = bool(listing) and "available cameras" in listing.lower() and "no cameras" not in listing.lower()
    found_p2 = isinstance(p2, list) and len(p2) > 0
    detail = []
    if listing:
        detail.append("list-cameras: " + " | ".join(l.strip() for l in listing.splitlines()[:4]))
    if p2 is not None:
        detail.append("picamera2: %s" % (p2,))
    rep.add("camera detected by system", "PASS" if (found_cli or found_p2) else "FAIL",
            "; ".join(detail) or "no enumeration tool available; will still try to open it")


def save_image(path: str, frame: np.ndarray) -> str:
    """JPEG via Pillow or OpenCV, else binary PPM/PGM. Colour order may be R/B swapped; that is cosmetic."""
    arr = np.asarray(frame)
    try:
        from PIL import Image  # type: ignore

        Image.fromarray(arr.astype(np.uint8)).save(path, "JPEG")
        return path
    except ImportError:
        pass
    try:
        import cv2  # type: ignore

        cv2.imwrite(path, arr.astype(np.uint8))
        return path
    except ImportError:
        pass
    ppm = os.path.splitext(path)[0] + (".ppm" if arr.ndim == 3 else ".pgm")
    h, w = arr.shape[:2]
    with open(ppm, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (w, h) if arr.ndim == 3 else b"P5\n%d %d\n255\n" % (w, h))
        f.write(arr[:, :, :3].astype(np.uint8).tobytes() if arr.ndim == 3 else arr.astype(np.uint8).tobytes())
    return ppm


def open_camera(env: Env, rep: Report, backend: str):
    cam = env.make_camera(backend)
    try:
        cam.open()
    except Exception as e:
        rep.add("camera opens (%s)" % backend, "FAIL", str(e))
        return None
    info = cam.info()
    rep.facts["camera_backend"] = cam.name
    rep.facts["camera_info"] = info
    rep.add("camera opens (%s)" % backend, "PASS", "backend in use: %s %s" % (cam.name, json.dumps(info, default=str)[:300]))
    return cam


def step_capture(env: Env, rep: Report, cam, args, out_dir: str) -> None:
    frames: List[np.ndarray] = []
    last_ts: Optional[float] = None
    new = 0
    t0 = env.clock.now_ms()
    deadline = t0 + args.capture_timeout * 1000
    while new < args.frames and env.clock.now_ms() < deadline:
        try:
            res = cam.read()
        except Exception as e:
            rep.add("capture %d frames" % args.frames, "FAIL", "read raised: %s" % e)
            return
        if res is None:
            env.clock.sleep(0.05)
            continue
        frame, ts = res
        if last_ts is None or ts > last_ts:
            new += 1
            last_ts = ts
            frames.append(frame)
        else:
            env.clock.sleep(0.02)
    elapsed = max((env.clock.now_ms() - t0) / 1000.0, 1e-9)
    fps = new / elapsed
    rep.facts.update(frames_captured=new, capture_seconds=round(elapsed, 2), fps=round(fps, 2),
                     frame_shape=list(frames[0].shape) if frames else None)
    if new < args.frames:
        rep.add("capture %d frames" % args.frames, "FAIL", "only %d new frames in %.1fs" % (new, elapsed))
        if not frames:
            return
    else:
        rep.add("capture %d frames" % args.frames, "PASS", "shape %s" % (frames[0].shape,))
    rep.add("frame rate", "PASS" if fps >= 5 else "WARN" if fps >= 2 else "FAIL",
            "%.1f new frames/s measured (the station defaults to --hz 5)" % fps)
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for tag, f in (("first", frames[0]), ("middle", frames[len(frames) // 2]), ("last", frames[-1])):
        try:
            saved.append(save_image(os.path.join(out_dir, "frame_%s.jpg" % tag), f))
        except Exception as e:
            rep.add("save JPEG %s" % tag, "WARN", str(e))
    if saved:
        rep.facts["saved_images"] = saved
        rep.add("saved images", "PASS", ", ".join(saved) + "  (look at them: is the view what you expect?)")


def collect_phase(env: Env, cam, args) -> Dict[str, List[float]]:
    ex = FeatureExtractor()
    env.clock.sleep(args.settle)  # let auto-exposure settle after the change
    vals: Dict[str, List[float]] = {k: [] for k in FEATURES + ("motion",)}
    end = env.clock.now_ms() + args.phase_seconds * 1000
    last_ts: Optional[float] = None
    while env.clock.now_ms() < end:
        res = cam.read()
        if res is None:
            env.clock.sleep(0.1)
            continue
        frame, ts = res
        if last_ts is None or ts > last_ts:
            last_ts = ts
            f = ex.process(frame)
            for k in vals:
                vals[k].append(getattr(f, k))
        env.clock.sleep(0.1)
    return vals


def analyze_separation(unc: List[float], cov: List[float]) -> Dict[str, Any]:
    if not unc or not cov:
        return {"separable": False}
    covered_below = float(np.median(cov)) < float(np.median(unc))
    if covered_below:
        gap, thr = min(unc) - max(cov), (min(unc) + max(cov)) / 2.0
    else:
        gap, thr = min(cov) - max(unc), (max(unc) + min(cov)) / 2.0
    return {"direction": "covered below threshold" if covered_below else "covered above threshold",
            "gap": gap, "midpoint": thr, "separable": gap > 0,
            "uncovered": summarize(unc), "covered": summarize(cov)}


def would_trigger(motions: List[float], luma: List[float], thr: float = 0.15, frames: int = 2, scene_luma: float = 30.0) -> bool:
    """Replay the station's LED rule over measured values (no LED involved)."""
    run = 0
    for i, m in enumerate(motions):
        jump = i > 0 and abs(luma[i] - luma[i - 1]) > scene_luma
        run = run + 1 if (m > thr and not jump) else 0
        if run >= frames:
            return True
    return False


def step_phases(env: Env, rep: Report, cam, args) -> None:
    data: List[Dict[str, List[float]]] = []
    for n, (name, msg) in enumerate(PHASES, 1):
        env.out("\n=== PHASE %d/3: %s ===\n%s" % (n, name, msg))
        try:
            env.ask("Press Enter when ready (then hold still for ~%ds)... " % args.phase_seconds)
        except EOFError:
            rep.add("guided phases", "FAIL", "stdin closed: run this in an interactive terminal")
            return
        try:
            d = collect_phase(env, cam, args)
        except Exception as e:
            rep.add("phase %s" % name, "FAIL", "capture failed: %s" % e)
            return
        data.append(d)
        s = {k: summarize(d[k]) for k in d}
        env.out("  frames=%d  " % s["mean_luma"]["n"] + "  ".join(
            "%s min/med/max = %.2f/%.2f/%.2f" % (k, s[k]["min"], s[k]["median"], s[k]["max"]) for k in FEATURES if s[k]["n"]))
        rep.facts.setdefault("phases", {})[name] = s
        if not d["mean_luma"]:
            rep.add("phase %s" % name, "FAIL", "no frames")
            return
    unc = {k: data[0][k] + data[2][k] for k in FEATURES}
    cov = {k: data[1][k] for k in FEATURES}
    results = {k: analyze_separation(unc[k], cov[k]) for k in FEATURES}
    rep.facts["separation"] = results
    env.out("\n--- threshold suggestions derived ONLY from this run (you decide; re-run if the scene changes) ---")
    for k, r in results.items():
        if not r.get("direction"):
            continue
        env.out("  %-9s %s: uncovered [%.2f..%.2f]  covered [%.2f..%.2f]  gap=%.2f  midpoint=%.2f  %s" % (
            k, r["direction"], r["uncovered"]["min"], r["uncovered"]["max"], r["covered"]["min"], r["covered"]["max"],
            r["gap"], r["midpoint"], "SEPARABLE" if r["separable"] else "OVERLAP - not usable alone"))
    # consistency between the two uncovered phases (scene/exposure drift)
    ml1, ml3 = float(np.median(data[0]["mean_luma"])), float(np.median(data[2]["mean_luma"]))
    drift = abs(ml1 - ml3) / max(ml1, 1e-9)
    rep.facts["uncovered_phase_median_mean_luma"] = [ml1, ml3]
    usable = [k for k, r in results.items() if r.get("separable")]
    if usable:
        rep.add("covered vs uncovered separable", "PASS", "features with a clean gap: " + ", ".join(usable))
    else:
        rep.add("covered vs uncovered separable", "FAIL", "no feature separates the phases; check lens cover, scene, lighting")
    rep.add("uncovered phases consistent", "PASS" if drift < 0.25 else "WARN",
            "median mean_luma %.1f then %.1f (%.0f%% apart)" % (ml1, ml3, drift * 100))
    if args.with_wave:
        step_wave(env, rep, cam, args, data)


def step_wave(env: Env, rep: Report, cam, args, data) -> None:
    env.out("\n=== PHASE 4 (optional): WAVE ===\nWave your hand in front of the camera for the whole phase.")
    try:
        env.ask("Press Enter when ready... ")
    except EOFError:
        rep.add("wave phase", "FAIL", "stdin closed")
        return
    wave = collect_phase(env, cam, args)
    idle_trig = any(would_trigger(d["motion"], d["mean_luma"]) for d in (data[0], data[2]))
    wave_trig = would_trigger(wave["motion"], wave["mean_luma"])
    s_idle = summarize(data[0]["motion"] + data[2]["motion"])
    s_wave = summarize(wave["motion"])
    rep.facts["motion"] = {"idle": s_idle, "wave": s_wave, "idle_would_trigger": idle_trig, "wave_would_trigger": wave_trig}
    env.out("  motion idle min/med/max = %.3f/%.3f/%.3f   wave = %.3f/%.3f/%.3f" % (
        s_idle["min"], s_idle["median"], s_idle["max"], s_wave["min"], s_wave["median"], s_wave["max"]))
    rep.add("wave triggers the LED rule (motion>0.15, 2 frames)", "PASS" if wave_trig else "FAIL",
            "rule replayed over measured motion; no LED involved")
    rep.add("idle phases do not trigger the LED rule", "PASS" if not idle_trig else "FAIL",
            "idle motion max %.3f" % s_idle["max"])


def step_led(env: Env, rep: Report, args) -> None:
    if args.dry_run_led:
        rep.add("LED blink", "SKIP", "dry-run is not hardware")
        return
    if args.led_pin is None:
        rep.add("LED blink", "SKIP", "no --led-pin. Read the BCM number from the physical wiring (never guess), then re-run.")
        return
    try:
        pin = resolve_led_pin(args.led_pin)
        driver = env.open_driver(pin, dry_run=False, active_high=not args.led_active_low)
    except (LedPinError, LedUnavailable) as e:
        rep.add("LED blink", "FAIL", str(e))
        return
    led = LedController(driver, env.clock)
    try:
        env.out("\nBlinking the LED on BCM %d three times. Watch it." % pin)
        for _ in range(3):
            led.set(True, "spike")
            env.clock.sleep(0.4)
            led.set(False, "spike")
            env.clock.sleep(0.4)
    finally:
        led.shutdown()
    try:
        ans = env.ask("Did you SEE the LED blink 3 times? [y/N] ").strip().lower()
    except EOFError:
        ans = ""
    rep.facts["led_pin_bcm"] = pin
    if ans in ("y", "yes"):
        rep.facts["led_human_confirmed"] = True
        rep.add("LED blink", "PASS", "BCM %d HUMAN CONFIRMED (you saw it)" % pin)
    else:
        rep.facts["led_human_confirmed"] = False
        rep.add("LED blink", "FAIL", "BCM %d NOT confirmed. Commands were sent, but a GPIO write is not light." % pin)


def step_core(env: Env, rep: Report, args, last_feats: Optional[Dict[str, Any]]) -> None:
    if not args.core:
        rep.add("core reachable", "SKIP", "no --core http://<laptop-ip>:8787")
        return
    base = args.core.rstrip("/")
    if "://" not in base:
        base = "http://" + base
    try:
        status, text = env.http_get(base + "/health", 3.0)
        if 200 <= status < 300:
            rep.add("core GET /health", "PASS", "HTTP %d %s" % (status, text[:200].replace("\n", " ")))
        else:
            rep.add("core GET /health", "FAIL", "HTTP %d" % status)
    except Exception as e:
        rep.add("core GET /health", "FAIL", "%s: %s (same Wi-Fi? firewall? core running on 0.0.0.0?)" % (type(e).__name__, e))
        return
    cam_obs = None
    if last_feats:
        cam_obs = {"frame_seq": 1, "frame_age_ms": 0, "mean_luma": last_feats["mean_luma"], "luma_std": last_feats["luma_std"],
                   "detail": last_feats["detail"], "motion": 0.0, "marker_found": None, "marker_id": None}
    obs = {"v": 2, "dev": "spike-" + env.hostname[:24], "seq": initial_seq(env.clock.wall_ms()) + 1,
           "ms": int(env.clock.now_ms()), "at": env.clock.wall_ms(),
           "source": "simulated",  # deliberately NOT pi_live: this is a connectivity probe
           "camera": cam_obs, "led": None, "error": None if cam_obs else "spike_no_camera"}
    try:
        status = env.http_post(base + "/observation", json.dumps(obs).encode(), 3.0)
        rep.add("core POST /observation accepted", "PASS" if 200 <= status < 300 else "FAIL",
                "HTTP %d (probe labelled source=simulated, dev=%s)" % (status, obs["dev"]))
    except Exception as e:
        rep.add("core POST /observation accepted", "FAIL", "%s: %s" % (type(e).__name__, e))


# --------------------------------------------------------------------------- output
def wiring_block(rep: Report, args, env: Env) -> str:
    f = rep.facts
    sep = f.get("separation", {})
    thr = "; ".join("%s: %s, midpoint %.2f (uncovered min %.2f / covered max %.2f)" % (
        k, v["direction"], v["midpoint"], v["uncovered"]["min"], v["covered"]["max"])
        for k, v in sep.items() if v.get("separable")) or "TODO (no clean separation measured)"
    led = f.get("led_pin_bcm")
    cam_text = (f.get("list_cameras_output") or f.get("picamera2_global_camera_info") or "TODO")
    cam_text = " ".join(str(cam_text).split())[:240]
    lines = [
        "<!-- paste into hardware/WIRING.md; generated by pi/tools/spike.py on %s -->" % env.today(),
        "| Field | Value | Source |",
        "|---|---|---|",
        "| Pi model | %s | MEASURED LIVE (/proc/device-tree/model) |" % (f.get("pi_model") or "TODO"),
        "| OS | %s | MEASURED LIVE (/etc/os-release) |" % (f.get("os") or "TODO"),
        "| Python | %s | MEASURED LIVE |" % f.get("python", "TODO"),
        "| Camera as reported by the system | %s | MEASURED LIVE |" % cam_text,
        "| Camera backend that opened | %s | MEASURED LIVE |" % (f.get("camera_backend") or "TODO (did not open)"),
        "| Measured fps (new frames) | %s | MEASURED LIVE |" % f.get("fps", "TODO"),
        "| LED pin (BCM) | %s | %s |" % (led if led is not None else "TODO", "HUMAN CONFIRMED" if f.get("led_human_confirmed") else "TODO (not confirmed by a human)"),
        "| LED active level | %s | HUMAN-ENTERED |" % ("low" if args.led_active_low else "TODO (spike assumed active-high)"),
        "| Lens-covered thresholds (this run only) | %s | MEASURED LIVE (derived) |" % thr,
        "| Core reachable from Pi | %s | MEASURED LIVE |" % (rep.status_of("core GET /health") or "TODO"),
        "| Camera mount / ribbon / field of view | TODO | HUMAN-ENTERED |",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None, env: Optional[Env] = None) -> int:
    ap = argparse.ArgumentParser(description="GhostBuild Pi hardware spike (run on the Pi)")
    ap.add_argument("--core", help="core URL, e.g. http://192.168.1.20:8787")
    ap.add_argument("--led-pin", type=int, help="BCM number read from the physical wiring")
    ap.add_argument("--led-active-low", action="store_true")
    ap.add_argument("--dry-run-led", action="store_true")
    ap.add_argument("--backend", default="auto", choices=["auto", "picamera2", "opencv", "rpicam"])
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--capture-timeout", type=float, default=30.0)
    ap.add_argument("--phase-seconds", type=float, default=3.0)
    ap.add_argument("--settle", type=float, default=1.5, help="seconds to wait after Enter before sampling")
    ap.add_argument("--with-wave", action="store_true", help="add a hand-wave phase to check the motion threshold")
    ap.add_argument("--out", default="spike_out")
    args = ap.parse_args(argv)
    env = env or Env()
    rep = Report(env)

    env.out("GhostBuild Pi spike - %s on %s" % (env.today(), env.hostname))
    step_system(env, rep)
    step_imports(env, rep)
    step_detect(env, rep)
    cam = open_camera(env, rep, args.backend)
    last_feats = None
    if cam is not None:
        try:
            step_capture(env, rep, cam, args, args.out)
            res = cam.read()
            if res is not None:
                f = FeatureExtractor().process(res[0])
                last_feats = {"mean_luma": f.mean_luma, "luma_std": f.luma_std, "detail": f.detail}
            step_phases(env, rep, cam, args)
        finally:
            cam.close()
    step_led(env, rep, args)
    step_core(env, rep, args, last_feats)

    must = ["camera opens (%s)" % args.backend, "capture %d frames" % args.frames, "covered vs uncovered separable"]
    overall = all(rep.status_of(n) == "PASS" for n in must)
    env.out("\n=========== SUMMARY ===========")
    for i in rep.items:
        env.out("%-5s %s" % (i["status"], i["name"]))
    env.out("OVERALL (camera opens + captures + covered/uncovered separable): %s" % ("PASS" if overall else "FAIL"))
    env.out("LED and core are reported separately above (SKIP means not tested, not passed).")
    block = wiring_block(rep, args, env)
    env.out("\n=========== PASTE INTO hardware/WIRING.md ===========\n" + block + "\n=====================================================")
    try:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "spike_report.json"), "w") as fh:
            json.dump({"items": rep.items, "facts": rep.facts, "overall": overall}, fh, indent=2, default=str)
        with open(os.path.join(args.out, "wiring_block.md"), "w") as fh:
            fh.write(block + "\n")
    except OSError as e:
        env.out("could not write report files: %s" % e)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
