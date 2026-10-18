"""Hot-path latencies on a running backend (local HTTP, 10 samples each). Not BLE/glasses timing."""
import json, statistics, sys, time, urllib.request
BE = sys.argv[1]
def t(fn, n=10):
    xs = []
    for _ in range(n):
        a = time.perf_counter(); fn(); xs.append((time.perf_counter() - a) * 1000)
    return {"median_ms": round(statistics.median(xs), 2), "min_ms": round(min(xs), 2), "max_ms": round(max(xs), 2), "n": n}
get = lambda u: urllib.request.urlopen(BE + u, timeout=10).read()
def post(u, b): return urllib.request.urlopen(urllib.request.Request(BE + u, json.dumps(b).encode(), {"content-type": "application/json"}), timeout=10).read()
st = json.loads(get("/state")); sid = st["session"]["id"]
card = json.loads(get("/catalog"))["tasks"]
res = {"catalog": t(lambda: get("/catalog")), "state": t(lambda: get("/state"))}
c = json.loads(get("/card"))
guides = [v["image"] for g in (c or {}).get("guides", []) for v in g["views"]][:3]
if c and c.get("guides"):
    gid = c["guides"][0]["id"]; view = c["guides"][0]["views"][0]["view"]
    res["guide_image_g2"] = t(lambda: get(f"/guides/{gid}/{view}.png"))
    res["guide_image_phone"] = t(lambda: get(f"/guides/{gid}/{view}.phone.png"))
res["deterministic_ask_where"] = t(lambda: post("/ask", {"session_id": sid, "text": "which step am I on"}))
print(json.dumps(res, indent=1)); json.dump(res, open(sys.argv[2], "w"), indent=1)
