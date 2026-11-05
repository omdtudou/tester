"""Collect Kalshi esports match prices for the research spreadsheet. Read-only, public data.

For every settled two-team match market in each series: the result, total
volume, and the bid / ask / last trade at fixed times around the scheduled
start (from 1-minute candles). Continues from data/dataset/<series>.json.
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import veto_backtest as vb  # noqa: E402

OFFSETS = (-120, -60, -30, -10, 0, 10, 20, 45)
DEFAULT_SERIES = ["KXCS2GAME", "KXLOLGAME", "KXDOTA2GAME"]


def checkpoint_quotes(candles, t0):
    out = {}
    for off in OFFSETS:
        q = vb.quote_at(candles, t0 + timedelta(minutes=off))
        out[str(off)] = [q["bid"], q["ask"], q["last"], round(q["mid"], 4), int(q["age_s"])] if q else None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*", default=DEFAULT_SERIES)
    ap.add_argument("--out", default="data/dataset")
    ap.add_argument("--budget-minutes", type=float, default=70)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    deadline = time.time() + args.budget_minutes * 60
    lock = threading.Lock()
    for series in args.series:
        path = os.path.join(args.out, f"{series}.json")
        try:
            with open(path, encoding="utf-8") as f:
                store = json.load(f)
        except (OSError, ValueError):
            store = {"series": series, "matches": {}}
        markets = vb.kalshi_markets(vb.http_get, series)
        rows, skipped = vb.kalshi_matches(markets)
        timed = [r for r in rows if r["kind"] == "time"]
        skipped["only a date in ticker"] = len(rows) - len(timed)
        store["skipped"] = skipped
        store["listed"] = len(rows)
        todo = [r for r in timed if r["event"] not in store["matches"]]
        print(f"{series}: {len(rows)} settled matches, {len(todo)} to fetch", flush=True)

        def fetch(r):
            if time.time() > deadline:
                return None
            t0 = vb.parse_iso(r["start"])
            candles = vb.kalshi_candles(vb.http_get, r["ticker_a"], r["tier"], t0, series)
            b = r["ticker_a"]
            return r["event"], {"start": r["start"], "team_a": r["team_a"], "team_b": r["team_b"],
                                "a_won": r["a_won"], "volume": r["volume"], "tier": r["tier"], "ticker_a": b,
                                "n_candles": len(candles), "q": checkpoint_quotes(candles, t0)}

        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(fetch, r) for r in todo]
            for fut in as_completed(futures):
                try:
                    got = fut.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  error: {e}", flush=True)
                    continue
                if not got:
                    continue
                with lock:
                    store["matches"][got[0]] = got[1]
                    done += 1
                    if done % 250 == 0:
                        print(f"  {series}: {done} fetched", flush=True)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(store, f, separators=(",", ":"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, separators=(",", ":"))
        print(f"{series}: {len(store['matches'])} matches stored", flush=True)
        if time.time() > deadline:
            print("time budget used up; run again to continue", flush=True)
            break


if __name__ == "__main__":
    main()
