"""One-off diagnostic: raw Kalshi public trades for the markets the maker simulation bid on."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.elections.kalshi.com/trade-api/v2"
tickers = []
if os.path.exists("data/paper.jsonl"):
    with open("data/paper.jsonl", encoding="utf-8") as f:
        for line in f:
            if '"maker_post"' in line:
                op = json.loads(line)["op"]                  # maker:{ticker}|{slug}:{side}
                t = op.split(":", 1)[1].split("|", 1)[0]
                if t not in tickers:
                    tickers.append(t)
out = {}
for t in tickers[-4:] or ["KXCS2GAME"]:
    for params in ({"ticker": t, "limit": 20}, {"ticker": t, "limit": 20, "min_ts": 0}):
        url = f"{API}/markets/trades?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "arbscan/1.1", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                out[url] = {"status": r.status, "body": json.loads(r.read().decode())}
        except urllib.error.HTTPError as e:
            out[url] = {"status": e.code, "body": e.read().decode("utf-8", "replace")[:2000]}
        except Exception as e:  # noqa: BLE001
            out[url] = {"status": None, "body": repr(e)}
        b = out[url]["body"]
        n = len(b.get("trades", [])) if isinstance(b, dict) else "-"
        print(out[url]["status"], n, "trades", url)
os.makedirs("data/diag", exist_ok=True)
with open("data/diag/kalshi_trades_raw.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
