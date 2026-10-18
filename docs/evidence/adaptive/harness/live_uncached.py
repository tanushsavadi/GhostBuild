"""Real uncached path through the actual Runtime: no cached card, live research engine = compile. Paid: Anthropic only."""
import json, os, sys, time, tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path.cwd() / ".env", override=False)
os.environ.update(GB_ASSISTANT="0", GB_LIVE_RESEARCH="1", GB_RESEARCH_ENGINE="compile", GB_CREAO="0", GB_VOICE="0", GB_DISCOVERY_LIVE="0")
from contracts.models import G2Hello, GoalRequest
from ghostbuild_core.cards import load_cards
from ghostbuild_core.runtime import Runtime

goal = sys.argv[1]
rt = Runtime(load_cards("knowledge/cards"), log_dir=Path(tempfile.mkdtemp()), asset_root=Path("."), brain=None)
rt.hello(G2Hello(client_id="eval")); time.sleep(2.7); rt.tick()
t0 = time.monotonic()
res = rt.resolve_goal(GoalRequest(session_id=rt.session().id, mode="fix", via="phone_text", text=goal))
print("resolution:", res.status if res else None, res.cue if res else None, "| glasses:", rt.hud.current.cue)
while rt.live.active is not None and time.monotonic() - t0 < 600:
    rt.tick(); time.sleep(0.5)
rt.tick()
took = round(time.monotonic() - t0, 1)
out = {"goal": goal, "took_s": took, "last": rt.live.last, "phase": rt.session().phase,
       "card": rt.playbook.card.card_id if rt.playbook else None, "first_screen": rt.hud.current.model_dump(mode="json")}
if rt.playbook:
    out["steps"] = [(s.id, s.kind, s.cue.line1, s.cue.line2) for s in rt.playbook.card.steps]
    out["sources"] = [s.url for s in rt.playbook.card.sources]
print(json.dumps(out, indent=1, default=str)[:4000])
json.dump(out, open(sys.argv[2], "w"), indent=1, default=str)
