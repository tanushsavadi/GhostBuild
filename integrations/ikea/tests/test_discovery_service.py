"""Real cached manual through the generic runtime; fake providers for network state transitions."""

import time
from pathlib import Path
from threading import Event
import pytest
from fastapi.testclient import TestClient
from contracts.models import G2Hello, G2Input, GoalRequest
from ghostbuild_core.cards import load_cards
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.discovery.service import ProductDiscoveryService
from ghostbuild_core.discovery.source import SearchResult, LookupResult
from ghostbuild_core.server import create_app
from integrations.ikea.source import IkeaSource

ROOT = Path(__file__).resolve().parents[3]
DEMO = "I have a white IKEA desk with a drawer and cabinet"


class Source(IkeaSource):
    def __init__(self):
        super().__init__(ROOT)
        self.searches = []
        self.exacts = []
        self.live = False
        self.out = SearchResult()
        self.gate = None

    def live_available(self):
        return self.live

    def search(self, query, timeout_s, exclude):
        self.searches.append(query)
        if self.gate:
            self.gate.wait(1)
        return self.out

    def lookup(self, claim, timeout_s):
        self.exacts.append(claim)
        return LookupResult(
            record=self.record_for(claim.article), ms=2, origin="saved record"
        )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GB_ASSISTANT", "0")
    monkeypatch.setenv("GB_LIVE_RESEARCH", "0")
    clock = ManualClock(0)
    rt = Runtime(
        load_cards(ROOT / "knowledge/cards"),
        asset_root=ROOT,
        log_dir=tmp_path,
        clock=clock,
        brain=False,
    )
    src = Source()
    d = ProductDiscoveryService(rt, [src], path=tmp_path / "discovery.json", live=True)
    rt.hello(G2Hello(client_id="test"))
    clock.advance(2600)
    rt.tick()
    yield rt, d, src
    rt.close()


def say(rt, text):
    return rt.resolve_goal(
        GoalRequest(
            session_id=rt.session().id, mode="build", via="phone_text", text=text
        )
    )


def wait(d, predicate):
    end = time.monotonic() + 2
    while time.monotonic() < end:
        d.pump()
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


def phase(rt, d):
    return d.state(rt.session().id).phase


def test_full_demo_script(env):
    rt, d, src = env
    say(rt, DEMO)
    sid = rt.session().id
    assert len(d.state(sid).candidates) == 5
    assert d.state(sid).candidates[0].record.article == "80213074"
    assert not src.searches and not src.exacts
    assert (
        rt.hud.current.image.guide_id == "product_matches"
        and rt.session().phase == "menu"
    )
    say(rt, "It's the MICKE")
    assert phase(rt, d) == "configuring"
    say(rt, "Cabinet on the left")
    assert phase(rt, d) == "ready"
    assert rt.playbook.index == 0 and not rt.playbook.confirmed
    rt.ask("Show me step 14")
    assert rt.playbook.index == 13 and not rt.playbook.confirmed
    answer = rt.ask("Which fastener do I use?")
    assert (
        "8x cam lock 103430" in answer.text
        and "Do not use cam lock 110126" in answer.text
    )
    assert rt.playbook.help_view() == "how"
    assert rt.hud.current.image.url.endswith("/how.png")
    rt.ask("Show me a closer look")
    assert rt.playbook.help_view() == "how"
    rt.ask("Okay, done. What's next?")
    assert rt.playbook.index == 14 and rt.playbook.confirmed == ["s14"]
    assert d.state(sid).config == {"cabinet_side": "left"}
    assert any(e.label == "HUMAN CONFIRMED" for e in rt.playbook.events)


@pytest.mark.parametrize("text", ["the first one", "number one", "It's the MICKE"])
def test_selection_forms(env, text):
    rt, d, _ = env
    say(rt, DEMO)
    say(rt, text)
    assert phase(rt, d) == "configuring"


def test_ambiguous_name_needs_variant(env):
    rt, d, _ = env
    say(rt, "Help me assemble an IKEA MICKE desk")
    say(rt, "It's the MICKE")
    assert phase(rt, d) == "choosing"
    assert d.state(rt.session().id).selected is None
    assert all(c.record.name == "MICKE" for c in d.state(rt.session().id).candidates)


def test_refine_merges_and_number_prompt(env):
    rt, d, _ = env
    say(rt, DEMO)
    say(rt, "mine has two drawers")
    s = d.state(rt.session().id)
    assert (
        s.attrs.features["drawer"] == 2
        and s.attrs.features["cabinet"] is True
        and s.attrs.color == "white"
    )
    before = s.attrs.model_dump()
    say(rt, "I found the product number")
    assert s.attrs.model_dump() == before and "article number" in s.message


def test_none_asks_only_unknown_attribute(env):
    rt, d, _ = env
    say(rt, "Help me assemble an IKEA white desk")
    say(rt, "none of those")
    s = d.state(rt.session().id)
    if s.question:
        assert s.question.feature not in s.attrs.features
        say(rt, s.question.options[0])
        assert phase(rt, d) == "choosing"
    else:
        assert phase(rt, d) == "no_match"


def test_more_skips_seen_and_cancel(env):
    rt, d, _ = env
    say(rt, DEMO)
    s = d.state(rt.session().id)
    old = {c.record.article for c in s.candidates}
    say(rt, "show me more")
    assert not old.intersection(c.record.article for c in s.candidates)
    d.cancel(rt.session().id)
    assert phase(rt, d) == "idle"


@pytest.mark.parametrize(
    "reference", ["80213074", "https://www.ikea.com/us/en/p/micke-desk-white-80213074/"]
)
def test_exact_lookup_before_search_or_cache(env, reference):
    rt, d, src = env
    src.live = True
    say(rt, "Help me assemble IKEA " + reference)
    wait(d, lambda: phase(rt, d) == "confirming")
    assert len(src.exacts) == 1 and not src.searches
    assert d.state(rt.session().id).pending.record.article == "80213074"
    say(rt, "yes")
    assert phase(rt, d) == "configuring"


def test_missing_exact(env):
    rt, d, _ = env
    say(rt, "Help me assemble IKEA 11111111")
    wait(d, lambda: phase(rt, d) == "no_match")


def test_unavailable_no_cache_match(env):
    rt, d, src = env
    src._records = {}
    say(rt, "Help me assemble an IKEA wardrobe")
    assert phase(rt, d) == "unavailable"


def test_live_results_pumped_without_reordering(env):
    rt, d, src = env
    src.live = True
    src.out = SearchResult(
        records=src.cached()[-4:], search_ms=12, validate_ms=8, provider="FAKE"
    )
    say(rt, DEMO)
    d.refresh_search(rt.session().id)
    s = d.state(rt.session().id)
    old = [c.record.article for c in s.candidates]
    assert s.live_state == "running"
    wait(d, lambda: s.live_state == "done")
    assert [
        c.record.article for c in s.candidates
    ] == old and s.timings.provider == "FAKE"


@pytest.mark.parametrize(
    "error,unavailable", [("search timed out", False), ("not configured", True)]
)
def test_search_failure_keeps_cache(env, error, unavailable):
    rt, d, src = env
    src.live = True
    src.out = SearchResult(error=error, unavailable=unavailable)
    say(rt, DEMO)
    d.refresh_search(rt.session().id)
    s = d.state(rt.session().id)
    wait(d, lambda: s.live_state != "running")
    assert s.candidates and s.notice == error


def test_worker_timeout_and_stale_completion(env):
    rt, d, src = env
    src.live = True
    src.gate = Event()
    d.timeout_s = 0.01
    say(rt, DEMO)
    d.refresh_search(rt.session().id)
    s = d.state(rt.session().id)
    time.sleep(0.02)
    d.pump()
    assert s.live_state == "failed" and s.candidates
    d.cancel(s.session_id)
    src.gate.set()
    time.sleep(0.02)
    d.pump()
    assert phase(rt, d) == "idle"


def test_remember_configuration_new_session_and_restart(env, tmp_path):
    rt, d, src = env
    say(rt, DEMO)
    say(rt, "It's the MICKE")
    say(rt, "Cabinet on the right")
    sid = rt.session().id
    rt.hello(G2Hello(client_id="next-user"))
    rt.clock.advance(2600)
    rt.tick()
    assert rt.session().id != sid
    say(rt, DEMO)
    say(rt, "It's the MICKE")
    assert phase(rt, d) == "ready"
    assert rt.active_card.card_id.endswith("_right")
    rt.ask("show me step 14")
    other = Runtime(
        load_cards(ROOT / "knowledge/cards"),
        asset_root=ROOT,
        log_dir=tmp_path,
        clock=rt.clock,
        brain=False,
    )
    try:
        fresh = ProductDiscoveryService(
            other, [Source()], path=tmp_path / "discovery.json", live=False
        )
        assert other.playbook.index == 13 and other.active_card.card_id.endswith(
            "_right"
        )
        assert fresh.remembered["ikea:80213074"] == {"cabinet_side": "right"}
    finally:
        other.close()


def test_g2_list_focus_selection_config_and_back(env):
    rt, d, _ = env
    say(rt, DEMO)
    sid = rt.session().id

    def gesture(g):
        rt.handle_input(G2Input(gesture=g, seq_seen=rt.hud.current.seq))

    gesture("press")
    assert rt.hud.current.mode == "visual" and d.state(sid).focus == 0
    gesture("swipe_down")
    assert d.state(sid).focus == 1
    gesture("swipe_up")
    assert d.state(sid).focus is None
    gesture("press")
    gesture("press")
    assert phase(rt, d) == "configuring"
    gesture("press")
    assert phase(rt, d) == "ready" and rt.playbook.index == 0


def test_g2_second_page_and_cancel(env):
    rt, d, _ = env
    say(rt, DEMO)

    def g(t):
        rt.handle_input(G2Input(gesture=t, seq_seen=rt.hud.current.seq))

    for _ in range(3):
        g("swipe_down")
    g("press")
    assert (
        d.state(rt.session().id).page == 1
        and rt.hud.current.image.guide_id == "product_matches"
    )
    g("swipe_up")
    assert phase(rt, d) == "idle"


def test_endpoint_flow_and_asset_boundaries(env):
    rt, d, _ = env
    with TestClient(create_app(rt, tick_interval=None)) as client:
        sid = rt.session().id
        say(rt, DEMO)
        state = client.get("/discovery/state").json()
        assert state["phase"] == "choosing"
        assert client.get(rt.hud.current.image.url).status_code == 200
        assert (
            client.post(
                "/discovery/select", json={"session_id": "old", "article": "80213074"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/discovery/select", json={"session_id": sid, "article": "invented"}
            ).status_code
            == 409
        )
        for c in state["candidates"]:
            rec = c["record"]
            im = client.get(f"/discovery/img/ikea/{rec['article']}.png")
            assert im.status_code == 200
        assert client.get("/discovery/img/ikea/80213074.g2.png").status_code == 200
        client.post(
            "/discovery/select", json={"session_id": sid, "article": "80213074"}
        )
        assert (
            client.get(
                "/discovery/assets/ikea/80213074/config_left.phone.png"
            ).status_code
            == 200
        )
        assert (
            client.get("/discovery/assets/ikea/80213074/bundle.json").status_code == 404
        )
        assert (
            client.get(
                "/discovery/assets/ikea/80213074/%2e%2e%2findex.json"
            ).status_code
            == 404
        )
        client.post("/discovery/config", json={"session_id": sid, "option": "left"})
        assert client.get("/card").json()["card_id"].endswith("_left")
        assert client.get("/cards/ikea_80213074_cabinet_left").status_code == 200
        assert (
            client.get("/guides/ikea80213074_left_s14/how.phone.png").status_code == 200
        )
        assert not any(
            "ikea" in c["card_id"] for c in client.get("/catalog").json()["tasks"]
        )


def test_context_contains_product_configuration_and_parts(env):
    from ghostbuild_core.assistant.prompts import step_context

    rt, d, _ = env
    say(rt, DEMO)
    say(rt, "It's the MICKE")
    say(rt, "Cabinet on the left")
    s = d.state(rt.session().id)
    text = step_context(
        rt.active_card,
        13,
        product={"product": s.selected.model_dump(), "configuration": s.config},
    )
    assert (
        "80213074" in text
        and "cabinet_side" in text
        and "left" in text
        and "103430" in text
        and "#page=13" in text
    )


def test_uncached_product_never_starts_research_by_default(env):
    rt, d, _ = env
    say(rt, DEMO)
    s = d.state(rt.session().id)
    rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
    d.select(s.session_id, rec.article)
    assert (
        s.phase == "unavailable"
        and rt.live.active is None
        and s.selected.article == rec.article
    )


def test_optional_research_passes_official_manual_urls_only(env, monkeypatch):
    rt, d, _ = env
    d.research = True
    called = []
    monkeypatch.setattr(
        rt.live, "try_start", lambda req, **kw: called.append((req, kw)) or True
    )
    say(rt, DEMO)
    s = d.state(rt.session().id)
    rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
    d.select(s.session_id, rec.article)
    assert (
        called[0][1]["doc_urls"] == [rec.manual_url, rec.product_url]
        and s.phase == "loading"
    )


def test_product_request_can_replace_an_existing_guide(env):
    rt, d, _ = env
    rt.sessions.start_card(rt.session().id, rt.cards[2], echo=False)
    assert rt.session().phase == "task"
    say(rt, DEMO)
    assert (
        phase(rt, d) == "choosing"
        and rt.playbook is None
        and rt.session().phase == "menu"
    )


def test_shortlist_contains_photos_before_focus(env):
    import io
    from PIL import Image

    rt, d, _ = env
    say(rt, DEMO)
    frame = rt.hud.current
    assert frame.mode == "visual" and frame.image.guide_id == "product_matches"
    assert d.state(rt.session().id).focus is None
    image = Image.open(io.BytesIO(d.sheet_images[frame.image.sha256]))
    assert image.size == (288, 144)
    assert all(v % 17 == 0 for v in set(image.tobytes()))
    # Every slot has actual lit photo pixels above its name.
    assert all(image.crop((x, 3, x + 90, 105)).getbbox() for x in (0, 96, 192))
    rt.handle_input(G2Input(gesture="swipe_down", seq_seen=frame.seq))
    assert rt.hud.current.image.sha256 != frame.image.sha256


def test_other_task_clears_previous_product_context(env):
    rt, d, _ = env
    say(rt, DEMO)
    say(rt, "It's the MICKE")
    say(rt, "Cabinet on the left")
    say(rt, "fold a paper cup")
    assert d.state(rt.session().id).phase == "idle"
    assert rt.active_card.card_id == "paper_cup"


def test_reconnect_restores_pending_photo_shortlist(env):
    rt, d, _ = env
    say(rt, DEMO)
    old = rt.session().id
    rt.hello(G2Hello(client_id="other-session"))
    rt.hello(G2Hello(client_id="original-session", session_id=old))
    assert rt.hud.current.image.guide_id == "product_matches"
    assert rt.hud.current.source == "manual"


def test_matching_saved_product_does_not_force_a_live_search(env):
    rt, d, src = env
    src.live = True
    say(rt, DEMO)
    d.pump()
    s = d.state(rt.session().id)
    assert s.live_state == "off" and src.searches == []
    assert "saved verified matches" in s.notice.lower()
    say(rt, "mine has a drawer and cabinet")
    d.pump()
    assert src.searches == []


def test_a_new_product_still_searches_and_manual_refresh_is_explicit(env):
    rt, d, src = env
    src.live = True
    say(rt, "Help me assemble an IKEA blue glass cabinet")
    wait(d, lambda: d.state(rt.session().id).live_state == "done")
    assert len(src.searches) == 1
    d.cancel(rt.session().id)
    say(rt, DEMO)
    assert len(src.searches) == 1
    d.refresh_search(rt.session().id)
    wait(d, lambda: d.state(rt.session().id).live_state == "done")
    assert len(src.searches) == 2


def test_every_manual_step_has_an_automatic_image_and_guard(env):
    rt, d, _ = env
    say(rt, DEMO)
    say(rt, "It's the MICKE")
    say(rt, "Cabinet on the left")
    assert rt.hud.current.mode == "visual" and rt.hud.current.step.index == 0
    assert rt.hud.current.image.view == "where" and rt.playbook.view_idx is None
    before = list(rt.playbook.confirmed)
    rt.handle_input(G2Input(gesture="swipe_down", seq_seen=rt.hud.current.seq))
    assert rt.playbook.index == 0 and rt.playbook.confirmed == before
    rt.clock.advance(700)
    rt.handle_input(G2Input(gesture="swipe_down", seq_seen=rt.hud.current.seq))
    assert (
        rt.playbook.index == 1
        and rt.hud.current.mode == "visual"
        and rt.hud.current.step.index == 1
    )


# ---------------------------------------------------------------- confirmed product without a prepared guide
# Operator log 2026-10-18 08:16: KLEPPSTAD / STJARNO "PRESS: THIS ONE" returned to the photo list five times; nothing was
# generated. A confirmed product now compiles a step guide from ITS official manual, shows progress, then starts it.
def _compile_env(env, monkeypatch, fail=False):
    import shutil
    import knowledge.compile as comp
    import knowledge.find_sources as fs

    rt, d, src = env
    d.research = True
    monkeypatch.setattr(type(src), "auto_card", lambda self, rec: None, raising=False)  # no per-step builder: compile path
    monkeypatch.setenv("GB_LIVE_RESEARCH", "1")
    monkeypatch.setenv("GB_RESEARCH_ENGINE", "compile")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setattr(fs, "find_sources", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no web search for a confirmed product")))
    calls = []
    base = next(c for c in rt.cards if c.steps).model_dump(mode="json")

    def fake_compile(goal, urls, **kw):
        calls.append((goal, list(urls)))
        if fail:
            raise ValueError("nothing usable")
        return {**base, "card_id": "zz_test_compiled_alex", "title": "ALEX assembly"}, {"rounds": 1}

    monkeypatch.setattr(comp, "compile_task", fake_compile)
    return rt, d, calls, lambda: shutil.rmtree(ROOT / "knowledge/live/compiled_cards/zz_test_compiled_alex", ignore_errors=True)


def _until(rt, pred):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        rt.tick()
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_confirmed_product_compiles_from_its_manual_shows_progress_then_starts_the_steps(env, monkeypatch):
    rt, d, calls, cleanup = _compile_env(env, monkeypatch)
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        assert s.phase == "loading" and rt.hud.current.cue.line1.startswith("RESEARCHING"), rt.hud.current.cue  # at once
        assert _until(rt, lambda: rt.playbook is not None)
        assert calls == [(calls[0][0], [rec.manual_url, rec.product_url])]  # its own manual, nothing searched
        assert rt.playbook.card.card_id == "zz_test_compiled_alex" and d.state(s.session_id).phase == "ready"
        assert rt.hud.current.mode in ("step", "visual", "intervene") and rt.session().phase == "task"
        # choosing the same product again reuses the compiled guide instantly: no second paid compile
        say(rt, DEMO)
        s = d.state(rt.session().id)
        d.select(s.session_id, rec.article)
        assert len(calls) == 1 and rt.playbook is not None and rt.playbook.card.card_id == "zz_test_compiled_alex"
    finally:
        cleanup()


def test_gestures_during_preparation_never_pick_a_hidden_photo(env, monkeypatch):
    rt, d, calls, cleanup = _compile_env(env, monkeypatch)
    import knowledge.compile as comp
    gate = Event()
    inner = comp.compile_task
    monkeypatch.setattr(comp, "compile_task", lambda *a, **k: (gate.wait(2), inner(*a, **k))[1])
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
        assert d.state(s.session_id).selected.article == rec.article and d.state(s.session_id).phase == "loading"
        gate.set()
        assert _until(rt, lambda: rt.playbook is not None)
    finally:
        gate.set()
        cleanup()


def test_failed_preparation_says_so_and_keeps_the_manual(env, monkeypatch):
    rt, d, calls, cleanup = _compile_env(env, monkeypatch, fail=True)
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        assert _until(rt, lambda: d.state(s.session_id).phase != "loading")
        s = d.state(s.session_id)
        assert s.phase == "unavailable" and "could not" in s.message.lower() and rt.playbook is None
        assert rt.hud.current.cue.line1 == "NO RELIABLE GUIDE"  # said on the glasses, not a silent photo list
    finally:
        cleanup()


def test_a_guide_that_cannot_start_says_so_on_the_glasses(env):
    """Live research off (or busy / at its cap): never a silent return to the photo list after THIS ONE."""
    rt, d, _ = env
    say(rt, DEMO)
    s = d.state(rt.session().id)
    rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
    d.select(s.session_id, rec.article)
    assert s.phase == "unavailable" and rt.hud.current.cue.line1 == "NO STEP GUIDE YET"
    assert rt.hud.current.cue.line2 == "MANUAL ON YOUR PHONE"


# ---------------------------------------------------------------- back (swipe up) after choosing, and gesture hints
def test_photo_screens_show_their_gestures(env):
    rt, d, _ = env
    say(rt, DEMO)
    assert "● ENLARGE" in rt.hud.current.cue.line2 and "◀▶" in rt.hud.current.cue.line2
    rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))
    assert rt.hud.current.cue.line2 == "● PICK  ▶ NEXT  ◀ BACK"


def test_swipe_up_while_preparing_returns_to_the_photo_and_choosing_again_resumes(env, monkeypatch):
    rt, d, calls, cleanup = _compile_env(env, monkeypatch)
    import knowledge.compile as comp
    gate = Event()
    inner = comp.compile_task
    monkeypatch.setattr(comp, "compile_task", lambda *a, **k: (gate.wait(3), inner(*a, **k))[1])
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        rt.handle_input(G2Input(gesture="swipe_up", seq_seen=rt.hud.current.seq))
        s = d.state(s.session_id)
        assert s.phase == "choosing" and s.candidates[s.focus].record.article == rec.article  # back on that photo
        assert rt.hud.current.cue.line2 == "● PICK  ▶ NEXT  ◀ BACK"
        rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))  # pick it again: wait for the same build
        assert d.state(s.session_id).phase == "loading" and rt.hud.current.cue.line1.startswith("RESEARCHING")
        gate.set()
        assert _until(rt, lambda: rt.playbook is not None) and len(calls) == 1
    finally:
        gate.set()
        cleanup()


def test_swipe_up_on_the_first_step_returns_to_the_chosen_product_photo(env, monkeypatch):
    rt, d, calls, cleanup = _compile_env(env, monkeypatch)
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        assert _until(rt, lambda: rt.playbook is not None)
        rt.clock.advance(5000)
        rt.tick()
        rt.handle_input(G2Input(gesture="swipe_up", seq_seen=rt.hud.current.seq))
        s = d.state(s.session_id)
        assert rt.playbook is None and rt.session().phase == "menu"
        assert s.phase == "choosing" and s.candidates[s.focus].record.article == rec.article
        rt.handle_input(G2Input(gesture="press", seq_seen=rt.hud.current.seq))  # and forward again: instant, no new build
        assert rt.playbook is not None and len(calls) == 1
    finally:
        cleanup()


def test_shortlist_image_shows_a_position_strip_for_more_than_one_page():
    from PIL import Image
    import io
    from ghostbuild_core.discovery.images import position_strip
    sheet = Image.new("L", (288, 144), 0)
    position_strip(sheet, total=5, current=3)
    row = [sheet.getpixel((x, 140)) for x in range(288)]
    assert max(row) > 0  # dots drawn
    blank = Image.new("L", (288, 144), 0)
    position_strip(blank, total=3, current=0)
    assert max(blank.getpixel((x, 140)) for x in range(288)) == 0  # one page: no strip


def test_a_per_step_manual_build_is_used_before_the_generic_compile(env, monkeypatch):
    """Operator 09:00: compiled MICKE 10244743 came out as 'DO MANUAL PAGES 1-10'. A numbered manual now becomes one step per
    manual step with its own crop (integrations/ikea/auto_manual.py); the page-level compile is only the fallback."""
    rt, d, calls, cleanup = _compile_env(env, monkeypatch)
    rt_, d_, src = env
    base = next(c for c in rt.cards if c.steps).model_dump(mode="json")
    monkeypatch.setattr(type(src), "auto_card", lambda self, rec: {**base, "card_id": "zz_test_compiled_alex", "title": "ALEX - assembly"},
                        raising=False)
    try:
        say(rt, DEMO)
        s = d.state(rt.session().id)
        rec = next(c.record for c in s.candidates if c.record.name == "ALEX")
        d.select(s.session_id, rec.article)
        assert _until(rt, lambda: rt.playbook is not None)
        assert rt.playbook.card.title == "ALEX - assembly" and calls == []  # the generic compile never ran
    finally:
        cleanup()
