import random
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone

import veto_backtest as vb


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


class Times(unittest.TestCase):
    def test_ticker_time_is_new_york_with_daylight_saving(self):
        self.assertEqual(vb.kalshi_start("KXVALORANTGAME-26SEP290500G2PR"), utc(2026, 9, 29, 9, 0))
        # Clocks went back on 1 Nov 2026, so 13:00 New York is 18:00 UTC.
        self.assertEqual(vb.kalshi_start("KXVALORANTGAME-26NOV011300KRM8GC"), utc(2026, 11, 1, 18, 0))
        self.assertIsNone(vb.kalshi_start("KXVALORANTGAME-26APR02FUTGM"))
        self.assertEqual(vb.kalshi_day("KXVALORANTGAME-26APR02FUTGM"), utc(2026, 4, 2, 16, 0))


class SeriesMaths(unittest.TestCase):
    def test_series_prob(self):
        self.assertAlmostEqual(vb.series_prob([0.7], 1), 0.7)
        self.assertAlmostEqual(vb.series_prob([0.5] * 3, 3), 0.5)
        self.assertAlmostEqual(vb.series_prob([0.6] * 3, 3), 0.6 ** 2 + 2 * 0.6 ** 2 * 0.4)
        q1, q2, q3 = 0.8, 0.3, 0.6
        self.assertAlmostEqual(vb.series_prob([q1, q2, q3], 3), q1 * q2 + q1 * (1 - q2) * q3 + (1 - q1) * q2 * q3)
        self.assertAlmostEqual(vb.series_prob([0.5] * 5, 5), 0.5)

    def test_base_map_prob_inverts(self):
        for bo in (1, 3, 5):
            for p in (0.1, 0.5, 0.83):
                q = vb.base_map_prob(p, bo)
                self.assertAlmostEqual(vb.series_prob([q] * bo, bo), p, places=6)

    def test_map_advantage(self):
        rec = {"lotus": [8, 2], "bind": [2, 8], "haven": [5, 5]}
        self.assertGreater(vb.map_advantage(rec, "Lotus"), 0.3)
        self.assertLess(vb.map_advantage(rec, "Bind"), -0.3)
        self.assertAlmostEqual(vb.map_advantage(rec, "Corrode"), 0.0)   # never played: no adjustment
        self.assertAlmostEqual(vb.map_advantage({}, "Lotus"), 0.0)
        # Shrinkage: 2-0 counts for much less than 20-0.
        self.assertLess(vb.map_advantage({"lotus": [2, 0], "bind": [5, 5]}, "lotus"),
                        vb.map_advantage({"lotus": [20, 0], "bind": [5, 5]}, "lotus"))

    def test_model_moves_toward_the_team_with_better_maps(self):
        strong = {"lotus": [9, 1], "bind": [8, 2], "haven": [2, 8]}
        weak = {"lotus": [2, 8], "bind": [3, 7], "haven": [8, 2]}
        maps = ["Lotus", "Bind", "Haven"]
        self.assertGreater(vb.model_prob(0.5, maps, strong, weak), 0.55)
        self.assertLess(vb.model_prob(0.5, maps, weak, strong), 0.45)
        self.assertAlmostEqual(vb.model_prob(0.62, maps, {}, {}), 0.62, places=6)


class VetoParsing(unittest.TestCase):
    def test_maps_come_from_picks_and_decider(self):
        info = {"bo": 3, "veto": [["ban", "Ascent", "A"], ["ban", "Pearl", "B"], ["pick", "Lotus", "A"],
                                  ["pick", "Bind", "B"], ["ban", "Sunset", "A"], ["ban", "Split", "B"],
                                  ["decider", "Haven", ""]],
                "games": [["Lotus", True], ["Bind", True]]}
        self.assertEqual(vb.series_maps(info), ["Lotus", "Bind", "Haven"])

    def test_falls_back_to_full_game_list_but_never_a_short_one(self):
        self.assertEqual(vb.series_maps({"bo": 3, "veto": [], "games": [["A", True], ["B", True], ["C", False]]}),
                         ["A", "B", "C"])
        # Only the two maps that were played: using them would leak a 2-0 result.
        self.assertIsNone(vb.series_maps({"bo": 3, "veto": [], "games": [["A", True], ["B", True]]}))

    def test_unnamed_maps_are_not_used(self):
        info = {"bo": 3, "veto": [["pick", "Lotus", "A"], ["pick", "N/A", "B"], ["decider", "Haven", ""]],
                "games": [["Lotus", True], ["N/A", True], ["Haven", True]]}
        self.assertIsNone(vb.series_maps(info))

    def test_best_of_inferred_from_veto(self):
        self.assertEqual(vb.series_maps({"bo": 0, "veto": [["decider", "Lotus", ""]], "games": []}), ["Lotus"])


class Prices(unittest.TestCase):
    def test_candle_formats(self):
        new = {"end_period_ts": 100, "yes_bid": {"close_dollars": "0.4400"}, "yes_ask": {"close_dollars": "0.4600"},
               "price": {"close_dollars": "0.4500"}}
        old = {"end_period_ts": 100, "yes_bid": {"close": 44}, "yes_ask": {"close": 46}, "price": {"close": None}}
        self.assertEqual(vb.compact_candle(new), [100, 0.44, 0.46, 0.45])
        self.assertEqual(vb.compact_candle(old), [100, 0.44, 0.46, None])
        self.assertIsNone(vb.compact_candle({"yes_bid": {}}))

    def test_quote_at_uses_latest_candle_before(self):
        t = utc(2026, 9, 1, 12, 0)
        ts = int(t.timestamp())
        candles = [[ts - 600, 0.40, 0.42, 0.41], [ts - 60, 0.50, 0.52, 0.51], [ts + 60, 0.70, 0.72, 0.71]]
        q = vb.quote_at(candles, t)
        self.assertAlmostEqual(q["mid"], 0.51)
        self.assertEqual(q["age_s"], 60)
        self.assertIsNone(vb.quote_at(candles, t - timedelta(hours=1)))

    def test_wide_spread_uses_last_trade(self):
        t = utc(2026, 9, 1, 12, 0)
        q = vb.quote_at([[int(t.timestamp()), 0.10, 0.60, 0.33]], t)
        self.assertAlmostEqual(q["mid"], 0.33)
        self.assertIsNone(vb.quote_at([[int(t.timestamp()), None, None, None]], t))


def market(ticker, event, team, result, vol=100):
    return {"ticker": ticker, "event": event, "team": team, "result": result, "volume": vol, "tier": "live"}


class KalshiGrouping(unittest.TestCase):
    def test_matches(self):
        ms = [market("KXVALORANTGAME-26SEP290500G2PR-PR", "KXVALORANTGAME-26SEP290500G2PR", "Paper Rex", "yes"),
              market("KXVALORANTGAME-26SEP290500G2PR-G2", "KXVALORANTGAME-26SEP290500G2PR", "G2 Esports", "no"),
              market("KXVALORANTGAME-26SEP300500ABCD-AB", "KXVALORANTGAME-26SEP300500ABCD", "AB", ""),
              market("KXVALORANTGAME-26SEP300500ABCD-CD", "KXVALORANTGAME-26SEP300500ABCD", "CD", "")]
        rows, skipped = vb.kalshi_matches(ms)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["team_a"], r["team_b"], r["a_won"]), ("G2 Esports", "Paper Rex", False))
        self.assertEqual(r["start"], "2026-09-29T09:00:00Z")
        self.assertEqual(skipped, {"not settled yes/no": 1})
        self.assertEqual(r["kind"], "time")

    def test_markets_from_both_tiers(self):
        def get(path, params):
            if path == "/events":
                return {"events": [{"markets": [{"ticker": "T-A", "event_ticker": "T", "yes_sub_title": "A",
                                                 "result": "yes", "volume_fp": "12.5"}]}]}
            return {"markets": [{"ticker": "T-A", "event_ticker": "T", "result": "yes"},
                                {"ticker": "U-A", "event_ticker": "U", "yes_sub_title": "A", "result": "no"}]}
        ms = {m["ticker"]: m for m in vb.kalshi_markets(get)}
        self.assertEqual(ms["T-A"]["tier"], "live")
        self.assertEqual(ms["T-A"]["volume"], 12.5)
        self.assertEqual(ms["U-A"]["tier"], "historical")


class Matching(unittest.TestCase):
    def setUp(self):
        self.results = [
            {"id": 1, "dt": "2026-09-29T09:20:00Z", "ev": "", "n1": "Paper Rex", "g1": "PRX", "i1": 10,
             "n2": "G2 Esports", "g2": "G2", "i2": 11},
            {"id": 2, "dt": "2026-09-30T09:00:00Z", "ev": "", "n1": "Paper Rex", "g1": "PRX", "i1": 10,
             "n2": "G2 Esports", "g2": "G2", "i2": 11},
            {"id": 3, "dt": "2026-09-29T09:00:00Z", "ev": "", "n1": "G2 Gozen", "g1": "G2G", "i1": 12,
             "n2": "Paper Rex", "g2": "PRX", "i2": 10}]

    def test_closest_in_time_and_orientation(self):
        row = {"start": "2026-09-29T09:00:00Z", "team_a": "G2", "team_b": "Paper Rex"}
        hit, a_is_1 = vb.find_vlr(row, self.results)
        self.assertEqual(hit["id"], 1)
        self.assertFalse(a_is_1)

    def test_different_team_not_matched(self):
        row = {"start": "2026-10-05T09:00:00Z", "team_a": "G2", "team_b": "Paper Rex"}
        self.assertIsNone(vb.find_vlr(row, self.results)[0])
        self.assertFalse(vb.same_team("G2 Esports", "G2 Gozen", "G2G"))
        self.assertTrue(vb.same_team("KRÜ Esports", "KRU Esports", "KRU"))
        self.assertTrue(vb.same_team("TEC Esports", "Titan Esports Club", "TEC"))

    def test_sister_team_names(self):
        results = [{"id": 7, "dt": "2026-10-30T21:40:00Z", "ev": "", "n1": "KRÜ BLAZE", "g1": "KRUB", "i1": 1,
                    "n2": "MIBR GC", "g2": "MIBR.GC", "i2": 2},
                   {"id": 8, "dt": "2026-10-23T09:00:00Z", "ev": "", "n1": "CGN Esports", "g1": "CGN", "i1": 3,
                    "n2": "Natus Vincere Junior", "g2": "NVJ", "i2": 4}]
        hit, a_is_1 = vb.find_vlr({"start": "2026-10-30T21:00:00Z", "team_a": "KRÜ Blaze",
                                   "team_b": "MIBR Female"}, results)
        self.assertEqual((hit["id"], a_is_1), (7, True))
        hit, a_is_1 = vb.find_vlr({"start": "2026-10-23T08:00:00Z", "team_a": "CGN Esports",
                                   "team_b": "Natus Vincere"}, results)
        self.assertEqual(hit["id"], 8)
        results.append({"id": 10, "dt": "2026-10-22T18:00:00Z", "ev": "", "n1": "FENNEL GC", "g1": "FLGC", "i1": 5,
                        "n2": "MIBR GC", "g2": "MIBR.GC", "i2": 2})
        hit, a_is_1 = vb.find_vlr({"start": "2026-10-22T18:00:00Z", "team_a": "FENNEL Female",
                                   "team_b": "MIBR Female"}, results)
        self.assertEqual((hit["id"], a_is_1), (10, True))
        # The loose rule only applies close in time.
        self.assertIsNone(vb.find_vlr({"start": "2026-10-31T09:00:00Z", "team_a": "KRÜ Blaze",
                                       "team_b": "MIBR Female"}, results)[0])

    def test_date_only_ticker_uses_vlr_time(self):
        row = {"start": "2026-04-02T16:00:00Z", "kind": "date", "team_a": "CGN Esports", "team_b": "Natus Vincere Junior"}
        res = [{"id": 9, "dt": "2026-04-02T23:30:00Z", "ev": "", "n1": "CGN Esports", "g1": "CGN", "i1": 3,
                "n2": "Natus Vincere Junior", "g2": "NVJ", "i2": 4}]
        hit, _ = vb.find_vlr(row, res)
        self.assertEqual(vb.match_t0(row, {"dt": "2026-04-02T23:35:00Z"}, hit), utc(2026, 4, 2, 23, 35))
        self.assertEqual(vb.match_t0(dict(row, kind="time"), None, hit), utc(2026, 4, 2, 16, 0))

    def test_event_level(self):
        self.assertEqual(vb.event_level("Champions Tour 2026: Pacific Stage 2"), "top")
        self.assertEqual(vb.event_level("Valorant Masters London 2026"), "top")
        self.assertEqual(vb.event_level("VCT 2026: China Threshold"), "lower")
        self.assertEqual(vb.event_level("Game Changers 2026: Championship"), "lower")


class Statistics(unittest.TestCase):
    def test_offset_logit_recovers_weight(self):
        rnd = random.Random(3)
        ys, offs, xs = [], [], []
        for _ in range(4000):
            o, x = rnd.gauss(0, 1), rnd.gauss(0, 0.6)
            ys.append(1 if rnd.random() < vb.sigmoid(o + x) else 0)
            offs.append(o)
            xs.append(x)
        b, se = vb.fit_offset_logit(ys, offs, xs)
        self.assertAlmostEqual(b, 1.0, delta=3 * se)
        b0, se0 = vb.fit_offset_logit(ys, offs, [rnd.gauss(0, 0.6) for _ in xs])
        self.assertLess(abs(b0), 3 * se0)

    def test_bets(self):
        rows = [{"event": "a", "model": 0.60, "y": 1, "post_q": {"bid": 0.48, "ask": 0.50}},
                {"event": "b", "model": 0.30, "y": 1, "post_q": {"bid": 0.40, "ask": 0.42}},
                {"event": "c", "model": 0.51, "y": 1, "post_q": {"bid": 0.48, "ask": 0.50}}]
        bets = vb.simulate_bets(rows, 0.05)
        self.assertEqual([b["event"] for b in bets], ["a", "b"])
        fee = 0.0175                                                     # $1.75 per 100 contracts at 50¢
        self.assertAlmostEqual(bets[0]["ret"], (1 - (0.50 + fee)) / (0.50 + fee))
        self.assertAlmostEqual(bets[1]["price"], 0.60)                   # bought NO at 1 - 0.40
        self.assertEqual(bets[1]["ret"], -1.0)

    def test_bootstrap(self):
        lo, hi = vb.bootstrap_mean_ci([0.1] * 50)
        self.assertAlmostEqual(lo, 0.1)
        self.assertAlmostEqual(hi, 0.1)
        self.assertEqual(vb.bootstrap_mean_ci([]), (None, None))


MAPS = ["Lotus", "Bind", "Haven", "Sunset", "Corrode", "Abyss", "Ascent"]


def synthetic_cache(folder, n=300, market_absorbs=True, informative=True, seed=11):
    """Matches where map records matter (or not), and the market prices the veto (or not)."""
    rnd = random.Random(seed)
    cache = vb.Cache(folder)
    markets, results = [], []
    t_base = utc(2026, 9, 1, 15, 0)
    for i in range(n):
        t0 = t_base + timedelta(hours=7 * i)
        local = t0.astimezone(vb.ET)
        ev = f"KXVALORANTGAME-{local.strftime('%y%b%d%H%M').upper()}T{i:03d}X{i:03d}"
        maps = rnd.sample(MAPS, 3)
        rec_a = {m.lower(): [rnd.randint(0, 10), rnd.randint(0, 10)] for m in MAPS}
        rec_b = {m.lower(): [rnd.randint(0, 10), rnd.randint(0, 10)] for m in MAPS}
        p_pre = min(max(rnd.gauss(0.5, 0.15), 0.08), 0.92)
        p_true = vb.model_prob(p_pre, maps, rec_a, rec_b) if informative else p_pre
        a_won = rnd.random() < p_true
        p_post = p_true if market_absorbs else p_pre
        a, b = f"Team{i}A", f"Team{i}B"
        markets += [market(f"{ev}-A", ev, a, "yes" if a_won else "no"),
                    market(f"{ev}-B", ev, b, "no" if a_won else "yes")]
        results.append({"id": 1000 + i, "dt": vb.iso(t0 + timedelta(minutes=5)), "ev": "VCT test",
                        "n1": a, "g1": "", "i1": 2 * i + 1, "n2": b, "g2": "", "i2": 2 * i + 2})
        cache["vlr_info"][str(1000 + i)] = {"dt": vb.iso(t0 + timedelta(minutes=5)), "bo": 3, "event": "VCT test",
                                            "t1": 2 * i + 1, "t2": 2 * i + 2, "forfeit": False,
                                            "veto": [["pick", maps[0], a], ["pick", maps[1], b],
                                                     ["decider", maps[2], ""]], "games": []}
        end = (t0 - timedelta(days=1)).date().isoformat()
        cache["vlr_stats"][f"{2 * i + 1}|{end}"] = rec_a
        cache["vlr_stats"][f"{2 * i + 2}|{end}"] = rec_b
        ts = int(t0.timestamp())
        cache["candles"][f"{ev}-A"] = [[ts - 3700, p_pre - 0.01, p_pre + 0.01, p_pre],
                                       [ts + 300, p_post - 0.01, p_post + 0.01, p_post]]
    cache["kalshi"]["markets"] = markets
    cache["vlr_results"]["rows"] = results
    return cache


class EndToEnd(unittest.TestCase):
    def run_case(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            cache = synthetic_cache(d, **kw)
            rows, funnel, reasons, offsets, unmatched = vb.build_rows(cache)
            res = vb.analyse(rows)
            return rows, funnel, res, vb.render(rows, funnel, reasons, offsets, unmatched, res)

    def test_information_absorbed_by_market(self):
        rows, funnel, res, text = self.run_case(n=400, market_absorbs=True)
        self.assertEqual(funnel["used (pre price, veto, map records)"], 400)
        b, se = res["info"]
        self.assertGreater(b / se, 2)
        self.assertIn("already absorbed", text)
        self.assertIn("vlr.gg minus Kalshi: median +5 min", text)
        self.assertIn("Big matches versus small ones", text)

    def test_market_ignores_maps_shows_edge(self):
        rows, funnel, res, text = self.run_case(n=600, market_absorbs=False)
        b, se = res["left"]
        self.assertGreater(b / se, 2)
        self.assertIn("Possible edge", text)

    def test_no_information(self):
        rows, funnel, res, text = self.run_case(n=400, informative=False)
        self.assertIn("No edge found", text)

    def test_too_few(self):
        rows, funnel, res, text = self.run_case(n=40)
        self.assertIn("Too few matches", text)


class FakeVlr:
    def __init__(self, cache):
        src = cache
        self.calls = []
        outer = self

        class M:
            def completed(self, page=1):
                outer.calls.append(("results", page))
                rows = src["vlr_results"]["rows"]
                chunk = rows[(page - 1) * 50: page * 50]
                data = [{"match_id": r["id"], "datetime": r["dt"], "event": r["ev"],
                         "team1": {"name": r["n1"], "tag": r["g1"], "id": r["i1"]},
                         "team2": {"name": r["n2"], "tag": r["g2"], "id": r["i2"]}} for r in chunk]
                return types.SimpleNamespace(matches=data, has_next_page=page * 50 < len(rows))

        class S:
            def info(self, series_id):
                outer.calls.append(("info", series_id))
                i = src["vlr_info"][str(series_id)]
                return {"datetime": i["dt"], "best_of": i["bo"], "event_name": i["event"],
                        "team1": {"id": i["t1"]}, "team2": {"id": i["t2"]}, "forfeit": {"forfeited": False},
                        "veto": [{"veto_type": k, "map_name": m, "team": t} for k, m, t in i["veto"]],
                        "games": []}

        class T:
            def stats(self, team_id, date_start, date_end):
                outer.calls.append(("stats", team_id))
                rec = src["vlr_stats"][f"{team_id}|{date_end.isoformat()}"]
                return {"maps": [{"map_name": m.title(), "wins": w, "losses": l} for m, (w, l) in rec.items()]}

        self.matches, self.series, self.team = M(), S(), T()


class Collect(unittest.TestCase):
    def test_collect_fills_cache_and_report_matches_source(self):
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as out_dir:
            src = synthetic_cache(src_dir, n=60)
            fake = FakeVlr(src)

            def get(path, params):
                if path == "/events":
                    return {"events": []}
                if path == "/historical/markets":
                    return {"markets": [{"ticker": m["ticker"], "event_ticker": m["event"],
                                         "yes_sub_title": m["team"], "result": m["result"]}
                                        for m in src["kalshi"]["markets"]]}
                ticker = path.split("/")[3]
                return {"candlesticks": [{"end_period_ts": c[0], "yes_bid": {"close_dollars": str(c[1])},
                                          "yes_ask": {"close_dollars": str(c[2])}, "price": {"close_dollars": str(c[3])}}
                                         for c in src["candles"][ticker]]}

            args = types.SimpleNamespace(budget_minutes=5, since=None, refresh_kalshi=False, max_matches=0,
                                         max_pages=50, aliases=None, vlr_rps=10)
            cache = vb.Cache(out_dir)
            vb.collect(args, cache, get=get, vlr=fake, log=lambda s: None)
            rows, funnel, *_ = vb.build_rows(vb.Cache(out_dir))
            self.assertEqual(funnel["used (pre price, veto, map records)"], 60)
            ref, *_ = vb.build_rows(src)
            self.assertEqual([round(r["model"], 9) for r in rows], [round(r["model"], 9) for r in ref])
            # A second run uses the cache: no more detail calls.
            n_calls = len([c for c in fake.calls if c[0] != "results"])
            vb.collect(args, vb.Cache(out_dir), get=get, vlr=fake, log=lambda s: None)
            self.assertEqual(len([c for c in fake.calls if c[0] != "results"]), n_calls)


if __name__ == "__main__":
    unittest.main()
