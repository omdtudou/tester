"""One-off check: how much past esports data does Kalshi keep?

Counts settled match markets per series, shows their date range, and pulls the
full trade history and 1-minute candles for a few of them. Read-only.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ["KXVALORANTGAME", "KXCS2GAME", "KXLOLGAME", "KXDOTA2GAME"]


def get(path, **params):
    url = f"{API}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "arbscan-diag"}), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            return {"_error": e.code, "_url": url}
        except Exception as e:  # noqa: BLE001
            return {"_error": str(e), "_url": url}
        finally:
            time.sleep(0.25)
    return {"_error": "gave up", "_url": url}


def settled_events(series, pages=10):
    out, cursor = [], None
    for _ in range(pages):
        d = get("/events", series_ticker=series, status="settled", with_nested_markets="true", limit=200, cursor=cursor)
        if "_error" in d:
            print("  events error:", d)
            break
        out += d.get("events") or []
        cursor = d.get("cursor")
        if not cursor:
            break
    return out


def all_trades(ticker, pages=20):
    out, cursor = [], None
    for _ in range(pages):
        d = get("/markets/trades", ticker=ticker, limit=1000, cursor=cursor)
        if "_error" in d:
            return out, d
        out += d.get("trades") or []
        cursor = d.get("cursor")
        if not cursor:
            break
    return out, None


def ts(s):
    return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone if s else None


def main():
    print("Historical endpoints:")
    for path in ("/historical/cutoff", "/historical/markets"):
        d = get(path, limit=1)
        print(f"  {path}: {'error ' + str(d['_error']) if '_error' in d else 'ok, keys ' + ', '.join(list(d)[:6])}")

    for series in SERIES:
        ev = settled_events(series)
        markets = [m for e in ev for m in (e.get("markets") or [])]
        closes = sorted(m.get("close_time") or m.get("expiration_time") or "" for m in markets if m)
        closes = [c for c in closes if c]
        vols = sorted((float(m.get("volume_fp") or m.get("volume") or 0), m.get("ticker")) for m in markets)
        print(f"\n== {series}: {len(ev)} settled events, {len(markets)} markets")
        if closes:
            print(f"  close times {closes[0][:10]} .. {closes[-1][:10]}")
        if not markets:
            continue
        zero = sum(1 for v, _ in vols if v == 0)
        print(f"  markets with zero volume: {zero}; median volume {vols[len(vols) // 2][0]:.0f}; top {vols[-1][0]:.0f}")
        print("  sample events:", ", ".join(e.get("event_ticker", "") for e in ev[:4]))
        # Trade history for the busiest, a median and a quiet market.
        picks = [vols[-1][1], vols[len(vols) // 2][1], vols[len(vols) // 4][1]]
        for t in dict.fromkeys(picks):
            trades, err = all_trades(t)
            times = sorted(x.get("created_time", "") for x in trades)
            span = f"{times[0][:16]} .. {times[-1][:16]}" if times else "none"
            print(f"  trades {t}: {len(trades)} ({span}){' ERROR ' + str(err) if err else ''}")
            if times:
                end = int(ts(times[-1])) + 60
                start = max(int(ts(times[0])) - 60, end - 5 * 24 * 3600)
                c = get(f"/series/{series}/markets/{t}/candlesticks", start_ts=start, end_ts=end, period_interval=1)
                if "_error" in c:
                    print(f"    candles: error {c['_error']}")
                else:
                    print(f"    candles (1 min): {len(c.get('candlesticks') or [])}")
    print("\nSample trade row:")
    for series in SERIES:
        ev = settled_events(series, pages=1)
        for e in ev:
            for m in e.get("markets") or []:
                tr, _ = all_trades(m["ticker"], pages=1)
                if tr:
                    print(json.dumps(tr[0])[:600])
                    return


if __name__ == "__main__":
    main()
