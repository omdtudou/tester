"""One-off diagnostic: save raw Polymarket US public API responses so the market mapping can be checked."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://gateway.polymarket.us"
OUT = "data/diag"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "arbscan/1.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            return {"status": r.status, "body": body[:60000]}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", "replace")[:5000]}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "body": repr(e)}


def slugs(body, limit=3):
    found = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("slug"), str) and ("question" in o or "marketSides" in o or "outcomes" in o):
                found.append(o["slug"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    try:
        walk(json.loads(body))
    except ValueError:
        pass
    return list(dict.fromkeys(found))[:limit]


paths = [
    "/v1/search?query=counter-strike",
    "/v1/search?query=league+of+legends",
    "/v1/search?query=dota",
    "/v1/markets?active=true&closed=false&limit=5",
    "/v1/markets?active=true&closed=false&limit=5&categories=esports",
    "/v1/events?active=true&limit=3",
    "/v1/sports",
]
out = {p: get(p) for p in paths}
for p in ("/v1/search?query=counter-strike", "/v1/search?query=league+of+legends",
          "/v1/markets?active=true&closed=false&limit=5"):
    for s in slugs(out[p]["body"], 2):
        q = urllib.parse.quote(s)
        for extra in (f"/v1/market/slug/{q}", f"/v1/markets/{q}/book"):
            out.setdefault(extra, get(extra))

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "pmus_raw.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
for p, r in out.items():
    print(r["status"], len(r["body"]), p)
