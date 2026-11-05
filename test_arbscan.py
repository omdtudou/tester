"""Tests for arbscan. Run with:  python -m unittest test_arbscan  (or: python test_arbscan.py)"""
import io
import json
import os
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

import arbscan as A

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "sample_odds.json")
NOW = datetime(2026, 11, 5, 2, 40, 0, tzinfo=timezone.utc)


def cfg(**kw):
    base = dict(bet_on=["kalshi", "polymarket_us"], reference=["pinnacle"],
                markets=("h2h", "spreads", "totals"), budget=100.0)
    base.update(kw)
    return A.Config(**base)


def sample_events(*ids):
    events, _ = A.load_file(SAMPLE)
    return [e for e in events if not ids or e["id"] in ids]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(eid, sport, home, away, books, live=False):
    start = NOW - timedelta(minutes=30) if live else NOW + timedelta(hours=5)
    return {"id": eid, "sport_key": sport, "sport_title": sport, "commence_time": iso(start),
            "home_team": home, "away_team": away,
            "bookmakers": [{"key": k, "title": k, "markets": [dict(m, last_update=iso(NOW - timedelta(seconds=5)))
                                                              for m in ms]} for k, ms in books.items()]}


class FeeMath(unittest.TestCase):
    def test_kalshi_fee_matches_published_example(self):
        # Kalshi's fee schedule example: 100 contracts at 55c -> $1.74
        self.assertEqual(A.exchange_fee(A.VENUES["kalshi"], 100, 0.55), 1.74)

    def test_exact_cent_fee_is_not_bumped_by_float_noise(self):
        self.assertEqual(A.exchange_fee(A.VENUES["kalshi"], 100, 0.50), 1.75)

    def test_polymarket_sports_fee(self):
        self.assertEqual(A.exchange_fee(A.VENUES["polymarket"], 100, 0.50), 1.25)
        self.assertEqual(A.exchange_fee(A.VENUES["polymarket_us"], 100, 0.24), 0.92)  # 0.912 rounded up

    def test_price_recovered_from_rounded_odds(self):
        self.assertEqual(A.price_from_odds(1.89, 0.01), 0.53)   # 1/1.89 = 0.5291
        self.assertEqual(A.price_from_odds(1.92, 0.01), 0.52)   # 1/1.92 = 0.5208
        self.assertEqual(A.price_from_odds(2.27, 0.01), 0.44)

    def test_genuine_subtick_price_rounds_up_never_down(self):
        self.assertEqual(A.price_from_odds(1 / 0.535, 0.01), 0.54)


class LinePairing(unittest.TestCase):
    def test_spreads_with_opposite_signs_never_pair(self):
        opps, _ = A.scan(sample_events("demo-nba-2"), cfg(), NOW)
        self.assertEqual(opps, [], "Heat -1.5 must not hedge Knicks -1.5")

    def test_spreads_on_the_same_line_do_pair(self):
        e = ev("s", "basketball_nba", "Heat", "Knicks", {
            "kalshi": [{"key": "spreads", "outcomes": [
                {"name": "Heat", "price": 1 / 0.45, "point": -1.5}, {"name": "Knicks", "price": 1 / 0.57, "point": 1.5}]}],
            "polymarket_us": [{"key": "spreads", "outcomes": [
                {"name": "Heat", "price": 1 / 0.58, "point": -1.5}, {"name": "Knicks", "price": 1 / 0.50, "point": 1.5}]}],
        })
        opps, _ = A.scan([e], cfg(reference=[]), NOW)
        self.assertEqual(len(opps), 1)
        self.assertEqual({l.label for l in opps[0].legs}, {"Heat -1.5", "Knicks +1.5"})

    def test_totals_on_different_points_never_pair(self):
        e = ev("t", "basketball_nba", "Suns", "Warriors", {
            "kalshi": [{"key": "totals", "outcomes": [
                {"name": "Over", "price": 1 / 0.40, "point": 228.5}, {"name": "Under", "price": 1 / 0.62, "point": 228.5}]}],
            "polymarket_us": [{"key": "totals", "outcomes": [
                {"name": "Over", "price": 1 / 0.62, "point": 231.5}, {"name": "Under", "price": 1 / 0.40, "point": 231.5}]}],
        })
        opps, _ = A.scan([e], cfg(reference=[]), NOW)
        self.assertEqual(opps, [])

    def test_two_way_soccer_moneyline_is_skipped(self):
        e = ev("x", "soccer_epl", "Arsenal", "Chelsea", {
            "kalshi": [{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 2.5}, {"name": "Chelsea", "price": 4.0}]}],
            "polymarket_us": [{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 2.6}, {"name": "Chelsea", "price": 4.2}]}],
        })
        self.assertEqual(A.build_groups([e], ("h2h",)), [])

    def test_three_way_needs_every_outcome_covered(self):
        e = ev("y", "soccer_epl", "Arsenal", "Chelsea", {
            "kalshi": [{"key": "h2h", "outcomes": [
                {"name": "Arsenal", "price": 3.0}, {"name": "Draw", "price": 3.0}, {"name": "Chelsea", "price": 3.0}]}],
        })
        opps, _ = A.scan([e], cfg(reference=[], bet_on=["polymarket_us"]), NOW)
        self.assertEqual(opps, [])


class Arbs(unittest.TestCase):
    def test_every_arb_fits_budget_and_pays_more_than_it_costs(self):
        for budget in (25, 100, 1000, 5000):
            opps, _ = A.scan(sample_events(), cfg(budget=budget), NOW)
            arbs = [o for o in opps if o.kind == "arb"]
            self.assertEqual(len(arbs), 3)
            for o in arbs:
                outlay = round(sum(l.cost for l in o.legs), 2)
                self.assertLessEqual(outlay, budget)
                self.assertEqual(outlay, o.outlay)
                for l in o.legs:
                    self.assertGreater(l.payout, outlay, f"{l.label} must return more than the outlay")
                self.assertAlmostEqual(min(l.payout for l in o.legs) - outlay, o.profit, places=2)

    def test_live_moneyline_slip(self):
        opps, _ = A.scan(sample_events("demo-nba-1"), cfg(reference=[]), NOW)
        (o,) = opps
        k, p = sorted(o.legs, key=lambda l: l.venue)
        self.assertEqual((k.venue, k.label, k.price, k.contracts, k.fee), ("kalshi", "Boston Celtics", 0.52, 101, 1.77))
        self.assertEqual((p.venue, p.label, p.price, p.contracts, p.fee),
                         ("polymarket_us", "Los Angeles Lakers", 0.44, 101, 1.25))
        self.assertEqual((o.outlay, o.profit), (99.98, 1.02))

    def test_fees_wipe_out_one_cent_edge(self):
        opps, stats = A.scan(sample_events("demo-nhl-1"), cfg(reference=[]), NOW)
        self.assertEqual(opps, [])
        self.assertEqual(stats.gross_only, 1)

    def test_stale_quote_is_ignored(self):
        events = sample_events("demo-nba-4")
        opps, stats = A.scan(events, cfg(reference=[]), NOW)
        self.assertEqual(opps, [])
        self.assertEqual(stats.stale_quotes, 2)
        opps, _ = A.scan(events, cfg(reference=[], max_age_live=600), NOW)
        self.assertEqual(len(opps), 1, "with a looser age limit the stale quote would have been used")

    def test_reference_only_venue_is_never_a_leg(self):
        opps, _ = A.scan(sample_events("demo-ncaaf-1"), cfg(), NOW)
        self.assertTrue(all(l.venue != "pinnacle" for o in opps for l in o.legs))
        self.assertFalse(any(o.kind == "arb" for o in opps))

    def test_pinnacle_leg_when_allowed(self):
        opps, _ = A.scan(sample_events("demo-ncaaf-1"), cfg(bet_on=["kalshi", "polymarket_us", "pinnacle"]), NOW)
        (arb,) = [o for o in opps if o.kind == "arb"]
        pin = next(l for l in arb.legs if l.venue == "pinnacle")
        self.assertEqual((pin.stake, pin.payout), (36.73, 101.0))
        self.assertEqual(arb.profit, 1.45)

    def test_nfl_moneyline_gets_tie_warning(self):
        opps, _ = A.scan(sample_events("demo-nfl-1"), cfg(reference=[]), NOW)
        self.assertTrue(any("tied" in w for w in opps[0].warnings))


class ValueBets(unittest.TestCase):
    def test_value_vs_pinnacle_no_vig(self):
        opps, _ = A.scan(sample_events("demo-epl-1"), cfg(), NOW)
        (o,) = opps
        self.assertEqual(o.kind, "value")
        self.assertEqual((o.legs[0].venue, o.legs[0].label), ("polymarket_us", "Chelsea"))
        implied = [1 / 2.10, 1 / 3.50, 1 / 3.60]
        self.assertAlmostEqual(o.fair, implied[2] / sum(implied), places=6)
        self.assertGreaterEqual(o.pct, 2.0)
        self.assertLessEqual(o.outlay, 25.0)

    def test_no_value_bets_without_reference(self):
        opps, _ = A.scan(sample_events("demo-epl-1"), cfg(reference=[]), NOW)
        self.assertEqual(opps, [])


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(json.dumps(body).encode())
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class OddsApi(unittest.TestCase):
    def test_request_shape_and_quota_headers(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["url"] = req.full_url
            return FakeResponse([], {"x-requests-remaining": "499", "x-requests-used": "1", "x-requests-last": "1"})

        with mock.patch.object(A.urllib.request, "urlopen", fake_urlopen):
            events, quota = A.fetch_odds("KEY", ["upcoming"], ["kalshi", "polymarket_us", "pinnacle"], ("h2h",))
        url = urllib.parse.urlsplit(seen["url"])
        q = dict(urllib.parse.parse_qsl(url.query))
        self.assertEqual(url.netloc, "api.the-odds-api.com")
        self.assertEqual(url.path, "/v4/sports/upcoming/odds/")
        self.assertEqual(q["bookmakers"], "kalshi,polymarket_us,pinnacle")
        self.assertEqual((q["markets"], q["oddsFormat"], q["apiKey"]), ("h2h", "decimal", "KEY"))
        self.assertEqual(quota["remaining"], "499")

    def test_http_error_is_explained(self):
        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                         io.BytesIO(b'{"message": "API key is not valid"}'))

        with mock.patch.object(A.urllib.request, "urlopen", fake_urlopen):
            with self.assertRaises(A.ApiError) as cm:
                A.fetch_odds("BAD", ["upcoming"], ["kalshi"], ("h2h",))
        self.assertIn("401", str(cm.exception))
        self.assertIn("API key is not valid", str(cm.exception))

    def test_credit_estimate(self):
        self.assertEqual(A.credits_per_scan(2, 1, 3), 2)
        self.assertEqual(A.credits_per_scan(1, 3, 11), 6)


class Cli(unittest.TestCase):
    def test_demo_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = A.main(["--demo"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertEqual(out.count("ARB "), 3)
        self.assertEqual(out.count("VALUE "), 2)

    def test_json_output_is_valid(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            A.main(["--demo", "--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data["opportunities"]), 5)

    def test_csv_log(self):
        path = os.path.join(HERE, "_test_log.csv")
        try:
            with redirect_stdout(io.StringIO()):
                A.main(["--demo", "--log", path])
            with open(path, encoding="utf-8") as f:
                rows = f.read().strip().splitlines()
            self.assertEqual(len(rows), 6)   # header + 5
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
