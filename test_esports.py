"""Tests for arbscan's esports mode. Run with:  python -m unittest test_esports"""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

import arbscan
import esports as E

HERE = os.path.dirname(os.path.abspath(__file__))
FEES = {"kalshi": 0.07, "polymarket_us": 0.05}


def replay_http():
    with open(os.path.join(HERE, "sample_esports.json"), encoding="utf-8") as f:
        return E.Http(replay=json.load(f)["responses"])


def pm_market(slug, question, sides, **extra):
    m = {"slug": slug, "question": question, "active": True, "closed": False, "sportsMarketTypeV2": "MONEYLINE",
         "marketSides": [{"description": n, "identifier": n[:3].upper(), "long": lg} for n, lg in sides]}
    m.update(extra)
    return m


def listing(venue, names, start=None, kind="none", game="valorant", fmt=None):
    keys = [E.team_key(n) for n in names]
    return E.Listing(venue=venue, game=game, title=" vs ".join(names), names=dict(zip(keys, names)),
                     ids={k: f"{venue}-{k}" for k in keys}, start=start, start_kind=kind,
                     long_key=keys[0] if venue == "polymarket_us" else None, fmt=fmt)


class TeamNames(unittest.TestCase):
    def test_equivalent_names(self):
        self.assertEqual(E.team_key("Team Liquid"), E.team_key("Liquid"))
        self.assertEqual(E.team_key("Leviatán Esports"), E.team_key("Leviatan"))
        self.assertEqual(E.team_key("G2 Esports"), E.team_key("G2"))
        self.assertEqual(E.team_key("Natus Vincere"), E.team_key("NAVI"))
        self.assertEqual(E.team_key("KRÜ Esports"), E.team_key("KRU"))

    def test_different_teams_stay_different(self):
        self.assertNotEqual(E.team_key("Spirit Academy"), E.team_key("Team Spirit"))
        self.assertNotEqual(E.team_key("Team Liquid Brazil"), E.team_key("Team Liquid"))
        self.assertNotEqual(E.team_key("Karmine Corp Blue"), E.team_key("Karmine Corp"))

    def test_alias_file_works_in_either_direction(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"Movistar KOI": "KOI"}, f)
        try:
            aliases = E.load_aliases(f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(E.team_key("Movistar KOI", aliases), E.team_key("KOI", aliases))


class KalshiTickers(unittest.TestCase):
    def test_time_in_ticker_is_eastern(self):
        start, kind = E.parse_kalshi_start("KXCS2GAME-26OCT131200HACPRO")
        self.assertEqual(kind, "time")
        self.assertEqual(start, datetime(2026, 10, 13, 17, 0, tzinfo=timezone.utc))

    def test_date_only_ticker(self):
        start, kind = E.parse_kalshi_start("KXVALORANTGAME-26FEB07LEVC9")
        self.assertEqual(kind, "date")
        self.assertEqual(start.date(), datetime(2026, 2, 7).date())

    def test_unparseable_ticker(self):
        self.assertEqual(E.parse_kalshi_start("KXLOLGAME")[1], "none")


class PolymarketListings(unittest.TestCase):
    def test_long_side_is_read_from_the_flag_not_the_order(self):
        m = pm_market("aec-lol-t1-gen-2026-11-07", "League of Legends: T1 vs Gen.G (BO5)",
                      [("Gen.G", True), ("T1", False)])
        l, why = E.pmus_listing(m, None, {})
        self.assertEqual(why, "ok")
        self.assertEqual(l.long_key, E.team_key("Gen.G"))
        self.assertEqual((l.game, l.fmt, l.start_kind), ("lol", "BO5", "date"))

    def test_rejections(self):
        cases = {
            "single map/game or prop market": pm_market("val-a-b-map1", "Valorant: A vs B - Map 1 Winner",
                                                        [("Alpha", True), ("Bravo", False)]),
            "best-of-2 (can end in a draw)": pm_market("dota-a-b", "Dota 2: A vs B (BO2)",
                                                       [("Alpha", True), ("Bravo", False)]),
            "not a series-winner market": pm_market("val-a-b-total", "Valorant: A vs B",
                                                    [("Alpha", True), ("Bravo", False)], sportsMarketTypeV2="TOTAL"),
            "can't tell which side is which": pm_market("val-a-b", "Valorant: A vs B",
                                                        [("Alpha", True), ("Bravo", True)]),
            "sides aren't team names": pm_market("val-x", "Valorant: will it happen", [("Yes", True), ("No", False)]),
        }
        for why, m in cases.items():
            self.assertEqual(E.pmus_listing(m, "valorant", {}), (None, why))

    def test_markets_found_at_any_nesting(self):
        found = []
        E._find_markets({"events": [{"markets": [pm_market("s1", "q", [("A", True), ("B", False)])]}],
                         "markets": [pm_market("s2", "q", [("A", True), ("B", False)])]}, found)
        self.assertEqual(sorted(m["slug"] for m in found), ["s1", "s2"])


class Matching(unittest.TestCase):
    d1 = datetime(2026, 11, 7, 20, tzinfo=timezone.utc)

    def test_same_teams_same_day_pair(self):
        k = listing("kalshi", ["Cloud9", "Leviatán Esports"], self.d1, "time")
        p = listing("polymarket_us", ["Cloud9", "Leviatan"], self.d1, "date")
        pairs, *_ = E.match([k], [p])
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0].confirmed_date)

    def test_different_week_does_not_pair(self):
        k = listing("kalshi", ["Cloud9", "Leviatán"], self.d1, "time")
        p = listing("polymarket_us", ["Cloud9", "Leviatán"], datetime(2026, 11, 14, tzinfo=timezone.utc), "date")
        self.assertEqual(E.match([k], [p])[0], [])

    def test_rematch_without_dates_is_left_out(self):
        ks = [listing("kalshi", ["Cloud9", "Leviatán"]), listing("kalshi", ["Cloud9", "Leviatán"])]
        p = listing("polymarket_us", ["Cloud9", "Leviatán"])
        pairs, _, _, ambiguous = E.match(ks, [p])
        self.assertEqual(pairs, [])
        self.assertGreaterEqual(ambiguous, 1)

    def test_unique_match_without_dates_pairs_but_is_flagged(self):
        pairs, *_ = E.match([listing("kalshi", ["Cloud9", "Leviatán"])],
                            [listing("polymarket_us", ["Cloud9", "Leviatán"])])
        self.assertEqual(len(pairs), 1)
        self.assertFalse(pairs[0].confirmed_date)

    def test_other_game_never_pairs(self):
        k = listing("kalshi", ["Cloud9", "G2"], game="cs2")
        p = listing("polymarket_us", ["Cloud9", "G2"], game="valorant")
        self.assertEqual(E.match([k], [p])[0], [])


class Books(unittest.TestCase):
    def test_kalshi_bids_become_asks_on_the_other_side(self):
        self.assertEqual(E.flip([(0.55, 120.0), (0.54, 300.0)]), [(0.45, 120.0), (0.46, 300.0)])

    def test_kalshi_book_formats(self):
        http = E.Http(replay={
            f"{E.KALSHI_API}/markets/NEW/orderbook": {"orderbook_fp": {"yes_dollars": [["0.4200", "13.00"]],
                                                                       "no_dollars": [["0.5500", "7.50"]]}},
            f"{E.KALSHI_API}/markets/OLD/orderbook": {"orderbook": {"yes": [[42, 13]], "no": [[55, 7]]}},
        })
        self.assertEqual(E.kalshi_book(http, "NEW"), ([(0.42, 13.0)], [(0.55, 7.5)]))
        self.assertEqual(E.kalshi_book(http, "OLD"), ([(0.42, 13.0)], [(0.55, 7.0)]))

    def test_pmus_book_ignores_prices_in_unknown_units(self):
        http = E.Http(replay={f"{E.PMUS_API}/v1/markets/x/book": {"marketData": {
            "state": "MARKET_STATE_OPEN",
            "bids": [{"px": {"value": "0.55"}, "qty": "10"}, {"px": "650", "qty": "5"}],
            "offers": [{"px": "0.57", "qty": "4.5"}]}}})
        self.assertEqual(E.pmus_book(http, "x"), ("MARKET_STATE_OPEN", [(0.55, 10.0)], [(0.57, 4.5)]))


class Sizing(unittest.TestCase):
    def test_fee_is_rounded_up_per_price_level(self):
        w = E.Walker([(0.50, 60.0), (0.51, 200.0)], 0.05)
        for _ in range(101):
            w.add_one()
        self.assertAlmostEqual(w.cost, 60 * 0.50 + 41 * 0.51)
        self.assertEqual(w.fee, 0.75 + 0.52)   # 0.75 and 0.5123 -> 0.52
        self.assertEqual(w.worst, 0.51)

    def test_optimiser_respects_budget_and_depth(self):
        a, b = [(0.45, 120.0), (0.46, 300.0)], [(0.50, 60.0), (0.51, 200.0)]
        for budget in (10, 50, 100, 1000):
            r = E.optimise(a, 0.07, b, 0.05, budget)
            self.assertLessEqual(r["outlay"], budget)
            self.assertLessEqual(r["n"], 260)
            self.assertAlmostEqual(r["profit"], r["n"] - r["outlay"], places=6)
            self.assertGreater(r["profit"], 0)

    def test_no_arb_when_books_cross_one_dollar(self):
        r = E.optimise([(0.50, 100.0)], 0.07, [(0.49, 100.0)], 0.05, 100)
        self.assertLessEqual(r["profit"], 0)


class EndToEnd(unittest.TestCase):
    def scan(self, **kw):
        return E.scan(replay_http(), list(E.GAMES), {}, {}, FEES, kw.get("budget", 100.0), 0.25)

    def test_demo_finds_the_two_real_arbs(self):
        arbs, stats, disc, (un_k, un_p, ambiguous) = self.scan()
        self.assertEqual(len(arbs), 2)
        self.assertEqual((stats.pairs, stats.gross_only), (3, 1))
        for a in arbs:
            self.assertLessEqual(a.outlay, 100)
            self.assertEqual({l.venue for l in a.legs}, {"kalshi", "polymarket_us"})
            self.assertNotEqual(a.legs[0].team, a.legs[1].team, "the two legs must back different teams")
            self.assertAlmostEqual(a.profit, a.legs[0].contracts - a.outlay, places=2)

    def test_team_swap_trap(self):
        arbs = self.scan()[0]
        lol = next(a for a in arbs if a.game == "lol")
        pm = next(l for l in lol.legs if l.venue == "polymarket_us")
        k = next(l for l in lol.legs if l.venue == "kalshi")
        self.assertEqual((pm.team, pm.limit), ("T1", 0.36))     # short side: 1 - best bid 0.64
        self.assertEqual(k.team, "Gen.G")

    def test_lookalike_teams_and_map_markets_never_pair(self):
        _, _, disc, (un_k, un_p, _) = self.scan()
        only_kalshi = {frozenset(l.names.values()) for l in un_k}
        self.assertIn(frozenset({"Team Spirit", "FaZe Clan"}), only_kalshi)
        self.assertIn(frozenset({"Sentinels", "KRÜ Esports"}), only_kalshi)
        self.assertEqual(disc.skipped["polymarket us: best-of-2 (can end in a draw)"], 1)

    def test_empty_books_are_counted_not_silently_dropped(self):
        http = replay_http()
        for url in list(http.replay):
            if url.endswith("/orderbook"):
                http.replay[url] = {"orderbook_fp": {"yes_dollars": [], "no_dollars": []}}
        arbs, stats, *_ = E.scan(http, list(E.GAMES), {}, {}, FEES, 100.0, 0.25)
        self.assertEqual((arbs, stats.empty_books), ([], 3))

    def test_market_not_open_is_skipped(self):
        http = replay_http()
        url = f"{E.PMUS_API}/v1/markets/aec-lol-t1-gen-2026-11-07/book"
        http.replay[url]["marketData"]["state"] = "MARKET_STATE_PREOPEN"
        arbs, stats, *_ = E.scan(http, ["lol"], {}, {}, FEES, 100.0, 0.25)
        self.assertEqual((arbs, stats.not_open), ([], 1))


class LiveApiShapes(unittest.TestCase):
    """Fixes found by running against the live APIs from GitHub Actions on 2026-11-05."""

    def test_live_market_type_values(self):
        ok = pm_market("aec-cs2-a-b-2026-11-05", "Who will win A vs B", [("Alpha", True), ("Bravo", False)],
                       sportsMarketTypeV2="SPORTS_MARKET_TYPE_MONEYLINE", sportsMarketType="esports_match_winner")
        fut = dict(ok, sportsMarketTypeV2="SPORTS_MARKET_TYPE_FUTURE", slug="x-cs2-future")
        self.assertEqual(E.pmus_listing(ok, "cs2", {})[1], "ok")
        self.assertEqual(E.pmus_listing(fut, "cs2", {}), (None, "not a series-winner market"))

    def test_resolved_status_is_skipped(self):
        m = pm_market("aec-cs2-a-b", "A vs B", [("Alpha", True), ("Bravo", False)], status="MARKET_STATUS_RESOLVED")
        self.assertEqual(E.pmus_listing(m, "cs2", {}), (None, "closed"))

    def test_market_fee_coefficient_is_used(self):
        http = replay_http()
        for url, body in http.replay.items():
            if "/v1/search" in url and body:
                for ev in body.get("events", []):
                    for m in ev.get("markets", []):
                        m["feeCoefficient"] = 0.0695
        arbs = E.scan(http, ["lol"], {}, {}, FEES, 100.0, 0.25)[0]
        pm = next(l for l in arbs[0].legs if l.venue == "polymarket_us")
        self.assertEqual(pm.fee_rate, 0.0695)
        overridden = E.scan(http, ["lol"], {}, {}, dict(FEES, pm_override=True), 100.0, 0.25)[0]
        self.assertEqual(next(l for l in overridden[0].legs if l.venue == "polymarket_us").fee_rate, 0.05)

    def test_exact_times_a_day_apart_do_not_pair(self):
        k = listing("kalshi", ["MEIA NOITE", "Rush"], datetime(2026, 11, 5, 21, tzinfo=timezone.utc), "time")
        p = listing("polymarket_us", ["MEIA NOITE", "Rush"], datetime(2026, 11, 6, 22, tzinfo=timezone.utc), "time")
        self.assertEqual(E.match([k], [p])[0], [])


class LiveCapture(unittest.TestCase):
    """Real Kalshi + Polymarket US listings captured on 2026-11-05 (trimmed)."""
    path = os.path.join(HERE, "fixtures", "live_2026-11-05.json")

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest("live fixture not present")
        with open(self.path, encoding="utf-8") as f:
            self.rec = json.load(f)["responses"]

    def test_real_listings_match_correctly(self):
        disc = E.discover(E.Http(replay=self.rec), list(E.GAMES), {}, {}, 5)
        pairs, *_ = E.match([l for g in disc.kalshi.values() for l in g], disc.pmus)
        names = {frozenset(p.pmus.names.values()) for p in pairs}
        self.assertEqual(len(disc.pmus), 23)
        self.assertEqual(len(pairs), 10)
        self.assertIn(frozenset({"Gen.G Esports", "Invictus Gaming"}), names)
        self.assertIn(frozenset({"Grêmio Esports", "underw0rld"}), names)
        self.assertNotIn(frozenset({"MEIA NOITE", "Rush"}), names)       # listed 25 hours apart
        for p in pairs:
            self.assertEqual(p.kalshi.keys, p.pmus.keys)
            self.assertTrue(p.confirmed_date)
            self.assertLessEqual(abs((p.kalshi.start - p.pmus.start).total_seconds()), 12 * 3600)
            self.assertAlmostEqual(p.pmus.fee_rate, 0.0695)


class PaperTrading(unittest.TestCase):
    def first_arb(self, game="valorant"):
        http = replay_http()
        arbs = E.scan(http, [game], {}, {}, FEES, 100.0, 0.25)[0]
        return http, arbs[0]

    def test_unchanged_books_fill_completely(self):
        http, arb = self.first_arb()
        r = E.recheck(http, arb, FEES, 100.0)
        self.assertEqual((r["fillable_n"], r["profit_if_placed"]), (arb.legs[0].contracts, arb.profit))

    def test_thinner_book_fills_partly(self):
        http, arb = self.first_arb()
        url = f"{E.PMUS_API}/v1/markets/aec-val-lev-c9-2026-11-07/book"
        http.replay[url]["marketData"]["bids"] = [{"px": {"value": "0.50"}, "qty": "40"}]
        r = E.recheck(http, arb, FEES, 100.0)
        self.assertEqual(r["fillable_n"], 40)
        self.assertGreater(r["profit_if_placed"], 0)

    def test_price_moved_past_the_limit(self):
        http, arb = self.first_arb()
        url = f"{E.PMUS_API}/v1/markets/aec-val-lev-c9-2026-11-07/book"
        http.replay[url]["marketData"]["bids"] = [{"px": {"value": "0.44"}, "qty": "500"}]   # Leviatán now 56¢
        r = E.recheck(http, arb, FEES, 100.0)
        self.assertEqual((r["fillable_n"], r["profit_if_placed"], r["still_arb_pct"]), (0, None, None))

    def test_paper_loop_writes_scans_sightings_and_rechecks(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "sub", "paper.jsonl")
            args = arbscan.parse_args(["--paper", "--demo", "--watch", "1", "--recheck", "1",
                                       "--paper-log", log])
            args.max_scans = 2
            with mock.patch.object(E.time, "sleep"), redirect_stdout(io.StringIO()):
                self.assertEqual(E.run(args, FEES), 0)
            with open(log, encoding="utf-8") as f:
                kinds = [json.loads(line)["type"] for line in f]
        self.assertEqual((kinds.count("scan"), kinds.count("seen"), kinds.count("recheck")), (2, 4, 4))


def synthetic_log(path, hours, arb_every=None, profit=1.5, fill="full", error=None, pairs=3):
    """A fake paper log: one scan a minute, an arb lasting 3 scans every `arb_every` minutes."""
    t0 = datetime(2026, 11, 5, tzinfo=timezone.utc)
    with open(path, "w", encoding="utf-8") as f:
        for m in range(int(hours * 60)):
            t = (t0 + E.timedelta(minutes=m)).isoformat()
            scan = {"type": "scan", "t": t, "pairs": pairs, "kalshi_markets": 20, "pmus_markets": 15}
            if error:
                scan = {"type": "scan", "t": t, "error": error}
            f.write(json.dumps(scan) + "\n")
            if arb_every and m % arb_every < 3:
                op = f"op{m // arb_every}"
                f.write(json.dumps({"type": "seen", "t": t, "op": op, "game": "Valorant"}) + "\n")
                if m % arb_every == 0:
                    n = {"full": 100, "part": 50, "gone": 0}[fill]
                    f.write(json.dumps({"type": "recheck", "t": t, "op": op, "delay_s": 20, "planned_n": 100,
                                        "fillable_n": n, "profit_if_placed": profit if n else None}) + "\n")


class MakerSimulation(unittest.TestCase):
    def quotes(self):
        http = replay_http()
        _, _, disc, _ = E.scan(http, ["valorant"], {}, {}, dict(FEES, polymarket_us=0.0695), 100.0, 0.25)
        now = datetime(2026, 11, 5, 4, tzinfo=timezone.utc)
        return http, E.maker_quotes(disc.pairs, dict(FEES, polymarket_us=0.0695), 0.0175, 100.0, 0.25, now)

    def test_quote_is_one_tick_above_best_bid_and_locks_profit(self):
        _, qs = self.quotes()
        q = next(q for q in qs if q.team == "Cloud9")
        self.assertEqual((q.bid, q.improved, q.size, q.hedge_team), (0.43, True, 104, "Leviatán"))
        self.assertAlmostEqual(q.edge, 104 - (44.72 + 0.45) - 54.26, places=2)   # $4.57
        self.assertLessEqual(44.72 + 0.45 + q.hedge_cost, 100)

    def test_fill_rules(self):
        _, qs = self.quotes()
        q = next(q for q in qs if q.team == "Cloud9")
        t = lambda side, price, count, mins=1: {"taker_outcome_side": side, "yes_price_dollars": str(price),
                                                "count_fp": str(count),
                                                "created_time": (q.posted + E.timedelta(minutes=mins)).isoformat()}
        self.assertEqual(E.maker_fill([t("no", 0.43, 30)], q)[0], 30)          # seller at our price
        self.assertEqual(E.maker_fill([t("no", 0.40, 500)], q)[0], 104)        # capped at our size
        self.assertEqual(E.maker_fill([t("yes", 0.43, 30)], q)[0], 0)          # a buyer doesn't hit our bid
        self.assertEqual(E.maker_fill([t("no", 0.44, 30)], q)[0], 0)           # above our bid
        self.assertEqual(E.maker_fill([t("no", 0.43, 30, mins=-1)], q)[0], 0)  # before we posted
        joined = E.MakerQuote(**{**q.__dict__, "improved": False})
        self.assertEqual(E.maker_fill([t("no", 0.43, 30)], joined)[0], 0)      # joined: need a trade through
        self.assertEqual(E.maker_fill([t("no", 0.42, 30)], joined)[0], 30)

    def test_best_and_worst_case(self):
        http, qs = self.quotes()
        q = next(q for q in qs if q.team == "Cloud9")
        sell = [{"taker_outcome_side": "no", "yes_price_dollars": "0.43", "count_fp": "104",
                 "created_time": (q.posted + E.timedelta(seconds=5)).isoformat()}]
        later = q.posted + E.timedelta(seconds=40)
        same = E.settle_quote(http, q, sell, q.pair.books, later)
        self.assertEqual((same["filled"], same["best_case"], same["worst_case"], same["unhedged"]),
                         (104, 4.57, 4.57, 0))
        self.assertEqual(same["spotted_after_s"], 35.0)
        moved = dict(q.pair.books, pm_bids=[(0.44, 500.0)])          # Leviatán now costs 56¢
        worse = E.settle_quote(http, q, sell, moved, later)
        self.assertLess(worse["worst_case"], 0)
        self.assertEqual(worse["best_case"], 4.57)
        thin = dict(q.pair.books, pm_bids=[(0.50, 40.0)])             # only 40 available to hedge
        part = E.settle_quote(http, q, sell, thin, later)
        self.assertEqual(part["unhedged"], 64)

    def test_paper_loop_logs_maker_fills_and_reports_them(self):
        def fake_trades(http, ticker, since):
            return [{"taker_side": "no", "yes_price_dollars": "0.10", "count_fp": "1000",
                     "created_time": (since + E.timedelta(seconds=3)).isoformat()}]
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "p.jsonl")
            args = arbscan.parse_args(["--paper", "--demo", "--watch", "1", "--recheck", "1", "--paper-log", log])
            args.max_scans = 3
            with mock.patch.object(E, "kalshi_trades", fake_trades), mock.patch.object(E.time, "sleep"), \
                    redirect_stdout(io.StringIO()):
                E.run(args, dict(FEES, polymarket_us=0.0695))
            with open(log, encoding="utf-8") as f:
                kinds = [json.loads(line)["type"] for line in f]
            report = E.report(log)
        self.assertEqual(kinds.count("maker_post"), 6)      # 2 bids per scan x 3 scans
        self.assertEqual(kinds.count("maker_fill"), 6)      # every bid "filled", incl. the final settle
        self.assertIn("## Maker strategy (simulated)", report)
        self.assertIn("Filled (someone sold into the bid before the next scan): **6**", report)

    def test_trade_lookup_failures_are_logged_not_hidden(self):
        def broken(http, ticker, since):
            raise E.VenueError("https://api.elections.kalshi.com/trade-api/v2/markets/trades failed (HTTP 400)")
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "p.jsonl")
            args = arbscan.parse_args(["--paper", "--demo", "--watch", "1", "--recheck", "1", "--paper-log", log])
            args.max_scans = 2
            with mock.patch.object(E, "kalshi_trades", broken), mock.patch.object(E.time, "sleep"), \
                    redirect_stdout(io.StringIO()):
                E.run(args, FEES)
            with open(log, encoding="utf-8") as f:
                scans = [json.loads(l) for l in f if '"type": "scan"' in l]
        self.assertEqual(scans[1]["maker_errors"], scans[0]["maker_quotes"])   # every lookup failed
        self.assertGreater(scans[0]["maker_quotes"], 0)
        self.assertIn("HTTP 400", scans[1]["maker_error"])
        self.assertEqual(scans[1]["maker_fills"], 0)

    def test_maker_verdicts(self):
        def verdict(best, worst):
            rows = [{"type": "scan", "t": (datetime(2026, 11, 5, tzinfo=timezone.utc) + E.timedelta(minutes=m)).isoformat(),
                     "pairs": 10} for m in range(24 * 60)]
            rows.append({"type": "maker_post", "event": "A vs B", "edge": 3.0})
            rows.append({"type": "maker_fill", "best_case": best, "worst_case": worst, "spotted_after_s": 20})
            return "\n".join(E._maker_section(rows, 86400.0, True))
        self.assertIn("Promising even in the worst case", verdict(15, 12))
        self.assertIn("Depends on hedging speed", verdict(15, -4))
        self.assertIn("Small", verdict(3, 1))
        self.assertIn("Tiny", verdict(0.4, -1))

    def test_no_maker_flag(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "p.jsonl")
            args = arbscan.parse_args(["--paper", "--demo", "--no-maker", "--recheck", "1", "--paper-log", log])
            args.max_scans = 1
            with mock.patch.object(E.time, "sleep"), redirect_stdout(io.StringIO()):
                E.run(args, FEES)
            with open(log, encoding="utf-8") as f:
                self.assertNotIn("maker_post", f.read())


class TwoSpeeds(unittest.TestCase):
    def test_rechecks_at_bot_and_human_speed(self):
        self.assertEqual(E.recheck_delays("20, 2"), [2.0, 20.0])
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "paper.jsonl")
            args = arbscan.parse_args(["--paper", "--demo", "--watch", "1", "--recheck", "2,20", "--paper-log", log])
            args.max_scans = 1
            with mock.patch.object(E.time, "sleep") as slept, redirect_stdout(io.StringIO()):
                E.run(args, FEES)
            self.assertEqual([c.args[0] for c in slept.call_args_list][:2], [2.0, 18.0])
            with open(log, encoding="utf-8") as f:
                delays = [json.loads(line)["delay_s"] for line in f if '"recheck"' in line]
            self.assertEqual(sorted(delays), [2.0, 2.0, 20.0, 20.0])
            report = E.report(log)
        self.assertIn("After 2s (bot speed)", report)
        self.assertIn("After 20s (by hand)", report)


class Report(unittest.TestCase):
    def report(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "log.jsonl")
            synthetic_log(path, **kw)
            return E.report(path)

    def test_counts_each_appearance_once(self):
        out = self.report(hours=24, arb_every=60)
        self.assertIn("**24** appearances", out)
        self.assertIn("fully fillable **24**", out)
        self.assertIn("$36.00", out)                    # 24 x $1.50
        self.assertIn("Promising", out)

    def test_small_daily_profit_verdict(self):
        self.assertIn("Arbs exist but are tiny", self.report(hours=24, arb_every=600, profit=0.2))   # 3 x $0.20
        self.assertIn("Small but real", self.report(hours=24, arb_every=600, profit=0.5))          # 3 x $0.50

    def test_no_daily_figure_from_too_little_data(self):
        out = self.report(hours=2, arb_every=30)
        self.assertIn("too little data", out)
        self.assertIn("Too early to tell", out)

    def test_no_arbs(self):
        self.assertIn("No arbs in 24 hours", self.report(hours=24))

    def test_nothing_matched(self):
        self.assertIn("almost never found the same match", self.report(hours=24, pairs=0))

    def test_all_failed(self):
        out = self.report(hours=1, error="https://gateway.polymarket.us/v1/search failed (HTTP 403)")
        self.assertIn("Every scan failed", out)
        self.assertIn("HTTP 403", out)

    def test_gone_arbs_earn_nothing(self):
        out = self.report(hours=24, arb_every=60, fill="gone")
        self.assertIn("gone **24**", out)
        self.assertIn("**$0.00**", out)


class HttpLayer(unittest.TestCase):
    def test_retries_rate_limits_then_succeeds(self):
        calls = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout):
            calls.append(req.full_url)
            if len(calls) < 3:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, io.BytesIO(b""))
            return Resp(b'{"ok": true}')

        with mock.patch.object(E.urllib.request, "urlopen", fake), mock.patch.object(E.time, "sleep"):
            self.assertEqual(E.Http().get("https://gateway.polymarket.us/v1/markets"), {"ok": True})
        self.assertEqual(len(calls), 3)

    def test_gives_up_with_a_clear_error(self):
        def fake(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b""))

        with mock.patch.object(E.urllib.request, "urlopen", fake), mock.patch.object(E.time, "sleep"):
            with self.assertRaises(E.VenueError) as cm:
                E.Http().get("https://gateway.polymarket.us/v1/markets")
        self.assertIn("HTTP 403", str(cm.exception))


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch("sys.stderr", io.StringIO()):
            code = arbscan.main(list(argv))
        return code, buf.getvalue()

    def test_demo(self):
        code, out = self.run_cli("--esports", "--demo")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("ARB "), 2)

    def test_probe(self):
        code, out = self.run_cli("--esports", "--demo", "--probe")
        self.assertEqual(code, 0)
        self.assertIn("Matched 3 match(es)", out)
        self.assertIn("Spirit Academy vs FaZe Clan", out)

    def test_json_and_fee_override(self):
        code, out = self.run_cli("--esports", "--demo", "--json", "--fee", "kalshi=0.20")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["opportunities"], [], "a much higher Kalshi fee should kill both arbs")
        arbscan.VENUES["kalshi"].fee_rate = 0.07

    def test_unknown_game(self):
        self.assertEqual(self.run_cli("--esports", "--demo", "--games", "fortnite")[0], 2)


if __name__ == "__main__":
    unittest.main()
