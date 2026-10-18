"""Bounded live check of the intake/step brain (Anthropic only; <=6 calls). Prints decisions, not secrets."""
import json, os, sys, time, tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path.cwd() / ".env", override=False)
for k in ("CREAO_API_KEY", "ELEVENLABS_API_KEY"):
    os.environ[k] = ""
os.environ.update(GB_CREAO="0", GB_LIVE_RESEARCH="0", GB_VOICE="0", GB_TTS="0", GB_DISCOVERY_LIVE="0")
from contracts.models import G2Hello, GoalRequest
from ghostbuild_core.assistant.brain import AnthropicBrain
from ghostbuild_core.cards import load_cards
from ghostbuild_core.clock import ManualClock
from ghostbuild_core.runtime import Runtime

calls = {"n": 0}
import anthropic
class Counted(AnthropicBrain):
    def __init__(self):
        super().__init__(client=anthropic.Anthropic(timeout=20, max_retries=0))
    def _parse(self, system, messages, model_cls, fast):
        calls["n"] += 1  # one HTTP request per _parse (SDK retries off)
        if calls["n"] > 8:
            raise RuntimeError("call budget exhausted")
        t = time.monotonic()
        try:
            return super()._parse(system, messages, model_cls, fast)
        finally:
            calls.setdefault("ms", []).append(int((time.monotonic()-t)*1000))

def run(turns):
    tmp = Path(tempfile.mkdtemp())
    clock = ManualClock()
    rt = Runtime(load_cards("knowledge/cards"), clock=clock, log_dir=tmp, asset_root=Path("."), brain=Counted())
    rt.hello(G2Hello(client_id="eval")); clock.advance(2600); rt.tick()
    out = []
    for t in turns:
        rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode="build", via="phone_text", text=t))
        end = time.time() + 40
        while rt.assistant.pending and time.time() < end:
            rt.tick(); time.sleep(0.05)
        rt.tick()
        task = rt.assistant.tasks.get(rt.session().id)
        msgs = [m for m in rt.assistant.chat.get(rt.session().id, []) if m.role in ("assistant", "system")]
        out.append({"user": t, "decision": task.decisions[-1]["decision"] if task and task.decisions else None,
                    "say": msgs[-1].text if msgs else None, "critical_unknowns": task.critical_unknowns if task else None,
                    "facts": [(f.field, f.value, f.origin) for f in task.facts] if task else None,
                    "phase": rt.session().phase, "card": rt.playbook.card.card_id if rt.playbook else None})
        print(json.dumps(out[-1], indent=1))
    rt.close()
    return out

cases = {
    "C_mac_screen": ["my mac screen is acting weird", "only the external monitor, the laptop screen is fine"],
    "D_F_bike_unknown": ["fix my bike tyre", "I don't know"],
    "H_new_goal": ["actually I want to build a bookshelf instead"],
}
res = {}
for name, turns in cases.items():
    print("==", name)
    res[name] = run(turns)
# one live step question on the real MICKE manual card (step 14)
print("== STEP_explain")
tmp = Path(tempfile.mkdtemp()); clock = ManualClock()
rt = Runtime(load_cards("knowledge/cards"), clock=clock, log_dir=tmp, asset_root=Path("."), brain=Counted())
from integrations.product_discovery import attach_discovery
attach_discovery(rt)
rt.hello(G2Hello(client_id="eval")); clock.advance(2600); rt.tick()
for t in ["I have a white IKEA desk with a drawer and cabinet", "It's the MICKE", "number one", "Cabinet on the left"]:
    rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode="build", via="phone_text", text=t))
rt.ask("show me step 14")
q = "How do these round metal locks work, and how far should I turn them?"
r = rt.ask(q)
end = time.time() + 40
while rt.assistant.pending and time.time() < end:
    rt.tick(); time.sleep(0.05)
rt.tick()
ans = [m for m in rt.assistant.chat[rt.session().id] if m.role == "assistant"]
res["STEP_explain"] = {"question": q, "routed": r.intent, "answer": ans[-1].text if ans else None, "grounding": ans[-1].grounding if ans else None,
                       "glasses_pages": rt.playbook.answer_data and len(__import__("ghostbuild_core.answer", fromlist=["pages"]).pages(rt.playbook.answer_data["text"])),
                       "step_after": rt.playbook.index, "confirmed": rt.playbook.confirmed}
print(json.dumps(res["STEP_explain"], indent=1))
rt.close()
res["anthropic_http_requests"] = calls["n"]
res["latency_ms"] = calls.get("ms")
json.dump(res, open(sys.argv[1], "w"), indent=1)
print("anthropic http requests:", calls["n"], calls.get("ms"))
