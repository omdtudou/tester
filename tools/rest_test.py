"""Does rest matter? Days since each team's previous match, favorite vs underdog.

Rule fixed before looking at CS2 / LoL / Dota 2:
    When the favorite has had REST_GAP or more days more rest than the underdog,
    buy the underdog at its ask 10 minutes before the start.

Rest comes from vlr.gg's full schedule for Valorant. For the other games only
Kalshi's own match list is available, so rest there counts only matches Kalshi
listed; the Valorant section shows how close that proxy gets to the real thing.
"""
import argparse
import os
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_workbook as bw  # noqa: E402
import edge_search as es  # noqa: E402
import veto_backtest as vb  # noqa: E402

REST_GAP = 3
CAP = 14
BUCKETS = [("Fav 3+ days LESS rest", -99, -3), ("Fav 1–3 days less", -3, -1), ("About equal (±1 day)", -1, 1.0001),
           ("Fav 1–3 days MORE rest", 1.0001, 3), ("Fav 3+ days MORE rest", 3, 99)]


def rest_from_times(times_by_team, team, when):
    ts = times_by_team.get(team, [])
    i = bisect_left(ts, when - timedelta(hours=3))
    return min((when - ts[i - 1]).total_seconds() / 86400, CAP) if i > 0 else None


def add_rest(rows, times_by_team, key_fav, key_dog, field):
    for r in rows:
        f = rest_from_times(times_by_team, key_fav(r), r["date"])
        d = rest_from_times(times_by_team, key_dog(r), r["date"])
        r[field] = None if f is None or d is None else f - d


def kalshi_schedule(rows):
    times = defaultdict(list)
    for r in rows:
        times[r["fav"]].append(r["date"])
        times[r["dog"]].append(r["date"])
    for v in times.values():
        v.sort()
    return times


def summarise(rows, field):
    out = []
    for label, lo, hi in BUCKETS:
        sub = [r for r in rows if r.get(field) is not None and lo <= r[field] < hi and r.get("c10") is not None]
        if not sub:
            out.append((label, 0, None, None, None, None))
            continue
        price = sum(r["c10"] for r in sub) / len(sub)
        won = sum(r["won"] for r in sub) / len(sub)
        dog = buy_dog(sub)
        fav = buy_fav(sub)
        out.append((label, len(sub), price, won, es.mean_ci(fav), es.mean_ci(dog)))
    return out


def buy_dog(rows):
    rets = []
    for r in rows:
        if r.get("bid10") is None:
            continue
        price = 1 - r["bid10"]
        rets.append((0.0 if r["won"] else 1.0) / (price + es.fee(price)) - 1)
    return rets


def buy_fav(rows):
    rets = []
    for r in rows:
        if r.get("ask10") is None:
            continue
        rets.append((1.0 if r["won"] else 0.0) / (r["ask10"] + es.fee(r["ask10"])) - 1)
    return rets


def slope(rows, field):
    sub = [r for r in rows if r.get(field) is not None and r.get("c10") is not None]
    if len(sub) < 50:
        return None
    b, se = es.fit([[1.0, r[field]] for r in sub], [r["won"] for r in sub], [es.logit(r["c10"]) for r in sub])
    return len(sub), b[1], se[1], es.p_two_sided(b[1] / se[1])


def fmt_ret(x):
    if not x or x[0] is None:
        return "–"
    m, lo, hi = x
    return f"{m * 100:+.1f}% ({lo * 100:+.0f} to {hi * 100:+.0f})"


def table(rows, field):
    L = ["| Rest gap (favorite minus underdog) | Matches | Avg fav chance | Fav won | Gap | Buy fav: return (90%) | "
         "Buy dog: return (90%) |", "|---|---|---|---|---|---|---|"]
    for label, n, price, won, fav, dog in summarise(rows, field):
        if not n:
            L.append(f"| {label} | 0 | | | | | |")
            continue
        L.append(f"| {label} | {n} | {price:.1%} | {won:.1%} | {(won - price) * 100:+.1f} pts | {fmt_ret(fav)} | "
                 f"{fmt_ret(dog)} |")
    return L


def rule_line(rows, field, label):
    sub = [r for r in rows if r.get(field) is not None and r[field] >= REST_GAP]
    m = es.mean_ci(buy_dog(sub))
    s = slope(rows, field)
    sl = f"slope {s[1]:+.3f} per day (± {s[2]:.3f}), p={s[3]:.2f}, n={s[0]}" if s else "slope: too few"
    return f"- {label}: rule bets {len(buy_dog(sub))}, return {fmt_ret(m)}; {sl}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", default="data/backtest")
    ap.add_argument("--dataset", default="data/dataset")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cache = vb.Cache(args.backtest)
    val, _ = bw.valorant_rows(cache)

    # vlr.gg full schedule, keyed by team id
    vlr_times = defaultdict(list)
    for x in cache["vlr_results"].get("rows", []):
        dt = vb.parse_iso(x["dt"])
        if dt:
            local = dt.astimezone(vb.ET).replace(tzinfo=None)
            for tid in (x["i1"], x["i2"]):
                if tid:
                    vlr_times[tid].append(local)
    for v in vlr_times.values():
        v.sort()
    ids = {}
    for r in val:
        info = cache["vlr_info"].get(r["vlr"].rsplit("/", 1)[1]) or {}
        ids[(r["vlr"], info.get("n1"))] = info.get("t1")
        ids[(r["vlr"], info.get("n2"))] = info.get("t2")
    add_rest(val, vlr_times, lambda r: ids.get((r["vlr"], r["fav"])), lambda r: ids.get((r["vlr"], r["dog"])), "rest_vlr")
    add_rest(val, kalshi_schedule(val), lambda r: r["fav"], lambda r: r["dog"], "rest_kalshi")
    for r in val:
        st = (r.get("stage") or "").lower()
        r["bracket"] = ("playoffs" if any(k in st for k in ("playoff", "final", "bracket", "upper", "lower",
                                                              "semifinal", "quarterfinal", "main event"))
                        else "groups/regular")

    L = ["# Rest-days test", "",
         f"Fixed rule: when the favorite has had {REST_GAP}+ more days of rest than the underdog, buy the underdog at "
         "its ask 10 minutes before the start (Kalshi taker fee included). Rest capped at 14 days.", ""]
    L += ["## Valorant (rest from vlr.gg's full schedule)", ""]
    L += table(val, "rest_vlr") + [""]
    val.sort(key=lambda r: r["date"])
    half = len(val) // 2
    cut = val[half]["date"]
    L.append(rule_line(val[:half], "rest_vlr", f"Earlier half (before {cut:%Y-%m-%d})"))
    L.append(rule_line(val[half:], "rest_vlr", "Later half"))
    L.append(rule_line(val, "rest_vlr", "All Valorant"))
    for b in ("groups/regular", "playoffs"):
        L.append(rule_line([r for r in val if r["bracket"] == b], "rest_vlr", f"Stage: {b}"))
    for g in ("International", "VCT league", "Challengers", "Game Changers", "Other"):
        sub = [r for r in val if r["group"] == g]
        if len(sub) >= 50:
            L.append(rule_line(sub, "rest_vlr", f"Event type: {g}"))
    both = [r for r in val if r.get("rest_vlr") is not None and r.get("rest_kalshi") is not None]
    if both:
        agree = sum(1 for r in both if (r["rest_vlr"] >= REST_GAP) == (r["rest_kalshi"] >= REST_GAP))
        L += ["", f"Proxy check: Kalshi-only schedule vs vlr.gg schedule agree on whether the rule fires in "
                  f"{agree} of {len(both)} matches ({agree / len(both):.0%})."]
        L.append(rule_line(val, "rest_kalshi", "All Valorant, rest from Kalshi's list only"))
    L.append("")

    for game, series in bw.GAMES:
        path = os.path.join(args.dataset, f"{series}.json")
        if not os.path.exists(path):
            continue
        rows, _ = bw.kalshi_only_rows(path)
        if len(rows) < 200:
            continue
        add_rest(rows, kalshi_schedule(rows), lambda r: r["fav"], lambda r: r["dog"], "rest_kalshi")
        L += [f"## {game} (rest from Kalshi's list only)", ""]
        L += table(rows, "rest_kalshi") + [""]
        L.append(rule_line(rows, "rest_kalshi", f"All {game}"))
        L.append("")
    text = "\n".join(L)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main()
