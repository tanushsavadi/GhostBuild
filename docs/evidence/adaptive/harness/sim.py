"""Drive the official simulator + harness backend; save composited glasses screenshots and state per step."""
import io, json, sys, time, urllib.request
from PIL import Image
SIM, BE = "http://127.0.0.1:9897", "http://127.0.0.1:8799"
OUT = sys.argv[1]
def get(u): return urllib.request.urlopen(u, timeout=15).read()
def post(u, body): return urllib.request.urlopen(urllib.request.Request(u, json.dumps(body).encode(), {"content-type": "application/json"}), timeout=15).read()
def state(): return json.loads(get(BE + "/state"))
def shot(name):
    img = Image.open(io.BytesIO(get(SIM + "/api/screenshot/glasses"))).convert("RGBA")
    bg = Image.new("RGBA", img.size, (0, 0, 0, 255)); bg.alpha_composite(img); bg.convert("RGB").save(f"{OUT}/{name}.png")
def inp(a): post(SIM + "/api/input", {"action": a}); time.sleep(0.9)
def summ(s): return {"mode": s["hud"]["mode"], "cue": s["hud"]["cue"], "answer": s["hud"].get("answer") and {k: s["hud"]["answer"][k] for k in ("index", "count")},
                     "step": s["playbook"] and s["playbook"]["step_index"], "confirmed": s["playbook"] and s["playbook"]["confirmed"], "session": s["session"]["id"]}
res = []
def rec(name):
    s = state(); shot(name); res.append({"name": name, **summ(s)}); print(name, res[-1])
for a in sys.argv[2:]:
    if a.startswith("ask:"):
        sid = state()["session"]["id"]
        post(BE + "/ask", {"session_id": sid, "text": a[4:]}); time.sleep(2.6)
    elif a.startswith("shot:"):
        rec(a[5:])
    elif a.startswith("wait:"):
        time.sleep(float(a[5:]))
    else:
        inp(a)
json.dump(res, open(f"{OUT}/sim-run.json", "a"), indent=1)
