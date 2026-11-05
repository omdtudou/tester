#!/usr/bin/env python3
"""
arbscan.py - fee-aware arbitrage and value-bet scanner for Kalshi, Polymarket and Pinnacle.

How it works
  1. Pulls live and upcoming game odds for the venues you choose from The Odds API
     (https://the-odds-api.com). That one feed carries Kalshi, Polymarket,
     Polymarket US and Pinnacle, and lines up the same game across all of them.
  2. Turns every quote into "cost per $1 of payout", including each exchange's taker
     fee, and drops quotes too old to trust.
  3. Reports two kinds of opportunity, each with an exact bet slip:
       ARB   - back every outcome on a venue you can trade on; you are paid the same
               whatever happens, and that payout is more than you put in after fees.
       VALUE - one exchange price that beats Pinnacle's no-vig fair price. Positive
               expected value, NOT guaranteed.

It never places orders. Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

API_HOST = "https://api.the-odds-api.com"
VERSION = "1.0"

# Exchange prices outside this band have sub-cent ticks and very thin books.
MIN_PRICE, MAX_PRICE = 0.02, 0.98


# --------------------------------------------------------------------------- venues

@dataclass
class Venue:
    key: str               # The Odds API bookmaker key
    name: str
    kind: str              # "exchange": buy contracts that pay $1; "book": stake at decimal odds
    fee_rate: float = 0.0  # taker fee = fee_rate * contracts * price * (1 - price)
    fee_rounding: str = "cent_up"   # "cent_up" (per order, up to the cent) or "5dp"
    tick: float = 0.01     # price increment, used to recover the contract price from decimal odds
    unit: str = "contracts"


# Fee rates are taker rates for sports markets as published in 2026. They change;
# override with --fee VENUE=RATE if a venue updates its schedule.
VENUES: Dict[str, Venue] = {
    "kalshi": Venue("kalshi", "Kalshi", "exchange", 0.07, "cent_up", 0.01, "contracts"),
    "polymarket_us": Venue("polymarket_us", "Polymarket US", "exchange", 0.0695, "cent_up", 0.01, "shares"),
    "polymarket": Venue("polymarket", "Polymarket", "exchange", 0.05, "5dp", 0.01, "shares"),
    "pinnacle": Venue("pinnacle", "Pinnacle", "book"),
}


def get_venue(key: str) -> Venue:
    """Known venue, or any other Odds API bookmaker treated as a fee-free sportsbook."""
    if key not in VENUES:
        VENUES[key] = Venue(key, key.replace("_", " ").title(), "book")
    return VENUES[key]


# --------------------------------------------------------------------------- money math

def ceil_cent(x: float) -> float:
    return math.ceil(round(x * 100, 6)) / 100


def floor_cent(x: float) -> float:
    return math.floor(round(x * 100, 6)) / 100


def exchange_fee(venue: Venue, contracts: int, price: float) -> float:
    raw = venue.fee_rate * contracts * price * (1 - price)
    if raw <= 0:
        return 0.0
    if venue.fee_rounding == "5dp":
        return round(raw, 5)
    return ceil_cent(raw)


def price_from_odds(odds: float, tick: float) -> float:
    """Recover an exchange's contract price from the decimal odds in the feed.

    The feed rounds decimal odds, so 1/odds lands near, not on, the real price.
    Small misses (under a quarter tick) snap to the nearest tick. Anything else
    rounds UP, so the scanner never assumes a cheaper price than the real one.
    """
    k = (1.0 / odds) / tick
    k = round(k) if abs(k - round(k)) < 0.25 else math.ceil(k)
    return round(k * tick, 6)


def net_unit_cost(venue: Venue, price: Optional[float], odds: float) -> float:
    """What it costs, fees included, to collect $1 if this outcome wins."""
    if venue.kind == "exchange":
        return price + venue.fee_rate * price * (1 - price)
    return 1.0 / odds


def gross_unit_cost(venue: Venue, price: Optional[float], odds: float) -> float:
    return price if venue.kind == "exchange" else 1.0 / odds


def american(odds: float) -> str:
    if odds >= 2:
        return f"+{round((odds - 1) * 100)}"
    return f"{round(-100 / (odds - 1))}"


def money(x: float) -> str:
    return f"${x:,.2f}"


def cents(p: float) -> str:
    c = p * 100
    return f"{c:.0f}¢" if abs(c - round(c)) < 1e-6 else f"{c:.1f}¢"


def fmt_point(x: float) -> str:
    return f"{x:+g}"


def fmt_age(seconds: Optional[float]) -> str:
    if seconds is None:
        return "age ?"
    seconds = max(seconds, 0)
    return f"{seconds:.0f}s old" if seconds < 90 else f"{seconds / 60:.0f}m old"


def parse_time(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError, OSError):
        return None


# --------------------------------------------------------------------------- data model

@dataclass
class Quote:
    venue: str
    label: str                 # what you are backing, e.g. "Boston Celtics -3.5"
    odds: float                # decimal odds from the feed
    price: Optional[float]     # contract price, exchanges only
    updated: Optional[datetime]
    link: Optional[str] = None

    def age(self, now: datetime) -> Optional[float]:
        return None if self.updated is None else (now - self.updated).total_seconds()

    def net(self) -> float:
        return net_unit_cost(get_venue(self.venue), self.price, self.odds)

    def gross(self) -> float:
        return gross_unit_cost(get_venue(self.venue), self.price, self.odds)


@dataclass
class MarketGroup:
    """One betting question on one game, e.g. 'moneyline' or 'total 221.5', across venues."""
    event_id: str
    sport_key: str
    sport_title: str
    home: str
    away: str
    commence: Optional[datetime]
    market: str                        # h2h | spreads | totals
    line: str                          # human description
    outcomes: Tuple[str, ...]          # every label that must be covered for a hedge
    quotes: Dict[str, List[Quote]] = field(default_factory=dict)

    def live(self, now: datetime) -> bool:
        return self.commence is not None and self.commence <= now

    def title(self) -> str:
        if self.sport_key.startswith("soccer"):
            return f"{self.home} vs {self.away}"
        return f"{self.away} @ {self.home}"


@dataclass
class Leg:
    venue: str
    label: str
    odds: float
    price: Optional[float]
    contracts: Optional[int]
    stake: float
    fee: float
    payout: float
    age: Optional[float]
    link: Optional[str] = None

    @property
    def cost(self) -> float:
        return round(self.stake + self.fee, 2)


@dataclass
class Opportunity:
    kind: str                     # "arb" | "value"
    group: MarketGroup
    legs: List[Leg]
    pct: float                    # guaranteed ROI % (arb) or expected value % (value)
    outlay: float
    profit: float                 # guaranteed (arb) or expected (value)
    fair: Optional[float] = None  # value: reference no-vig probability
    reference: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def key(self) -> tuple:
        g = self.group
        return (self.kind, g.event_id, g.market, g.line,
                tuple((l.venue, l.label, l.price if l.price is not None else l.odds) for l in self.legs))

    def to_dict(self, now: datetime) -> dict:
        g = self.group
        return {
            "kind": self.kind,
            "sport": g.sport_title,
            "event": g.title(),
            "live": g.live(now),
            "commence_time": g.commence.isoformat() if g.commence else None,
            "market": g.market,
            "line": g.line,
            "pct": round(self.pct, 3),
            "outlay": self.outlay,
            "profit": self.profit,
            "fair_probability": round(self.fair, 4) if self.fair is not None else None,
            "reference": self.reference,
            "legs": [{
                "venue": l.venue, "outcome": l.label, "decimal_odds": l.odds,
                "limit_price": l.price, "contracts": l.contracts, "stake": l.stake,
                "fee": l.fee, "payout": l.payout,
                "quote_age_s": round(l.age, 1) if l.age is not None else None,
                "link": l.link,
            } for l in self.legs],
            "warnings": self.warnings,
        }


@dataclass
class Config:
    bet_on: List[str]
    reference: List[str]
    markets: Tuple[str, ...] = ("h2h",)
    budget: float = 100.0
    min_profit_pct: float = 0.25
    min_ev_pct: float = 2.0
    value_stake: float = 25.0
    max_age_live: float = 60.0
    max_age_pregame: float = 600.0
    suspicious_pct: float = 8.0


@dataclass
class Stats:
    events: int = 0
    markets: int = 0
    stale_quotes: int = 0
    gross_only: int = 0   # looked like an arb before fees/rounding, didn't survive them


# --------------------------------------------------------------------------- normalising the feed

def _normalise_market(ev: dict, market_key: str, outcomes: list):
    """Return (group_key, line_description, [(label, outcome), ...]) or None to skip.

    The grouping key is what makes a hedge valid: two quotes only end up in the same
    group if they are opposite sides of the *same* line.
    """
    names = [o.get("name") for o in outcomes]
    if len(outcomes) < 2 or None in names or len(set(names)) != len(names):
        return None
    sport = ev.get("sport_key", "")

    if market_key == "h2h":
        # A soccer moneyline without a Draw outcome is not the same bet as a 3-way
        # one; mixing them leaves you losing every leg on a draw.
        if sport.startswith("soccer") and "Draw" not in names:
            return None
        sig = tuple(sorted(names))
        line = "Moneyline (3-way)" if "Draw" in names else "Moneyline"
        return ("h2h", sig), line, [(n, o) for n, o in zip(names, outcomes)]

    if market_key == "totals":
        if len(outcomes) != 2 or set(names) != {"Over", "Under"}:
            return None
        points = {o.get("point") for o in outcomes}
        if len(points) != 1 or None in points:
            return None
        pt = points.pop()
        return ("totals", float(pt)), f"Total {pt:g}", [(f"{o['name']} {pt:g}", o) for o in outcomes]

    if market_key == "spreads":
        home, away = ev.get("home_team"), ev.get("away_team")
        by_name = {o.get("name"): o for o in outcomes}
        if len(outcomes) != 2 or home not in by_name or away not in by_name:
            return None
        h, a = by_name[home].get("point"), by_name[away].get("point")
        if h is None or a is None or abs(float(h) + float(a)) > 1e-9:
            return None
        h, a = float(h), float(a)
        # Keyed on the home team's signed line, so "-1.5" and "+1.5" never mix.
        return (("spreads", h), f"Spread {home} {fmt_point(h)}",
                [(f"{home} {fmt_point(h)}", by_name[home]), (f"{away} {fmt_point(a)}", by_name[away])])

    return None


def build_groups(events: list, markets: Tuple[str, ...]) -> List[MarketGroup]:
    groups: Dict[tuple, MarketGroup] = {}
    for ev in events:
        ev_id = ev.get("id")
        if not ev_id:
            continue
        for bm in ev.get("bookmakers") or []:
            vkey = bm.get("key")
            if not vkey:
                continue
            venue = get_venue(vkey)
            for mk in bm.get("markets") or []:
                mkey = mk.get("key")
                if mkey not in markets:
                    continue
                parsed = _normalise_market(ev, mkey, mk.get("outcomes") or [])
                if not parsed:
                    continue
                gkey, line, labelled = parsed
                full_key = (ev_id,) + gkey
                group = groups.get(full_key)
                if group is None:
                    group = MarketGroup(
                        event_id=ev_id,
                        sport_key=ev.get("sport_key", ""),
                        sport_title=ev.get("sport_title") or ev.get("sport_key", ""),
                        home=ev.get("home_team", ""),
                        away=ev.get("away_team", ""),
                        commence=parse_time(ev.get("commence_time")),
                        market=mkey,
                        line=line,
                        outcomes=tuple(label for label, _ in labelled),
                    )
                    groups[full_key] = group
                updated = parse_time(mk.get("last_update") or bm.get("last_update"))
                for label, out in labelled:
                    odds = out.get("price")
                    if not isinstance(odds, (int, float)) or odds <= 1.0:
                        continue
                    price = None
                    if venue.kind == "exchange":
                        price = price_from_odds(float(odds), venue.tick)
                        if not (MIN_PRICE <= price <= MAX_PRICE):
                            continue
                    link = out.get("link") or mk.get("link") or bm.get("link")
                    group.quotes.setdefault(label, []).append(
                        Quote(vkey, label, float(odds), price, updated, link))
    return list(groups.values())


# --------------------------------------------------------------------------- finding opportunities

def is_fresh(q: Quote, g: MarketGroup, cfg: Config, now: datetime) -> bool:
    age = q.age(now)
    if age is None:
        return True
    return age <= (cfg.max_age_live if g.live(now) else cfg.max_age_pregame)


def make_leg(q: Quote, payout_target: int, now: datetime) -> Leg:
    """Size one leg so it returns at least `payout_target` dollars if it wins."""
    v = get_venue(q.venue)
    if v.kind == "exchange":
        n = payout_target
        return Leg(q.venue, q.label, q.odds, q.price, n, ceil_cent(n * q.price),
                   exchange_fee(v, n, q.price), float(n), q.age(now), q.link)
    stake = ceil_cent(payout_target / q.odds)
    return Leg(q.venue, q.label, q.odds, None, None, stake, 0.0,
               floor_cent(stake * q.odds), q.age(now), q.link)


def size_to_budget(quotes: List[Quote], budget: float, now: datetime) -> Optional[List[Leg]]:
    """Largest equal payout (whole contracts) whose total outlay fits the budget."""
    unit = sum(q.net() for q in quotes)
    n = int(budget / unit) + 1
    while n >= 1:
        legs = [make_leg(q, n, now) for q in quotes]
        if sum(l.cost for l in legs) <= budget + 1e-9:
            return legs
        n -= 1
    return None


def rule_warnings(g: MarketGroup, legs: List[Leg]) -> List[str]:
    w = []
    if g.sport_key == "americanfootball_nfl" and g.market == "h2h":
        w.append("NFL games can end tied. Check how each venue settles a tie "
                 "(refund vs. NO) before betting.")
    if g.sport_key.startswith("soccer"):
        w.append("Confirm every venue settles on 90 minutes plus stoppage time, "
                 "not extra time or penalties.")
    if len({l.venue for l in legs}) > 1 and g.market != "h2h":
        w.append("Make sure the line is identical on both venues when you place the bets.")
    return w


def find_arb(g: MarketGroup, cfg: Config, now: datetime, stats: Stats) -> Optional[Opportunity]:
    chosen: List[Quote] = []
    gross_total = 0.0
    for label in g.outcomes:
        cands = [q for q in g.quotes.get(label, [])
                 if q.venue in cfg.bet_on and is_fresh(q, g, cfg, now)]
        if not cands:
            return None
        chosen.append(min(cands, key=lambda q: q.net()))
        gross_total += min(q.gross() for q in cands)

    def gross_only() -> None:
        if gross_total < 1.0:
            stats.gross_only += 1

    if sum(q.net() for q in chosen) >= 1.0:
        gross_only()
        return None
    legs = size_to_budget(chosen, cfg.budget, now)
    if not legs:
        gross_only()
        return None
    outlay = round(sum(l.cost for l in legs), 2)
    profit = round(min(l.payout for l in legs) - outlay, 2)
    pct = profit / outlay * 100 if outlay else 0.0
    if pct < cfg.min_profit_pct:
        gross_only()
        return None
    warnings = rule_warnings(g, legs)
    if pct > cfg.suspicious_pct:
        warnings.insert(0, "Unusually large edge. It's usually a stale quote or two "
                           "different markets, so check both prices by hand first.")
    return Opportunity("arb", g, legs, pct, outlay, profit, warnings=warnings)


def size_single(q: Quote, stake: float, now: datetime) -> Optional[Leg]:
    n = int(stake / q.net()) + 1
    while n >= 1:
        leg = make_leg(q, n, now)
        if leg.cost <= stake + 1e-9:
            return leg
        n -= 1
    return None


def find_value(g: MarketGroup, cfg: Config, now: datetime) -> List[Opportunity]:
    ref_key, ref_quotes = None, {}
    for rk in cfg.reference:
        quotes = {}
        for label in g.outcomes:
            c = [q for q in g.quotes.get(label, []) if q.venue == rk and is_fresh(q, g, cfg, now)]
            if not c:
                break
            quotes[label] = c[0]
        else:
            ref_key, ref_quotes = rk, quotes
            break
    if ref_key is None:
        return []

    implied = {l: 1.0 / q.odds for l, q in ref_quotes.items()}
    overround = sum(implied.values())
    if overround < 1.0:      # reference book itself looks broken; don't trust it
        return []
    fair = {l: p / overround for l, p in implied.items()}

    out = []
    for label in g.outcomes:
        for q in g.quotes.get(label, []):
            if q.venue == ref_key or q.venue not in cfg.bet_on or not is_fresh(q, g, cfg, now):
                continue
            ev = fair[label] / q.net() - 1
            if ev * 100 < cfg.min_ev_pct:
                continue
            leg = size_single(q, cfg.value_stake, now)
            if leg is None:
                continue
            expected = round(fair[label] * leg.payout - leg.cost, 2)
            warnings = rule_warnings(g, [leg])
            if ev * 100 > cfg.suspicious_pct:
                warnings.insert(0, "Unusually large edge. The reference line may be stale; "
                                   "check it before betting.")
            out.append(Opportunity("value", g, [leg], ev * 100, leg.cost, expected,
                                   fair=fair[label], reference=ref_key, warnings=warnings))
    return out


def scan(events: list, cfg: Config, now: datetime) -> Tuple[List[Opportunity], Stats]:
    groups = build_groups(events, cfg.markets)
    stats = Stats(events=len(events), markets=len(groups))
    seen = set()
    for g in groups:
        for qs in g.quotes.values():
            for q in qs:
                if q.venue in cfg.bet_on and not is_fresh(q, g, cfg, now) and id(q) not in seen:
                    seen.add(id(q))
                    stats.stale_quotes += 1
    opps: List[Opportunity] = []
    for g in groups:
        arb = find_arb(g, cfg, now, stats)
        if arb:
            opps.append(arb)
        opps.extend(find_value(g, cfg, now))
    opps.sort(key=lambda o: (o.kind != "arb", -o.pct))
    return opps, stats


# --------------------------------------------------------------------------- output

def render(o: Opportunity, now: datetime) -> str:
    g = o.group
    if o.kind == "arb":
        head = f"ARB  +{o.pct:.2f}% guaranteed after fees"
    else:
        head = f"VALUE  +{o.pct:.1f}% expected vs {get_venue(o.reference).name} no-vig line (not guaranteed)"
    when = "LIVE" if g.live(now) else (
        "starts " + g.commence.astimezone().strftime("%a %b %d %I:%M %p") if g.commence else "start time ?")
    lines = ["=" * 78, head, f"{g.sport_title} | {g.title()} | {when} | {g.line}"]
    for i, l in enumerate(o.legs, 1):
        v = get_venue(l.venue)
        if l.contracts is not None:
            action = f"BUY {l.contracts} {v.unit} at <= {cents(l.price)}"
            cost = f"{money(l.stake)} + {money(l.fee)} fee"
        else:
            action = f"BET {money(l.stake)} at {l.odds:.3g} ({american(l.odds)})"
            cost = money(l.stake)
        lines.append(f"  {i}. {v.name:<14} {l.label:<30} {action:<32} {cost}  [{fmt_age(l.age)}]")
    if o.kind == "arb":
        lines.append(f"  Outlay {money(o.outlay)} -> pays at least {money(min(l.payout for l in o.legs))} "
                     f"whichever way it goes -> profit {money(o.profit)}")
    else:
        leg = o.legs[0]
        lines.append(f"  Fair value {cents(o.fair)} vs your all-in cost {cents(leg.cost / leg.payout)} "
                     f"| stake {money(o.outlay)} | expected profit {money(o.profit)}")
    for w in o.warnings:
        lines.append(f"  ! {w}")
    for l in o.legs:
        if l.link:
            lines.append(f"  {get_venue(l.venue).name}: {l.link}")
    return "\n".join(lines)


FOOTER = ("Before betting: use LIMIT orders at the prices shown (never market orders), "
          "place the leg with less depth first,\nand only place the second leg once the first "
          "has filled. Check that both markets settle the same way\n(overtime, postponement, ties).")


def summary_line(stats: Stats, opps: List[Opportunity], quota: dict, source: str) -> str:
    arbs = sum(o.kind == "arb" for o in opps)
    values = len(opps) - arbs
    parts = [f"{stats.events} games", f"{stats.markets} markets", f"{arbs} arb", f"{values} value"]
    if stats.gross_only:
        parts.append(f"{stats.gross_only} gross-only (fees ate them)")
    if stats.stale_quotes:
        parts.append(f"{stats.stale_quotes} stale quotes ignored")
    if quota.get("remaining") is not None:
        parts.append(f"credits left {quota['remaining']} (last call cost {quota.get('last', '?')})")
    return f"[{datetime.now().strftime('%H:%M:%S')}] {source}: " + ", ".join(parts)


def append_log(path: str, opps: List[Opportunity], now: datetime) -> None:
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["seen_at", "kind", "sport", "event", "line", "pct", "outlay", "profit", "legs"])
        for o in opps:
            legs = " | ".join(
                f"{get_venue(l.venue).name}: {l.label} "
                + (f"{l.contracts}@{cents(l.price)}" if l.contracts is not None else f"{money(l.stake)}@{l.odds}")
                for l in o.legs)
            w.writerow([now.isoformat(), o.kind, o.group.sport_title, o.group.title(),
                        o.group.line, f"{o.pct:.3f}", o.outlay, o.profit, legs])


# --------------------------------------------------------------------------- The Odds API

class ApiError(RuntimeError):
    pass


def api_get(path: str, params: dict, timeout: float = 20.0) -> Tuple[object, dict]:
    url = f"{API_HOST}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"arbscan/{VERSION}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            h = resp.headers
            quota = {"remaining": h.get("x-requests-remaining"), "used": h.get("x-requests-used"),
                     "last": h.get("x-requests-last")}
            return body, quota
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("message", "")
        except Exception:
            msg = ""
        hints = {401: "Check your API key, or your monthly credits may be used up.",
                 422: "A parameter was rejected; check --sports and --markets.",
                 429: "Too many requests; slow down with a longer --watch interval."}
        raise ApiError(f"The Odds API returned HTTP {e.code}. {msg} {hints.get(e.code, '')}".strip()) from None
    except urllib.error.URLError as e:
        raise ApiError(f"Couldn't reach The Odds API: {e.reason}") from None


def fetch_odds(api_key: str, sports: List[str], books: List[str], markets: Tuple[str, ...]) -> Tuple[list, dict]:
    events, quota = [], {}
    for sport in sports:
        data, quota = api_get(f"/v4/sports/{sport}/odds/", {
            "apiKey": api_key,
            "bookmakers": ",".join(books),
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
            "dateFormat": "iso",
            "includeLinks": "true",
        })
        if isinstance(data, list):
            events.extend(data)
    return events, quota


def credits_per_scan(n_sports: int, n_markets: int, n_books: int) -> int:
    # The Odds API: cost = markets x regions, and every 10 bookmakers count as one region.
    return n_sports * n_markets * max(1, math.ceil(n_books / 10))


def load_file(path: str) -> Tuple[list, Optional[datetime]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("events", []), parse_time(data.get("now") or data.get("fetched_at"))
    return data, None


# --------------------------------------------------------------------------- CLI

def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="arbscan",
        description="Find fee-aware arbitrage and value bets across Kalshi, Polymarket and Pinnacle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  python arbscan.py --demo\n"
               "  python arbscan.py --sports basketball_nba,icehockey_nhl --budget 250\n"
               "  python arbscan.py --watch 120 --beep --log arbs.csv\n"
               "  python arbscan.py --bet-on kalshi,polymarket_us,pinnacle   (if you can bet at Pinnacle)\n"
               "  python arbscan.py --esports --games valorant,cs2 --budget 200\n"
               "  python arbscan.py --esports --probe          (check what each venue lists)")
    p.add_argument("--api-key", default=os.environ.get("ODDS_API_KEY"),
                   help="The Odds API key (or set ODDS_API_KEY)")
    p.add_argument("--sports", default="upcoming",
                   help="comma-separated sport keys, or 'upcoming' for every live game plus the "
                        "next 8 starting (default: upcoming)")
    p.add_argument("--markets", default=None,
                   help="h2h, spreads, totals, comma-separated (default: h2h live, all in --demo)")
    p.add_argument("--bet-on", default="kalshi,polymarket_us",
                   help="venues you can actually trade on (default: kalshi,polymarket_us)")
    p.add_argument("--reference", default="pinnacle",
                   help="sharp venue(s) used for fair prices (default: pinnacle)")
    p.add_argument("--budget", type=float, default=100.0, help="max total outlay per arb, $ (default 100)")
    p.add_argument("--min-profit", type=float, default=0.25,
                   help="min guaranteed return after fees, %% (default 0.25)")
    p.add_argument("--min-ev", type=float, default=2.0, help="min expected value for VALUE bets, %% (default 2)")
    p.add_argument("--value-stake", type=float, default=25.0, help="stake used to size VALUE bets, $ (default 25)")
    p.add_argument("--no-value", action="store_true", help="only show guaranteed arbs")
    p.add_argument("--max-age", type=float, default=60.0, help="ignore live quotes older than N seconds (default 60)")
    p.add_argument("--max-age-pregame", type=float, default=600.0,
                   help="ignore pre-game quotes older than N seconds (default 600)")
    p.add_argument("--fee", action="append", default=[], metavar="VENUE=RATE",
                   help="override a taker fee rate, e.g. --fee kalshi=0.07 (repeatable)")
    p.add_argument("--watch", type=float, metavar="SECONDS", help="rescan every N seconds until Ctrl-C")
    p.add_argument("--beep", action="store_true", help="ring the terminal bell on new opportunities")
    p.add_argument("--json", action="store_true", help="print JSON instead of bet slips")
    p.add_argument("--log", metavar="CSV", help="append every opportunity found to a CSV file")
    p.add_argument("--save", metavar="FILE", help="save the raw odds feed to a file (to replay with --from-file)")
    p.add_argument("--from-file", metavar="FILE", help="scan a saved feed instead of calling the API")
    p.add_argument("--demo", action="store_true", help="scan the bundled sample feed (no API key needed)")
    p.add_argument("--list-sports", action="store_true", help="list sport keys (free, no credits used)")
    e = p.add_argument_group("esports mode (Kalshi + Polymarket US order books, no API key needed)")
    e.add_argument("--esports", action="store_true", help="scan esports series-winner markets instead")
    e.add_argument("--games", default=None, help="valorant,cs2,lol,dota2 (default: all)")
    e.add_argument("--probe", action="store_true",
                   help="show what each venue lists and what matched, instead of arbs")
    e.add_argument("--aliases", metavar="JSON", help='team names that differ, e.g. {"Movistar KOI": "KOI"}')
    e.add_argument("--kalshi-series", action="append", default=[], metavar="GAME=TICKER",
                   help="override Kalshi series tickers, e.g. dota2=KXDOTA2GAME (repeatable)")
    e.add_argument("--pmus-pages", type=int, default=5,
                   help="extra Polymarket US market-list pages to search, 100 each (default 5)")
    pt = p.add_argument_group("paper trading (esports): measure what you'd really have made, no orders")
    pt.add_argument("--paper", action="store_true", help="scan on a timer, log arbs, recheck each one later")
    pt.add_argument("--recheck", type=float, default=20.0,
                    help="seconds to wait before checking whether an arb was still fillable (default 20)")
    pt.add_argument("--paper-log", default="paper.jsonl", help="where to write the log (default paper.jsonl)")
    pt.add_argument("--minutes", type=float, help="stop after this many minutes")
    pt.add_argument("--hours", type=float, help="stop after this many hours")
    pt.add_argument("--report", metavar="LOG", help="summarise a paper-trading log and exit")
    return p.parse_args(argv)


def _csv(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    args = parse_args(argv)

    for item in args.fee:
        try:
            k, rate = item.split("=", 1)
            get_venue(k.strip()).fee_rate = float(rate)
        except ValueError:
            print(f"Bad --fee value {item!r}; use VENUE=RATE, e.g. kalshi=0.07", file=sys.stderr)
            return 2

    if args.report:
        import esports
        try:
            print(esports.report(args.report))
        except OSError as e:
            print(f"Couldn't read {args.report}: {e}", file=sys.stderr)
            return 1
        return 0

    if args.paper:
        args.esports = True

    if args.esports:
        import esports
        return esports.run(args, {"kalshi": VENUES["kalshi"].fee_rate,
                                  "polymarket_us": VENUES["polymarket_us"].fee_rate})

    offline = args.demo or args.from_file
    markets = tuple(_csv(args.markets)) if args.markets else (
        ("h2h", "spreads", "totals") if offline else ("h2h",))
    bad = [m for m in markets if m not in ("h2h", "spreads", "totals")]
    if bad:
        print(f"Unsupported market(s): {', '.join(bad)}. Use h2h, spreads, totals.", file=sys.stderr)
        return 2

    cfg = Config(bet_on=_csv(args.bet_on), reference=[] if args.no_value else _csv(args.reference),
                 markets=markets, budget=args.budget, min_profit_pct=args.min_profit,
                 min_ev_pct=args.min_ev, value_stake=args.value_stake,
                 max_age_live=args.max_age, max_age_pregame=args.max_age_pregame)
    books = list(dict.fromkeys(cfg.bet_on + _csv(args.reference)))
    sports = _csv(args.sports)

    if not offline and not args.api_key:
        print("No API key. Get a free one at https://the-odds-api.com, then run with --api-key KEY "
              "or set ODDS_API_KEY.\nTo try it without a key: python arbscan.py --demo", file=sys.stderr)
        return 2

    if args.list_sports:
        try:
            data, _ = api_get("/v4/sports/", {"apiKey": args.api_key})
        except ApiError as e:
            print(e, file=sys.stderr)
            return 1
        for s in data:
            print(f"{s.get('key', ''):<40} {s.get('title', '')}")
        return 0

    if not offline:
        cost = credits_per_scan(len(sports), len(markets), len(books))
        msg = f"Each scan costs about {cost} API credit{'s' if cost != 1 else ''}"
        if args.watch:
            msg += f"; every {args.watch:g}s that's ~{cost * 86400 / args.watch:,.0f} per day"
        print(msg + ".", file=sys.stderr)

    seen_keys: set = set()
    first = True
    while True:
        now = datetime.now(timezone.utc)
        quota: dict = {}
        try:
            if offline:
                path = args.from_file or os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_odds.json")
                events, file_now = load_file(path)
                now = file_now or now
                source = "demo data" if args.demo else os.path.basename(path)
            else:
                events, quota = fetch_odds(args.api_key, sports, books, markets)
                source = "live"
                if args.save:
                    with open(args.save, "w", encoding="utf-8") as f:
                        json.dump({"fetched_at": now.isoformat(), "events": events}, f)
        except ApiError as e:
            print(e, file=sys.stderr)
            if not args.watch:
                return 1
            time.sleep(args.watch)
            continue
        except (OSError, json.JSONDecodeError) as e:
            print(f"Couldn't read odds file: {e}", file=sys.stderr)
            return 1

        opps, stats = scan(events, cfg, now)

        if first and not offline:
            present = {bm.get("key") for ev in events for bm in ev.get("bookmakers") or []}
            missing = [b for b in books if b not in present]
            if events and missing:
                print("No odds came back for: " + ", ".join(get_venue(b).name for b in missing)
                      + ". They may have no lines on these games, or your plan may not include them.",
                      file=sys.stderr)

        if args.json:
            print(json.dumps({"scanned_at": now.isoformat(), "source": source,
                              "stats": stats.__dict__, "quota": quota,
                              "opportunities": [o.to_dict(now) for o in opps]}, indent=2))
        else:
            fresh = [o for o in opps if o.key() not in seen_keys] if args.watch else opps
            for o in fresh:
                print(render(o, now))
            if fresh:
                print("=" * 78)
                print(FOOTER)
                if args.beep:
                    print("\a", end="")
            print(summary_line(stats, opps, quota, source))

        if args.log and opps:
            new = [o for o in opps if o.key() not in seen_keys]
            if new:
                append_log(args.log, new, now)
        seen_keys |= {o.key() for o in opps}
        first = False

        if not args.watch or offline:
            return 0
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
