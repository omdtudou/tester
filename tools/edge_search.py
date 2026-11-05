"""Look for a pricing edge in Kalshi esports match markets, with an out-of-sample check.

The hypotheses are fixed in advance (HYPOTHESES below). Each one is fitted on
the earlier half of the matches (by date) and then tested, unchanged, on the
later half. A hypothesis counts only if it holds in the later half after a
correction for testing many ideas (Holm), and if betting on it there makes
money after Kalshi's fee at the quoted ask.

    python tools/edge_search.py            # Valorant (+ other games if collected)
"""
import argparse
import math
import os
import random
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_workbook as bw  # noqa: E402
import veto_backtest as vb  # noqa: E402

FEE = 0.07
BET_GAP = 0.03


# --------------------------------------------------------------------------- statistics

def sigmoid(x):
    return vb.sigmoid(x)


def logit(p):
    return vb.logit(p)


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            raise ValueError("singular")
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def inverse(A):
    n = len(A)
    cols = [solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def fit(X, y, off):
    """Logistic regression with an offset (the market's log-odds). Returns (coefs, standard errors)."""
    k = len(X[0])
    b = [0.0] * k
    H = None
    for _ in range(60):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for xi, yi, oi in zip(X, y, off):
            p = sigmoid(oi + sum(bj * xj for bj, xj in zip(b, xi)))
            w = p * (1 - p)
            for a in range(k):
                g[a] += (yi - p) * xi[a]
                for c in range(k):
                    H[a][c] += w * xi[a] * xi[c]
        step = solve(H, g)
        b = [bj + sj for bj, sj in zip(b, step)]
        if max(abs(s) for s in step) < 1e-10:
            break
    cov = inverse(H)
    return b, [math.sqrt(max(cov[i][i], 0)) for i in range(k)]


def p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def fee(p):
    """Kalshi taker fee per contract on a 100-contract order (rounded up to the cent)."""
    return math.ceil(round(FEE * 100 * p * (1 - p) * 100, 6)) / 100 / 100


def bets_from_model(rows, predict):
    """Bet the side the model prefers by BET_GAP or more, at the ask 10 min before, after fee."""
    out = []
    for r in rows:
        p = predict(r)
        if p is None or r.get("ask10") is None or r.get("bid10") is None:
            continue
        if p - r["ask10"] >= BET_GAP:
            cost = r["ask10"] + fee(r["ask10"])
            out.append((1.0 if r["won"] else 0.0) / cost - 1)
        elif r["bid10"] - p >= BET_GAP:
            price = 1 - r["bid10"]
            cost = price + fee(price)
            out.append((0.0 if r["won"] else 1.0) / cost - 1)
    return out


def mean_ci(vals, n=2000, seed=5):
    if not vals:
        return None, None, None
    rnd = random.Random(seed)
    means = sorted(sum(rnd.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return sum(vals) / len(vals), means[int(0.05 * n)], means[int(0.95 * n) - 1]


# --------------------------------------------------------------------------- features

def add_history_features(rows, results=None, name_to_id=None):
    """Features that need earlier matches: team over/under-performance vs price, rematches, rest days."""
    rows = sorted(rows, key=lambda r: r["date"])
    hist = defaultdict(list)          # team -> [(date, residual vs price, won)]
    meetings = {}                     # frozenset(teams) -> (date, winner)
    for r in rows:
        d = r["date"]
        feats = {}
        for side in ("fav", "dog"):
            t = r[side]
            recent = [h for h in hist[t] if (d - h[0]).days <= 120][-10:]
            feats[side + "_resid"] = sum(h[1] for h in recent)
            feats[side + "_n"] = len(recent)
            last5 = hist[t][-5:]
            feats[side + "_form"] = (sum(h[2] for h in last5) / len(last5)) if last5 else None
        r["x_resid"] = feats["fav_resid"] - feats["dog_resid"]
        r["x_form"] = (feats["fav_form"] - feats["dog_form"]
                       if feats["fav_form"] is not None and feats["dog_form"] is not None else None)
        key = frozenset((r["fav"], r["dog"]))
        prev = meetings.get(key)
        r["x_rematch"] = None
        if prev and (d - prev[0]).days <= 30:
            r["x_rematch"] = 1.0 if prev[1] == r["fav"] else -1.0
        if r.get("c10") is not None:
            for side, won in (("fav", r["won"]), ("dog", 1 - r["won"])):
                price = r["c10"] if side == "fav" else 1 - r["c10"]
                hist[r[side]].append((d, won - price, won))
            meetings[key] = (d, r["fav"] if r["won"] else r["dog"])
    if results is not None and name_to_id is not None:
        times = defaultdict(list)
        for x in results:
            dt = vb.parse_iso(x["dt"])
            if dt is None:
                continue
            local = dt.astimezone(vb.ET).replace(tzinfo=None)
            for tid in (x["i1"], x["i2"]):
                if tid:
                    times[tid].append(local)
        for v in times.values():
            v.sort()
        for r in rows:
            rest = []
            for side in ("fav", "dog"):
                tid = name_to_id.get((r["vlr"], r[side]))
                ts = times.get(tid, [])
                i = bisect_left(ts, r["date"] - timedelta(hours=3))
                rest.append(min((r["date"] - ts[i - 1]).total_seconds() / 86400, 14) if i > 0 else 14)
            r["x_rest"] = rest[0] - rest[1]
    return rows


def hypotheses(game):
    """(name, what it means, subset filter, feature). Feature None = bias inside the subset."""
    H = [
        ("Favorite-longshot bias", "Are favorites under- or over-priced more the further from 50%? "
         "(feature: the price's log-odds)", lambda r: True, lambda r: logit(r["c10"])),
        ("Late price move", "Does the move from 1 h to 10 min before keep going (follow it) or reverse (fade it)?",
         lambda r: r.get("c1h") is not None, lambda r: logit(r["c10"]) - logit(r["c1h"])),
        ("Thin markets", "Is the favorite mispriced when the spread 10 min before is over 3¢?",
         lambda r: r.get("ask10") is not None and r.get("bid10") is not None and r["ask10"] - r["bid10"] > 0.03,
         None),
        ("Near coin flips", "Is the favorite mispriced when priced 50–55%?", lambda r: r["c10"] < 0.55, None),
        ("Overnight matches (midnight–8am New York)", "Thin US trading hours",
         lambda r: r["date"].hour < 8, None),
        ("Teams beating their prices", "Do teams that beat (or missed) their prices in their last 10 matches keep "
         "doing so? (feature: fav's summed surprise minus dog's)", lambda r: True, lambda r: r["x_resid"]),
        ("Recent form", "Last-5 win rate, favorite minus underdog", lambda r: r.get("x_form") is not None,
         lambda r: r["x_form"]),
        ("Rematch within 30 days", "Does the winner of their last meeting win more than priced? "
         "(+1 = favorite won it, −1 = underdog did)", lambda r: r.get("x_rematch") is not None,
         lambda r: r["x_rematch"]),
    ]
    if game == "Valorant":
        H += [
            ("Lower-tier events", "Challengers, Game Changers and other non-VCT events",
             lambda r: r["group"] not in ("International", "VCT league"), None),
            ("Top-tier events", "VCT leagues, Masters, Champions, EWC",
             lambda r: r["group"] in ("International", "VCT league"), None),
            ("Best of 5", "Longer series favor the better team; is that priced?", lambda r: r.get("bo") == 5, None),
            ("Rest days", "Days since each team's previous vlr.gg match (capped at 14), favorite minus underdog",
             lambda r: r.get("x_rest") is not None, lambda r: r["x_rest"]),
        ]
    return H


# --------------------------------------------------------------------------- run

def test_all(game, rows):
    rows = [r for r in rows if r.get("c10") is not None and 0.0 < r["c10"] < 1.0]
    rows.sort(key=lambda r: r["date"])
    cut = rows[len(rows) // 2]["date"]
    early = [r for r in rows if r["date"] < cut]
    late = [r for r in rows if r["date"] >= cut]
    out = []
    for name, meaning, keep, feat in hypotheses(game):
        res = {"name": name, "meaning": meaning}
        for label, part in (("early", early), ("late", late)):
            sub = [r for r in part if keep(r)]
            res[label + "_n"] = len(sub)
            if len(sub) < 30:
                res[label] = None
                continue
            X = [[1.0] if feat is None else [1.0, feat(r)] for r in sub]
            try:
                b, se = fit(X, [r["won"] for r in sub], [logit(r["c10"]) for r in sub])
            except ValueError:
                res[label] = None
                continue
            j = len(b) - 1
            res[label] = (b, se, b[j] / se[j] if se[j] > 0 else 0.0, p_two_sided(b[j] / se[j]) if se[j] > 0 else 1.0)
        # Strategy fitted on the early half, applied unchanged to the late half.
        if res.get("early"):
            b = res["early"][0]

            def predict(r, b=b, keep=keep, feat=feat):
                if not keep(r):
                    return None
                x = [1.0] if feat is None else [1.0, feat(r)]
                return sigmoid(logit(r["c10"]) + sum(bj * xj for bj, xj in zip(b, x)))
            res["bets"] = mean_ci(bets_from_model(late, predict))
            res["n_bets"] = len(bets_from_model(late, predict))
        out.append(res)
    # Holm correction on the late-half p-values
    ps = sorted((r["late"][3], i) for i, r in enumerate(out) if r.get("late"))
    m = len(ps)
    running = 0.0
    for rank, (p, i) in enumerate(ps):
        running = max(running, min(1.0, (m - rank) * p))
        out[i]["holm"] = running
    return out, cut, len(early), len(late)


def render(game, out, cut, n_early, n_late):
    L = [f"## {game}", "",
         f"Earlier half: {n_early} matches before {cut:%Y-%m-%d}. Later half: {n_late} matches from then on.", "",
         "| Idea | Earlier half: effect (± ) p | Later half: effect (±) p | After correcting for "
         f"{len(out)} ideas | Later-half bets | Avg return (90% range) |",
         "|---|---|---|---|---|---|"]
    for r in out:
        def eff(x):
            if not x:
                return "too few"
            b, se, z, p = x
            j = len(b) - 1
            return f"{b[j]:+.2f} (± {se[j]:.2f}) p={p:.2f}"
        bets = r.get("bets") or (None, None, None)
        ret = (f"{bets[0] * 100:+.1f}% ({bets[1] * 100:+.1f} to {bets[2] * 100:+.1f})" if bets[0] is not None else "–")
        holm = f"p={r['holm']:.2f}" if r.get("holm") is not None else "–"
        L.append(f"| {r['name']} | {eff(r.get('early'))} | {eff(r.get('late'))} | {holm} | "
                 f"{r.get('n_bets', 0)} | {ret} |")
    L.append("")
    for r in out:
        L.append(f"- **{r['name']}**: {r['meaning']}")
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", default="data/backtest")
    ap.add_argument("--dataset", default="data/dataset")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cache = vb.Cache(args.backtest)
    val, _ = bw.valorant_rows(cache)
    name_to_id = {}
    for r in val:
        info = cache["vlr_info"].get(r["vlr"].rsplit("/", 1)[1])
        if info:
            name_to_id[(r["vlr"], info["n1"])] = info["t1"]
            name_to_id[(r["vlr"], info["n2"])] = info["t2"]
    games = {"Valorant": add_history_features(val, cache["vlr_results"].get("rows", []), name_to_id)}
    for game, series in bw.GAMES:
        path = os.path.join(args.dataset, f"{series}.json")
        if os.path.exists(path):
            rows, _ = bw.kalshi_only_rows(path)
            if len(rows) > 200:
                games[game] = add_history_features(rows)
    text = ["# Edge search", "",
            "Each idea is fitted on the earlier half of the matches and tested unchanged on the later half. "
            "Effect > 0 means the favorite wins more than its price says (for a feature: when the feature is "
            "higher). Returns: betting the side the earlier-half fit prefers by 3¢+, at the ask 10 min before, "
            "after Kalshi's fee.", ""]
    for game, rows in games.items():
        out, cut, ne, nl = test_all(game, rows)
        text.append(render(game, out, cut, ne, nl))
    report = "\n".join(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)


if __name__ == "__main__":
    main()
