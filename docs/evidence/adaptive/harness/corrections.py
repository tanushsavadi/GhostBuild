"""Correction scenarios through the real Runtime (no model): what changes, what is kept, what is asked."""
import json, os, sys, tempfile, time
from pathlib import Path
os.environ.update(GB_ASSISTANT="0", GB_LIVE_RESEARCH="0", GB_CREAO="0", GB_VOICE="0", GB_DISCOVERY_LIVE="0")
from contracts.models import G2Hello, GoalRequest
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime
from integrations.product_discovery import attach_discovery

def fresh():
    clock = ManualClock()
    rt = Runtime(load_cards("knowledge/cards"), clock=clock, log_dir=Path(tempfile.mkdtemp()), asset_root=Path("."), brain=None)
    rt.clock = clock
    attach_discovery(rt)
    rt.hello(G2Hello(client_id="t")); clock.advance(2600); rt.tick()
    return rt

def where(rt):
    pb = rt.playbook
    d = rt.discovery.state(rt.session().id) if rt.discovery else None
    return {"phase": rt.session().phase, "card": pb and pb.card.card_id, "step": pb and pb.step.id, "kind": pb and pb.step.kind,
            "observations": pb and [o["text"] for o in pb.observations], "glasses": rt.hud.current.cue.model_dump() if rt.hud.current.cue else None,
            "image": rt.hud.current.image and rt.hud.current.image.url, "discovery": d and d.phase, "selected": d and d.selected and d.selected.name,
            "candidates": d and [c.record.name + " " + c.record.article for c in d.candidates][:5]}

def say(rt, text):
    if rt.session().phase == "task" and rt.playbook is not None:
        r = rt.ask(text); out = {"you": text, "intent": r.intent if r else None, "reply": r.text if r else None}
    else:
        r = rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode="fix", via="phone_text", text=text))
        out = {"you": text, "status": r and r.status, "reply": r and r.detail}
    rt.tick(); rt.clock.advance(1700); rt.tick()
    out["now"] = where(rt); print(json.dumps(out)); return out

def start(rt, cid):
    rt.sessions.start_card(rt.session().id, rt.card_by_id(cid)); rt.tick(); rt.clock.advance(1700); rt.tick()

log = {"_evidence": {"label": "DETERMINISTIC Runtime harness; not physical G2", "provider_calls": 0,
                     "note": "Product records may include previously retrieved local cache entries. Live retrieval is disabled."}}
rt = fresh(); log["1_ikea"] = [say(rt, "I'm assembling a white IKEA MICKE desk"), say(rt, "number one"), say(rt, "cabinet on the left"),
                               say(rt, "show me step 14"),
                               say(rt, "Wait, actually, I checked the box. It's a MALM desk, not MICKE.")]
assert rt.playbook is None
rt.close()
rt = fresh(); start(rt, "mac_display_colors")
log["2_mac"] = [say(rt, "My MacBook screen is turning green, but my external monitor looks fine."), say(rt, "the laptop screen"),
                say(rt, "Actually, I just checked. The external monitor is green too.")]
assert "both" in rt.playbook.observations[0]["text"].lower()
rt.close()
rt = fresh(); start(rt, "bike_flat_tire")
log["3_bike"] = [say(rt, "I'm pretty sure my bike has an inner tube"),
                 say(rt, "Wait, the tire says tubeless ready, and I think it's actually set up tubeless.")]
assert rt.playbook.step.id == "q_tube_type" and not rt.playbook.observations
rt.close()
rt = fresh(); start(rt, "prusa_mk4_not_extruding")
log["4_prusa"] = [say(rt, "It's a Prusa MK4 and it makes a loud clicking"), say(rt, "Sorry, it's actually an MK3S+.")]
assert rt.playbook is None
rt.close()
json.dump(log, open(sys.argv[1], "w"), indent=1)
