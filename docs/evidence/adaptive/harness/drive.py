"""Drive a backend + official simulator: say/press things, record HUD state and composited glasses screenshots."""
import io, json, sys, time, urllib.request
from PIL import Image
BE, SIM, OUT = sys.argv[1], "http://127.0.0.1:9897", sys.argv[2]
def get(u): return urllib.request.urlopen(u, timeout=30).read()
def post(u, b): return json.loads(urllib.request.urlopen(urllib.request.Request(u, json.dumps(b).encode(), {"content-type": "application/json"}), timeout=60).read() or b"null")
def st(): return json.loads(get(BE + "/state"))
def shot(name):
    img = Image.open(io.BytesIO(get(SIM + "/api/screenshot/glasses"))).convert("RGBA")
    bg = Image.new("RGBA", img.size, (0, 0, 0, 255)); bg.alpha_composite(img); bg.convert("RGB").save(f"{OUT}/{name}.png")
def wait_idle(limit=40):
    end = time.time() + limit
    while time.time() < end:
        a = json.loads(get(BE + "/assistant/state"))
        if not a.get("pending"): return a
        time.sleep(0.4)
    return json.loads(get(BE + "/assistant/state"))
log = []
for a in sys.argv[3:]:
    s = st(); sid = s["session"]["id"]; t0 = time.monotonic()
    if a.startswith("goal:"):
        r = post(BE + "/session/goal", {"session_id": sid, "mode": "fix", "via": "phone_text", "text": a[5:]})
        asst = wait_idle()
    elif a.startswith("say:"):
        if s["session"]["phase"] == "task":
            r = post(BE + "/ask", {"session_id": sid, "text": a[4:]})
        else:
            r = post(BE + "/session/goal", {"session_id": sid, "mode": "fix", "via": "phone_text", "text": a[4:]})
        asst = wait_idle()
    elif a.startswith("shot:"):
        shot(a[5:]); s = st()
        entry = {"shot": a[5:], "mode": s["hud"]["mode"], "cue": s["hud"]["cue"], "menu": s["hud"].get("menu"), "phase": s["session"]["phase"],
                 "card": s.get("card_id"), "step": s["playbook"] and s["playbook"]["step_id"], "observations": s["playbook"] and s["playbook"].get("observations")}
        print(json.dumps(entry)); log.append(entry); continue
    elif a.startswith("wait:"):
        time.sleep(float(a[5:])); continue
    else:
        post(SIM + "/api/input", {"action": a}); time.sleep(1.0); continue
    a2 = json.loads(get(BE + "/assistant/state"))
    msgs = [m for m in a2["messages"] if m["role"] != "user"][-1:]
    entry = {"said": a[4:], "took_s": round(time.monotonic() - t0, 2), "assistant": msgs[0]["text"] if msgs else None,
             "decision": (a2.get("task_profile") or {}).get("decisions", [{}])[-1].get("decision") if a2.get("task_profile") else None}
    print(json.dumps(entry)); log.append(entry)
json.dump(log, open(f"{OUT}/drive-{int(time.time())}.json", "w"), indent=1)
