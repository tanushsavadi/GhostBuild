import pytest

from ghostbuild_pi.camera import (AutoCamera, CameraOpenError, FakeCamera, FAKE_SCENARIOS, detect_backends,
                                  make_backend)
from ghostbuild_pi.clock import FakeClock


def test_all_scenarios_exist():
    assert set(FAKE_SCENARIOS) == {"blocked", "clear", "flicker", "frozen", "disconnect", "wave"}
    with pytest.raises(ValueError):
        FakeCamera("nope", FakeClock())


def test_frame_shape_and_timestamp():
    clock = FakeClock()
    cam = FakeCamera("clear", clock)
    cam.open()
    frame, ts = cam.read()
    assert frame.shape == (240, 320, 3) and frame.dtype.name == "uint8" and ts == clock.now_ms()


def test_frozen_returns_identical_frame_and_timestamp():
    clock = FakeClock()
    cam = FakeCamera("frozen", clock)
    cam.open()
    a = cam.read()
    clock.advance(500)
    b = cam.read()
    assert b[1] == a[1] and (b[0] == a[0]).all()


def test_disconnect_returns_none_and_cannot_reopen():
    clock = FakeClock()
    cam = FakeCamera("disconnect", clock, disconnect_after_ms=100)
    cam.open()
    assert cam.read() is not None
    clock.advance(200)
    assert cam.read() is None
    cam.close()
    with pytest.raises(CameraOpenError):
        cam.open()


def test_read_before_open_raises():
    with pytest.raises(Exception):
        FakeCamera("clear", FakeClock()).read()


def test_auto_reports_why_nothing_opened_on_a_laptop():
    cam = AutoCamera(FakeClock(), order=("picamera2",))
    with pytest.raises(CameraOpenError) as e:
        cam.open()
    assert "picamera2" in str(e.value)
    assert cam.info()["tried"]


def test_auto_exposes_active_backend_name():
    class Ok:
        name = "ok-backend"

        def open(self):
            pass

        def read(self):
            return None

        def close(self):
            pass

        def info(self):
            return {"backend": self.name}

    import ghostbuild_pi.camera as camera

    orig = camera.make_backend
    camera.make_backend = lambda *a, **k: Ok()
    try:
        cam = AutoCamera(FakeClock(), order=("picamera2",))
        assert cam.name == "auto"
        cam.open()
        assert cam.name == "ok-backend" and cam.info()["backend"] == "ok-backend"
    finally:
        camera.make_backend = orig


def test_unknown_backend_and_detect():
    with pytest.raises(ValueError):
        make_backend("x", FakeClock())
    d = detect_backends()
    assert {"picamera2_importable", "cv2_importable", "rpicam_still"} <= set(d)
