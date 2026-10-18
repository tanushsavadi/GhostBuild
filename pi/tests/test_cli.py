import json

import pytest

from contracts.models import Observation
from ghostbuild_pi.cli import main


def run_cli(capsys, *argv):
    rc = main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_refuses_pi_live_with_fake_camera(capsys):
    rc, out, err = run_cli(capsys, "--no-post", "--fake-camera", "clear", "--source", "pi_live", "--duration", "1")
    assert rc == 2 and "refusing" in err and out == ""


def test_refuses_pi_live_with_replay(capsys, tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text("{}")
    rc, _, err = run_cli(capsys, "--no-post", "--replay", str(f), "--source", "pi_live")
    assert rc == 2 and "refusing" in err


def test_fake_camera_emits_simulated_and_valid_contract(capsys):
    rc, out, _ = run_cli(capsys, "--no-post", "--fake-camera", "wave", "--print", "--hz", "10", "--duration", "0.6",
                         "--dry-run-led")
    assert rc == 0
    lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert lines
    for o in lines:
        Observation.model_validate(o)
        assert o["source"] == "simulated"
    seqs = [o["seq"] for o in lines]
    assert seqs == sorted(set(seqs))


def test_real_camera_defaults_to_pi_live_and_nulls_when_no_camera(capsys):
    rc, out, _ = run_cli(capsys, "--no-post", "--print", "--camera-backend", "picamera2", "--duration", "0.3", "--hz", "10")
    lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert rc == 0 and lines
    assert all(o["source"] == "pi_live" and o["camera"] is None and o["error"] == "camera_open_failed" for o in lines)


def test_dry_run_led_hidden_on_live_data_but_shown_on_simulated(capsys):
    _, out, _ = run_cli(capsys, "--no-post", "--print", "--camera-backend", "picamera2", "--dry-run-led",
                        "--duration", "0.2", "--hz", "10")
    assert all(json.loads(l)["led"] is None for l in out.splitlines() if l.startswith("{"))
    _, out, _ = run_cli(capsys, "--no-post", "--print", "--fake-camera", "clear", "--dry-run-led", "--duration", "0.2",
                        "--hz", "10")
    assert all(json.loads(l)["led"] is not None for l in out.splitlines() if l.startswith("{"))


def test_requires_core_unless_no_post(capsys):
    rc, _, err = run_cli(capsys, "--fake-camera", "clear")
    assert rc == 2 and "--core" in err


@pytest.mark.parametrize("bad", [["--hz", "0"], ["--hz", "50"], ["--roi", "1,2,3"], ["--led-pin", "99", "--dry-run-led"]])
def test_bad_args_exit_2(capsys, bad):
    rc, _, _ = run_cli(capsys, "--no-post", "--fake-camera", "clear", "--duration", "0.2", *bad)
    assert rc == 2


def test_record_then_replay_roundtrip_is_labelled_replay(capsys, tmp_path):
    rec = tmp_path / "rec.jsonl"
    rc, _, _ = run_cli(capsys, "--no-post", "--fake-camera", "wave", "--dry-run-led", "--hz", "10", "--duration", "1.0",
                       "--record", str(rec))
    assert rc == 0
    recorded = [json.loads(l) for l in rec.read_text().splitlines()]
    assert recorded and all(r["source"] == "simulated" for r in recorded)
    rc, out, _ = run_cli(capsys, "--no-post", "--print", "--replay", str(rec))
    assert rc == 0
    replayed = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert len(replayed) == len(recorded)
    for o, r in zip(replayed, recorded):
        Observation.model_validate(o)
        assert o["source"] == "replay" and o["camera"] == r["camera"]
    assert [o["seq"] for o in replayed] == sorted({o["seq"] for o in replayed})


def test_replay_loop_keeps_frame_seq_increasing(tmp_path):
    from ghostbuild_pi.clock import FakeClock
    from ghostbuild_pi.replay import replay_observations

    recs = [{"ms": i * 100, "camera": {"frame_seq": 10 + i}, "led": None, "error": None} for i in range(3)]
    gen = replay_observations(recs, "pi-01", FakeClock(), loop=True)
    fs = [next(gen)[1]["camera"]["frame_seq"] for _ in range(9)]
    assert fs == sorted(set(fs)) and len(fs) == 9


def test_list_backends(capsys):
    rc, out, _ = run_cli(capsys, "--list-backends")
    assert rc == 0 and "picamera2_importable" in json.loads(out)
