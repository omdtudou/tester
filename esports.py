"""
esports.py - esports arbitrage straight from the venues' own order books.

Used by `python arbscan.py --esports`. No API keys and no paid data feed:

  1. Lists open series-winner markets for Valorant, CS2, League of Legends and
     Dota 2 from Kalshi's and Polymarket US's free public APIs.
  2. Pairs a Kalshi match with a Polymarket US match only when both list the
     same two teams (after name clean-up) on compatible dates. Anything unclear
     is skipped, never guessed.
  3. Reads both live order books and walks them level by level, so each arb is
     sized to the contracts actually for sale, with each venue's taker fee.

It never places orders.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
PMUS_API = "https://gateway.polymarket.us"
UA = "arbscan/1.1"

# Kalshi series for the series (match) winner. KXLOLMAP / map markets are
# deliberately absent. Override with --kalshi-series GAME=TICKER.
GAMES: Dict[str, dict] = {
    "valorant": {"name": "Valorant", "kalshi": ["KXVALORANTGAME"],
                 "search": ["valorant"], "words": ["valorant", "vct", "vcl"], "slug": {"val", "valorant"}},
    "cs2": {"name": "CS2", "kalshi": ["KXCS2GAME"],
            "search": ["counter-strike", "cs2"], "words": ["counter-strike", "counter strike", "cs2", "csgo", "cs:go"],
            "slug": {"cs2", "csgo"}},
    "lol": {"name": "League of Legends", "kalshi": ["KXLOLGAME"],
            "search": ["league of legends"], "words": ["league of legends", "lck", "lec", "lpl", "lcs"],
            "slug": {"lol"}},
    "dota2": {"name": "Dota 2", "kalshi": ["KXDOTA2GAME"],   # unconfirmed ticker; skipped if absent
              "search": ["dota"], "words": ["dota"], "slug": {"dota", "dota2"}},
}

CLOSED_STATUSES = {"closed", "settled", "finalized", "determined", "inactive", "deactivated"}
NOT_SERIES_RE = re.compile(
    r"\b(map|game)\s*#?\d+\b|first blood|\bkills?\b|handicap|\btotal\b|o/u|over/under|\bspread\b|\bpistol\b")
BO2_RE = re.compile(r"\bbo\s*2\b|\bbest[\s-]of[\s-](2|two)\b")
FORMAT_RE = re.compile(r"\bbo\s*([135])\b|\bbest[\s-]of[\s-]([135])\b")
TEAM_FILLER = {"esports", "esport", "e", "sports", "gaming", "team", "club", "gg", "the"}
# Well-known names that venues write differently. Extend with --aliases.
BUILTIN_ALIASES = {"natus vincere": "navi", "ninjas in pyjamas": "nip", "mousesports": "mouz",
                   "100 thieves": "100t"}


class VenueError(RuntimeError):
    pass


# --------------------------------------------------------------------------- money

def ceil_cent(x: float) -> float:
    return math.ceil(round(x * 100, 6)) / 100


def money(x: float) -> str:
    return f"${x:,.2f}"


def cents(p: float) -> str:
    c = p * 100
    return f"{c:.0f}¢" if abs(c - round(c)) < 1e-6 else f"{c:.1f}¢"


# --------------------------------------------------------------------------- HTTP (live, recording or replay)

class Http:
    def __init__(self, replay: Optional[dict] = None, record: Optional[dict] = None):
        self.replay = replay
        self.record = record
        self.calls = 0
        self._last: Dict[str, float] = {}

    @staticmethod
    def build(base: str, params: Optional[dict] = None) -> str:
        return base + ("?" + urllib.parse.urlencode(params) if params else "")

    def get(self, base: str, params: Optional[dict] = None, min_interval: float = 0.0):
        url = self.build(base, params)
        if self.replay is not None:
            return self.replay.get(url)
        host = urllib.parse.urlsplit(url).netloc
        last_err = "no response"
        for attempt in range(4):
            wait = self._last.get(host, 0.0) + min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._last[host] = time.monotonic()
                self.calls += 1
                if self.record is not None:
                    self.record[url] = data
                return data
            except urllib.error.HTTPError as e:
                self._last[host] = time.monotonic()
                if e.code == 404:
                    if self.record is not None:
                        self.record[url] = None
                    return None
                last_err = f"HTTP {e.code}"
                if e.code not in (429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
                last_err = str(getattr(e, "reason", e))
            time.sleep(1.5 * 2 ** attempt)
        raise VenueError(f"{base} failed ({last_err})")


# --------------------------------------------------------------------------- team names

def team_key(name: str, aliases: Optional[Dict[str, str]] = None) -> str:
    """Comparable form of a team name: accents, punctuation and filler words removed.

    "Team Liquid" == "Liquid", "Leviatán Esports" == "Leviatan", but
    "Spirit Academy" != "Spirit" and "Liquid Brazil" != "Liquid".
    """
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s.replace("&", " and "))
    words = s.split()
    key = " ".join(w for w in words if w not in TEAM_FILLER) or " ".join(words)
    key = BUILTIN_ALIASES.get(key, key)
    if aliases:
        key = aliases.get(key, key)
    return key


def load_aliases(path: Optional[str]) -> Dict[str, str]:
    """JSON file of {"name on one venue": "name on the other"} pairs, either direction."""
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, str] = {}
    for a, b in raw.items():
        ka, kb = team_key(a), team_key(b)
        canonical = min(ka, kb)
        out[ka] = canonical
        out[kb] = canonical
    return out


# --------------------------------------------------------------------------- listings

@dataclass
class Listing:
    venue: str                      # kalshi | polymarket_us
    game: str
    title: str
    names: Dict[str, str]           # team key -> name as the venue shows it
    ids: Dict[str, str]             # kalshi: team key -> market ticker; pmus: both -> slug
    start: Optional[datetime] = None
    start_kind: str = "none"        # time | date | loose | none
    long_key: Optional[str] = None  # pmus: which team the long side is
    fmt: Optional[str] = None       # "BO3" etc. when stated
    fee_rate: Optional[float] = None  # pmus: the market's own feeCoefficient

    @property
    def keys(self) -> frozenset:
        return frozenset(self.names)


@dataclass
class Discovery:
    kalshi: Dict[str, List[Listing]] = field(default_factory=dict)        # game -> listings
    pmus: List[Listing] = field(default_factory=list)
    pmus_seen: int = 0
    skipped: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    notes: List[str] = field(default_factory=list)
    sample_market: Optional[dict] = None


def parse_kalshi_start(event_ticker: str) -> Tuple[Optional[datetime], str]:
    """KXCS2GAME-26OCT131200HACPRO -> 2026-10-13 12:00 ET. Times are Eastern;
    a fixed UTC-5 is close enough for matching windows measured in days."""
    suffix = event_ticker.split("-", 1)[1] if "-" in event_ticker else ""
    m = re.match(r"(\d{2})([A-Z]{3})(\d{2})(?:(\d{2})(\d{2})(?=[A-Z]))?", suffix)
    if not m:
        return None, "none"
    try:
        day = datetime.strptime(f"{m.group(1)}{m.group(2).title()}{m.group(3)}", "%y%b%d")
    except ValueError:
        return None, "none"
    if m.group(4) and int(m.group(4)) < 24 and int(m.group(5)) < 60:
        local = day.replace(hour=int(m.group(4)), minute=int(m.group(5)))
        return (local + timedelta(hours=5)).replace(tzinfo=timezone.utc), "time"
    return (day + timedelta(hours=17)).replace(tzinfo=timezone.utc), "date"


def parse_iso(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def kalshi_events(http: Http, series: str, max_pages: int = 10) -> list:
    events, cursor = [], None
    for _ in range(max_pages):
        params = {"series_ticker": series, "status": "open", "with_nested_markets": "true", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = http.get(f"{KALSHI_API}/events", params) or {}
        events.extend(data.get("events") or [])
        cursor = data.get("cursor")
        if not cursor:
            break
    return events


def kalshi_listings(http: Http, game: str, series_list: List[str], aliases, disc: Discovery) -> List[Listing]:
    out = []
    for series in series_list:
        try:
            events = kalshi_events(http, series)
        except VenueError as e:
            disc.notes.append(f"Kalshi {series}: {e}")
            continue
        if not events:
            disc.notes.append(f"Kalshi {series}: no open events (or the series doesn't exist)")
        for ev in events:
            markets = [m for m in ev.get("markets") or []
                       if str(m.get("status", "")).lower() not in CLOSED_STATUSES]
            if len(markets) != 2:
                disc.skipped["kalshi: not exactly two teams"] += 1
                continue
            names = [(m.get("yes_sub_title") or "").strip() for m in markets]
            keys = [team_key(n, aliases) for n in names]
            if not all(names) or keys[0] == keys[1]:
                disc.skipped["kalshi: unclear team names"] += 1
                continue
            start, kind = parse_kalshi_start(ev.get("event_ticker") or markets[0].get("event_ticker", ""))
            text = f"{ev.get('title', '')} {ev.get('sub_title', '')}".lower()
            fm = FORMAT_RE.search(text)
            out.append(Listing(
                venue="kalshi", game=game, title=ev.get("title") or " vs ".join(names),
                names=dict(zip(keys, names)), ids={k: m.get("ticker", "") for k, m in zip(keys, markets)},
                start=start, start_kind=kind, fmt=f"BO{fm.group(1) or fm.group(2)}" if fm else None))
    return out


def _find_markets(obj, out: list) -> None:
    """Collect every dict that looks like a Polymarket US market, whatever the nesting."""
    if isinstance(obj, dict):
        if "slug" in obj and isinstance(obj.get("marketSides"), list):
            out.append(obj)
            return
        for v in obj.values():
            _find_markets(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _find_markets(v, out)


def classify_game(text: str, slug: str) -> Optional[str]:
    tokens = set(slug.lower().split("-"))
    for g, spec in GAMES.items():
        if tokens & spec["slug"] or any(re.search(rf"\b{re.escape(w)}\b", text) for w in spec["words"]):
            return g
    return None


def _fee_coefficient(m: dict) -> Optional[float]:
    try:
        v = float(m.get("feeCoefficient"))
    except (TypeError, ValueError):
        return None
    return v if 0 < v < 0.25 else None


def pmus_listing(m: dict, game_hint: Optional[str], aliases) -> Tuple[Optional[Listing], str]:
    status = str(m.get("status") or "").upper()
    if m.get("closed") is True or m.get("active") is False or (status and not status.endswith("OPEN")):
        return None, "closed"
    # Live API values look like "SPORTS_MARKET_TYPE_MONEYLINE"; docs show plain "MONEYLINE".
    v2 = str(m.get("sportsMarketTypeV2") or "").upper()
    if v2 and not v2.endswith("MONEYLINE"):
        return None, "not a series-winner market"
    slug = str(m.get("slug") or "")
    text = " ".join(str(m.get(k) or "") for k in
                    ("question", "title", "sportsMarketType", "category", "subcategory", "slug")).lower()
    if NOT_SERIES_RE.search(text):
        return None, "single map/game or prop market"
    if BO2_RE.search(text):
        return None, "best-of-2 (can end in a draw)"
    sides = m.get("marketSides") or []
    longs = [s for s in sides if s.get("long") is True]
    if len(sides) != 2 or len(longs) != 1:
        return None, "can't tell which side is which"
    names = [str(s.get("description") or s.get("identifier") or "").strip() for s in sides]
    if any(n.lower() in ("", "yes", "no") for n in names):
        return None, "sides aren't team names"
    game = classify_game(text, slug) or game_hint
    if game not in GAMES:
        return None, "not an esports game we scan"
    keys = [team_key(n, aliases) for n in names]
    if keys[0] == keys[1]:
        return None, "unclear team names"
    long_key = keys[sides.index(longs[0])]

    start = parse_iso(m.get("gameStartTime") or m.get("eventStartTime") or m.get("startTime"))
    kind = "time" if start else "none"
    if not start:
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", slug)
        if dm:
            start = parse_iso(dm.group(1) + "T17:00:00+00:00")
            kind = "date" if start else "none"
    if not start:
        start = parse_iso(m.get("endDate"))
        kind = "loose" if start else "none"
    fm = FORMAT_RE.search(text)
    return Listing(venue="polymarket_us", game=game, title=str(m.get("question") or m.get("title") or slug),
                   names=dict(zip(keys, names)), ids={k: slug for k in keys}, start=start, start_kind=kind,
                   long_key=long_key, fmt=f"BO{fm.group(1) or fm.group(2)}" if fm else None,
                   fee_rate=_fee_coefficient(m)), "ok"


def pmus_listings(http: Http, games: List[str], aliases, disc: Discovery, pages: int) -> List[Listing]:
    raw: Dict[str, Tuple[dict, Optional[str]]] = {}
    for g in games:
        for q in GAMES[g]["search"]:
            try:
                data = http.get(f"{PMUS_API}/v1/search", {"query": q}, min_interval=0.35)
            except VenueError as e:
                disc.notes.append(f"Polymarket US search '{q}': {e}")
                continue
            found: list = []
            _find_markets(data, found)
            for m in found:
                raw.setdefault(str(m.get("slug")), (m, g))
    for i in range(pages):   # broad listing as a backstop for anything search missed
        try:
            data = http.get(f"{PMUS_API}/v1/markets",
                            {"active": "true", "closed": "false", "limit": 100, "offset": i * 100},
                            min_interval=0.35)
        except VenueError as e:
            disc.notes.append(f"Polymarket US markets page {i + 1}: {e}")
            break
        found = []
        _find_markets(data, found)
        for m in found:
            raw.setdefault(str(m.get("slug")), (m, None))
        if len(found) < 100:
            break

    disc.pmus_seen = len(raw)
    out = []
    for slug, (m, hint) in raw.items():
        listing, why = pmus_listing(m, hint, aliases)
        if listing is None:
            if why != "not an esports game we scan":
                disc.skipped[f"polymarket us: {why}"] += 1
            continue
        if listing.game in games:
            if disc.sample_market is None:
                disc.sample_market = m
            out.append(listing)
    return out


# --------------------------------------------------------------------------- matching

def _window(a: Listing, b: Listing) -> Optional[float]:
    kinds = {a.start_kind, b.start_kind}
    if "none" in kinds:
        return None
    if "loose" in kinds:
        return 96.0
    if "date" in kinds:
        return 48.0
    return 12.0     # both venues give an exact start time


def dates_compatible(a: Listing, b: Listing) -> Optional[bool]:
    hours = _window(a, b)
    if hours is None:
        return None
    return abs((a.start - b.start).total_seconds()) <= hours * 3600


@dataclass
class Pair:
    kalshi: Listing
    pmus: Listing
    confirmed_date: bool


def match(kalshi: List[Listing], pmus: List[Listing]) -> Tuple[List[Pair], List[Listing], List[Listing], int]:
    """Same game + same two teams + compatible dates. Ambiguity means no pair."""
    k_by: Dict[tuple, List[Listing]] = defaultdict(list)
    p_by: Dict[tuple, List[Listing]] = defaultdict(list)
    for k in kalshi:
        k_by[(k.game, k.keys)].append(k)
    for p in pmus:
        p_by[(p.game, p.keys)].append(p)

    pairs, ambiguous, used_p = [], 0, set()
    for key, ks in k_by.items():
        ps = p_by.get(key, [])
        for k in ks:
            cands = []
            for p in ps:
                ok = dates_compatible(k, p)
                if ok is True:
                    cands.append((p, True))
                elif ok is None and len(ks) == 1 and len(ps) == 1:
                    cands.append((p, False))     # only one such match listed anywhere
            if len(cands) == 1 and id(cands[0][0]) not in used_p:
                rivals = [k2 for k2 in ks if k2 is not k and dates_compatible(k2, cands[0][0])]
                if not rivals:
                    pairs.append(Pair(k, cands[0][0], cands[0][1]))
                    used_p.add(id(cands[0][0]))
                    continue
            if any(dates_compatible(k, p) is not False for p in ps):
                ambiguous += 1      # same two teams on both venues, but we can't tell which listing is which
    unmatched_k = [k for k in kalshi if not any(pr.kalshi is k for pr in pairs)]
    unmatched_p = [p for p in pmus if id(p) not in used_p]
    return pairs, unmatched_k, unmatched_p, ambiguous


# --------------------------------------------------------------------------- order books

Ladder = List[Tuple[float, float]]   # (price to buy one contract, contracts), cheapest first


def _clean(levels: Ladder) -> Ladder:
    out = [(round(p, 6), q) for p, q in levels if 0.0 < p < 1.0 and q > 0]
    return sorted(out, key=lambda x: x[0])


def kalshi_book(http: Http, ticker: str) -> Tuple[Ladder, Ladder]:
    """Returns (yes_bids, no_bids) as (price, contracts). Kalshi only publishes bids;
    buying YES at p means matching a NO bid at 1 - p, and vice versa."""
    data = http.get(f"{KALSHI_API}/markets/{urllib.parse.quote(ticker)}/orderbook") or {}
    ob = data.get("orderbook_fp")
    if isinstance(ob, dict):
        yes = [(float(p), float(q)) for p, q in ob.get("yes_dollars") or []]
        no = [(float(p), float(q)) for p, q in ob.get("no_dollars") or []]
    else:   # older integer-cents format
        ob = data.get("orderbook") or {}
        yes = [(float(p) / 100, float(q)) for p, q in ob.get("yes") or []]
        no = [(float(p) / 100, float(q)) for p, q in ob.get("no") or []]
    return yes, no


def _px(level: dict) -> Optional[float]:
    px = level.get("px")
    if isinstance(px, dict):
        px = px.get("value")
    try:
        v = float(px)
    except (TypeError, ValueError):
        return None
    return v if 0 < v < 1 else None     # anything else is in units we don't know: skip it


def pmus_book(http: Http, slug: str) -> Tuple[Optional[str], Ladder, Ladder]:
    """Returns (state, bids, offers) for the market's long side."""
    data = http.get(f"{PMUS_API}/v1/markets/{urllib.parse.quote(slug)}/book", min_interval=0.35) or {}
    md = data.get("marketData") if isinstance(data.get("marketData"), dict) else data
    bids, offers = [], []
    for lvl in md.get("bids") or []:
        p = _px(lvl)
        if p is not None:
            bids.append((p, float(lvl.get("qty") or 0)))
    for lvl in md.get("offers") or md.get("asks") or []:
        p = _px(lvl)
        if p is not None:
            offers.append((p, float(lvl.get("qty") or 0)))
    return md.get("state"), bids, offers


def flip(bids: Ladder) -> Ladder:
    """Bids on one side are offers on the other side at 1 - price."""
    return _clean([(1.0 - p, q) for p, q in bids])


# --------------------------------------------------------------------------- sizing by walking the books

class Walker:
    """Buys a ladder one contract at a time, tracking cost and per-level fees.

    Fees are rounded up to the cent per price level, which is at least as
    much as the venue charges when an order fills across several levels."""

    def __init__(self, ladder: Ladder, fee_rate: float):
        self.lv = [x for x in ladder if x[1] > 0]
        self.rate = fee_rate
        self.i = 0
        self.used = 0.0
        self.cost = 0.0
        self.closed_fee = 0.0
        self.n = 0
        self.worst = None

    def depth(self) -> float:
        return sum(q for _, q in self.lv)

    def add_one(self) -> None:
        need = 1.0
        while need > 1e-12:
            p, q = self.lv[self.i]
            take = min(need, q - self.used)
            self.cost += take * p
            self.used += take
            need -= take
            self.worst = p
            if q - self.used <= 1e-12:
                self.closed_fee += ceil_cent(self.rate * q * p * (1 - p))
                self.i += 1
                self.used = 0.0
        self.n += 1

    @property
    def fee(self) -> float:
        open_fee = 0.0
        if self.used > 0 and self.i < len(self.lv):
            p = self.lv[self.i][0]
            open_fee = ceil_cent(self.rate * self.used * p * (1 - p))
        return round(self.closed_fee + open_fee, 2)

    @property
    def spend(self) -> float:
        return ceil_cent(self.cost)


@dataclass
class EsLeg:
    venue: str
    team: str
    contract: str      # what to buy, in the venue's own terms
    market_id: str
    contracts: int
    limit: float       # worst price you need to accept for the whole size
    avg: float
    spend: float
    fee: float
    top_size: float    # contracts at the best price
    side: str = ""     # kalshi: yes|no on market_id; polymarket_us: long|short
    fee_rate: float = 0.0

    @property
    def cost(self) -> float:
        return round(self.spend + self.fee, 2)


def optimise(lad_a: Ladder, rate_a: float, lad_b: Ladder, rate_b: float, budget: float):
    """Most profitable equal number of contracts on both legs within budget and depth."""
    wa, wb = Walker(lad_a, rate_a), Walker(lad_b, rate_b)
    n_max = int(min(wa.depth(), wb.depth()) + 1e-9)
    best = None
    for n in range(1, n_max + 1):
        wa.add_one()
        wb.add_one()
        outlay = round(wa.spend + wa.fee + wb.spend + wb.fee, 2)
        if outlay > budget + 1e-9:
            break
        profit = round(n - outlay, 2)
        if best is None or profit > best["profit"] + 1e-9:
            best = {"n": n, "profit": profit, "outlay": outlay,
                    "a": (wa.spend, wa.fee, wa.worst, wa.cost / n),
                    "b": (wb.spend, wb.fee, wb.worst, wb.cost / n)}
    return best


@dataclass
class EsArb:
    game: str
    title: str
    start: Optional[datetime]
    fmt: Optional[str]
    legs: List[EsLeg]
    outlay: float
    profit: float
    pct: float
    depth_limited: bool
    warnings: List[str] = field(default_factory=list)
    pair: Optional["Pair"] = None

    def key(self) -> tuple:
        return (self.title, tuple((l.venue, l.team, l.limit, l.contracts) for l in self.legs))

    @property
    def op_id(self) -> str:
        """Stable identity of the opportunity (same markets and sides), across price changes."""
        return "|".join(f"{l.venue}:{l.market_id}:{l.side}" for l in self.legs)

    def to_dict(self) -> dict:
        return {"kind": "arb", "game": GAMES[self.game]["name"], "event": self.title,
                "start": self.start.isoformat() if self.start else None, "format": self.fmt,
                "pct": round(self.pct, 3), "outlay": self.outlay, "profit": self.profit,
                "depth_limited": self.depth_limited,
                "legs": [{"venue": l.venue, "team": l.team, "contract": l.contract, "market": l.market_id,
                          "contracts": l.contracts, "limit_price": l.limit, "avg_price": round(l.avg, 4),
                          "spend": l.spend, "fee": l.fee, "top_of_book_size": l.top_size} for l in self.legs],
                "warnings": self.warnings}


@dataclass
class EsStats:
    pairs: int = 0
    books_checked: int = 0
    gross_only: int = 0
    not_open: int = 0
    empty_books: int = 0


def evaluate_pair(http: Http, pair: Pair, fees: Dict[str, float], budget: float, min_profit_pct: float,
                  suspicious_pct: float, stats: EsStats) -> Optional[EsArb]:
    k, p = pair.kalshi, pair.pmus
    a, b = sorted(k.keys)
    yes_bids, no_bids = {}, {}
    for team in (a, b):
        yes_bids[team], no_bids[team] = kalshi_book(http, k.ids[team])
    state, pm_bids, pm_offers = pmus_book(http, p.ids[a])
    stats.books_checked += 1
    if state and "OPEN" not in str(state).upper().replace("PREOPEN", ""):
        stats.not_open += 1
        return None

    other = {a: b, b: a}
    # Ways to back each team on Kalshi: YES on its own market, or NO on the opponent's.
    kalshi_ways = {t: [(f'YES "{k.names[t]}"', k.ids[t], flip(no_bids[t]), "yes"),
                       (f'NO "{k.names[other[t]]}" (= {k.names[t]})', k.ids[other[t]],
                        flip(yes_bids[other[t]]), "no")]
                   for t in (a, b)}
    pm_way = {p.long_key: _clean(pm_offers), other[p.long_key]: flip(pm_bids)}
    pm_rate = fees["polymarket_us"] if fees.get("pm_override") or p.fee_rate is None else p.fee_rate
    if not any(yes_bids[t] or no_bids[t] for t in (a, b)) or not (pm_bids or pm_offers):
        stats.empty_books += 1
        return None

    best, gross_seen = None, False
    for t_k in (a, b):
        t_p = other[t_k]
        lad_p = pm_way[t_p]
        if not lad_p:
            continue
        for label, ticker, lad_k, k_side in kalshi_ways[t_k]:
            if not lad_k:
                continue
            if lad_k[0][0] + lad_p[0][0] < 1.0:
                gross_seen = True
            r = optimise(lad_k, fees["kalshi"], lad_p, pm_rate, budget)
            if r and r["profit"] > 0 and (best is None or r["profit"] > best[0]["profit"]):
                best = (r, t_k, label, ticker, lad_k, t_p, lad_p, k_side)
    if best is None:
        if gross_seen:
            stats.gross_only += 1
        return None
    r, t_k, label, ticker, lad_k, t_p, lad_p, k_side = best
    p_side = "long" if t_p == p.long_key else "short"
    pct = r["profit"] / r["outlay"] * 100
    if pct < min_profit_pct:
        stats.gross_only += 1
        return None

    sk, fk, wk, ak = r["a"]
    sp, fp, wp, ap = r["b"]
    legs = [
        EsLeg("kalshi", k.names[t_k], label, ticker, r["n"], wk, ak, sk, fk, lad_k[0][1], k_side, fees["kalshi"]),
        EsLeg("polymarket_us", p.names[t_p], f'"{p.names[t_p]}"', p.ids[t_p], r["n"], wp, ap, sp, fp,
              lad_p[0][1], p_side, pm_rate),
    ]
    depth_limited = r["outlay"] < budget * 0.9

    warnings = ["If the match is forfeited, cancelled or postponed, Kalshi may settle at the \"last fair "
                "price\" while Polymarket US uses its own rule (often 50-50), so the hedge can break."]
    if not pair.confirmed_date:
        warnings.append("Couldn't confirm the start time on both venues. Check it's the same match "
                        "(teams can meet twice in a bracket).")
    if not (k.fmt or p.fmt):
        warnings.append("Check both markets are for the whole series, not a single map.")
    elif k.fmt and p.fmt and k.fmt != p.fmt:
        warnings.insert(0, f"Series format differs ({k.fmt} vs {p.fmt}). This is probably not the same match.")
    if pct > suspicious_pct:
        warnings.insert(0, "Unusually large edge. Usually a market about to suspend, or a mismatch; check by hand.")
    return EsArb(k.game, p.title if len(p.title) > len(k.title) else k.title, k.start or p.start,
                 k.fmt or p.fmt, legs, r["outlay"], r["profit"], pct, depth_limited, warnings, pair)


# --------------------------------------------------------------------------- one full scan

def discover(http: Http, games: List[str], series: Dict[str, List[str]], aliases, pages: int) -> Discovery:
    disc = Discovery()
    for g in games:
        disc.kalshi[g] = kalshi_listings(http, g, series.get(g, GAMES[g]["kalshi"]), aliases, disc)
    disc.pmus = pmus_listings(http, games, aliases, disc, pages)
    return disc


def scan(http: Http, games: List[str], series, aliases, fees, budget, min_profit_pct,
         suspicious_pct=8.0, pages=5):
    disc = discover(http, games, series, aliases, pages)
    kalshi_all = [l for g in games for l in disc.kalshi.get(g, [])]
    pairs, un_k, un_p, ambiguous = match(kalshi_all, disc.pmus)
    stats = EsStats(pairs=len(pairs))
    arbs = []
    for pr in pairs:
        try:
            arb = evaluate_pair(http, pr, fees, budget, min_profit_pct, suspicious_pct, stats)
        except VenueError as e:
            disc.notes.append(f"Order book for {pr.kalshi.title}: {e}")
            continue
        if arb:
            arbs.append(arb)
    arbs.sort(key=lambda a: -a.pct)
    return arbs, stats, disc, (un_k, un_p, ambiguous)


# --------------------------------------------------------------------------- output

VENUE_NAMES = {"kalshi": "Kalshi", "polymarket_us": "Polymarket US"}


def render(a: EsArb) -> str:
    when = a.start.astimezone().strftime("%a %b %d %I:%M %p") if a.start else "start time ?"
    lines = ["=" * 78, f"ARB  +{a.pct:.2f}% guaranteed after fees  (sized from live order books)",
             f"{GAMES[a.game]['name']} | {a.title} | {when} | Series winner{' ' + a.fmt if a.fmt else ''}"]
    for i, l in enumerate(a.legs, 1):
        action = f"BUY {l.contracts} at <= {cents(l.limit)} (avg {cents(l.avg)})"
        lines.append(f"  {i}. {VENUE_NAMES[l.venue]:<14} {l.contract:<36} {action:<34} "
                     f"{money(l.spend)} + {money(l.fee)} fee")
        lines.append(f"     {l.market_id}")
    lines.append(f"  Outlay {money(a.outlay)} -> pays {money(float(a.legs[0].contracts))} whichever team wins "
                 f"-> profit {money(a.profit)}")
    if a.depth_limited:
        lines.append(f"  Size is capped by the order books, not your budget "
                     f"(best-price size: {a.legs[0].top_size:g} / {a.legs[1].top_size:g}).")
    for w in a.warnings:
        lines.append(f"  ! {w}")
    return "\n".join(lines)


FOOTER = ("Before betting: use LIMIT orders at the prices shown, place the thinner leg first, and only place "
          "the second\nonce the first has filled. Books move in seconds; if a price is gone, skip it.")


def probe_report(disc: Discovery, games: List[str], series, un_k, un_p, ambiguous, pairs: int) -> str:
    out = ["Esports probe (read-only, no orders)", ""]
    for g in games:
        tickers = ", ".join(series.get(g, GAMES[g]["kalshi"]))
        out.append(f"Kalshi {GAMES[g]['name']:<18} {len(disc.kalshi.get(g, [])):>3} open matches  ({tickers})")
    by_game = defaultdict(int)
    for p in disc.pmus:
        by_game[p.game] += 1
    out.append(f"Polymarket US: {disc.pmus_seen} markets looked at, "
               + ", ".join(f"{GAMES[g]['name']} {by_game.get(g, 0)}" for g in games) + " series-winner markets")
    for why, n in sorted(disc.skipped.items(), key=lambda x: -x[1]):
        out.append(f"  skipped {n:>4}  {why}")
    out.append("")
    out.append(f"Matched {pairs} match(es) on both venues; {ambiguous} ambiguous left out.")
    for label, items in (("Only on Kalshi", un_k), ("Only on Polymarket US", un_p)):
        if items:
            out.append(f"{label} (first 8):")
            for l in items[:8]:
                when = l.start.astimezone().strftime("%b %d") if l.start else "date ?"
                out.append(f"  {GAMES[l.game]['name']:<18} {' vs '.join(l.names.values())}  [{when}]")
    if disc.notes:
        out.append("")
        out.extend(f"note: {n}" for n in disc.notes)
    if disc.sample_market:
        m = disc.sample_market
        out.append("")
        out.append("Sample Polymarket US market fields (to check the mapping):")
        out.append("  keys: " + ", ".join(sorted(m.keys())))
        for s in m.get("marketSides") or []:
            out.append(f"  side: long={s.get('long')!r} description={s.get('description')!r} "
                       f"identifier={s.get('identifier')!r}")
    out.append("")
    out.append("If team names differ between venues, add them to an aliases file (--aliases) and re-run.")
    return "\n".join(out)


# --------------------------------------------------------------------------- paper trading

def leg_ladder(http: Http, leg: EsLeg) -> Ladder:
    """A fresh ladder for exactly the contract the slip told you to buy."""
    if leg.venue == "kalshi":
        yes, no = kalshi_book(http, leg.market_id)
        return flip(no) if leg.side == "yes" else flip(yes)
    state, bids, offers = pmus_book(http, leg.market_id)
    if state and "OPEN" not in str(state).upper().replace("PREOPEN", ""):
        return []
    return _clean(offers) if leg.side == "long" else flip(bids)


def capped(ladder: Ladder, limit: float, n: int) -> Ladder:
    """The part of a ladder a limit order at `limit` for n contracts would take."""
    out, left = [], float(n)
    for p, q in ladder:
        if p > limit + 1e-9 or left <= 1e-9:
            break
        take = min(q, left)
        out.append((p, take))
        left -= take
    return out


def recheck(http: Http, arb: EsArb, fees: Dict[str, float], budget: float) -> dict:
    """What placing both of the slip's limit orders right now would have got you."""
    fresh = [leg_ladder(http, l) for l in arb.legs]
    caps = [capped(lad, l.limit, l.contracts) for lad, l in zip(fresh, arb.legs)]
    fillable = int(min(sum(q for _, q in c) for c in caps) + 1e-9)
    profit = None
    if fillable >= 1:
        walkers = [Walker(c, l.fee_rate) for c, l in zip(caps, arb.legs)]
        for _ in range(fillable):
            for w in walkers:
                w.add_one()
        profit = round(fillable - sum(w.spend + w.fee for w in walkers), 2)
    again = optimise(fresh[0], arb.legs[0].fee_rate, fresh[1], arb.legs[1].fee_rate, budget) \
        if fresh[0] and fresh[1] else None
    still = round(again["profit"] / again["outlay"] * 100, 3) if again and again["profit"] > 0 else None
    return {"fillable_n": fillable, "profit_if_placed": profit, "still_arb_pct": still}


def _append(path: str, row: dict) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def paper(args, fees: Dict[str, float], games: List[str], series, aliases, http_factory=None) -> int:
    """Scan on a timer, log every arb, and recheck each one after a delay. Never trades."""
    http_factory = http_factory or Http
    interval = args.watch or 60
    stop_after = (args.minutes or 0) * 60 + (args.hours or 0) * 3600
    started = time.monotonic()
    scans = 0
    while True:
        t_scan = time.monotonic()
        http = http_factory()
        stamp = datetime.now(timezone.utc).isoformat()
        row: dict = {"type": "scan", "t": stamp}
        arbs: List[EsArb] = []
        try:
            arbs, stats, disc, _ = scan(http, games, series, aliases, fees, args.budget, args.min_profit,
                                        pages=args.pmus_pages)
            row.update(pairs=stats.pairs, arbs=len(arbs), gross_only=stats.gross_only,
                       empty_books=stats.empty_books, not_open=stats.not_open,
                       kalshi_markets=sum(len(v) for v in disc.kalshi.values()),
                       pmus_markets=len(disc.pmus), notes=disc.notes[:5])
        except VenueError as e:
            row["error"] = str(e)
        row["calls"] = http.calls
        _append(args.paper_log, row)
        for a in arbs:
            _append(args.paper_log, dict(type="seen", t=stamp, op=a.op_id, **a.to_dict()))
        if arbs and args.recheck > 0:
            time.sleep(args.recheck)
            for a in arbs:
                try:
                    res = recheck(http, a, fees, args.budget)
                except VenueError as e:
                    res = {"error": str(e), "fillable_n": 0, "profit_if_placed": None, "still_arb_pct": None}
                _append(args.paper_log, dict(type="recheck", t=datetime.now(timezone.utc).isoformat(), op=a.op_id,
                                             delay_s=args.recheck, planned_n=a.legs[0].contracts,
                                             planned_profit=a.profit, **res))
        scans += 1
        status = f"error: {row['error']}" if "error" in row else \
            f"{row['pairs']} on both venues, {len(arbs)} arb"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] paper scan {scans}: {status}", flush=True)
        if stop_after and time.monotonic() - started + interval > stop_after:
            break
        if getattr(args, "max_scans", None) and scans >= args.max_scans:
            break
        time.sleep(max(0.0, interval - (time.monotonic() - t_scan)))
    print(f"Log: {args.paper_log}. Summary: python arbscan.py --report {args.paper_log}")
    return 0


def _episodes(times: List[datetime], max_gap: float) -> List[Tuple[datetime, datetime]]:
    """Group sightings into continuous runs; a gap longer than max_gap starts a new one."""
    eps: List[Tuple[datetime, datetime]] = []
    for t in sorted(times):
        if eps and (t - eps[-1][1]).total_seconds() <= max_gap:
            eps[-1] = (eps[-1][0], t)
        else:
            eps.append((t, t))
    return eps


def report(path: str) -> str:
    """Plain-English summary of a paper-trading log."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    scans = [r for r in rows if r.get("type") == "scan"]
    if not scans:
        return "No scans in this log yet."
    times = sorted(t for t in (parse_iso(r.get("t")) for r in scans) if t)
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    typical = sorted(gaps)[len(gaps) // 2] if gaps else 60.0
    max_gap = 3 * typical
    watched = sum(g for g in gaps if g <= max_gap) + typical       # seconds actually being watched
    hours = watched / 3600
    ok = [r for r in scans if not r.get("error")]
    errors = [r["error"] for r in scans if r.get("error")]
    avg_pairs = sum(r.get("pairs", 0) for r in ok) / len(ok) if ok else 0.0

    sightings: Dict[str, List[datetime]] = defaultdict(list)
    game_of: Dict[str, str] = {}
    for r in rows:
        if r.get("type") == "seen" and parse_iso(r.get("t")):
            sightings[r["op"]].append(parse_iso(r["t"]))
            game_of[r["op"]] = r.get("game", "?")
    rechecks: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        if r.get("type") == "recheck" and parse_iso(r.get("t")):
            rechecks[r["op"]].append(r)

    # One "appearance" = an arb seen in consecutive scans. You'd only place it once per appearance,
    # so profit counts the first recheck of each appearance.
    appearances = []      # (game, lifetime_s, first recheck or None)
    for op, ts in sightings.items():
        checks = sorted(rechecks.get(op, []), key=lambda r: r["t"])
        for start, end in _episodes(ts, max_gap):
            first = next((c for c in checks
                          if start <= parse_iso(c["t"]) <= end + timedelta(seconds=max_gap)), None)
            appearances.append((game_of[op], (end - start).total_seconds(), first))

    checked = [c for _, _, c in appearances if c is not None]
    full = sum(1 for c in checked if c.get("fillable_n", 0) >= c.get("planned_n", 1))
    part = sum(1 for c in checked if 0 < c.get("fillable_n", 0) < c.get("planned_n", 1))
    gone = len(checked) - full - part
    realised = sum((c.get("profit_if_placed") or 0.0) for c in checked)
    enough = hours >= 6
    per_day = realised / (watched / 86400) if enough else None
    games = defaultdict(int)
    for g, _, _ in appearances:
        games[g] += 1

    out = [f"# Paper test: {times[0]:%b %d %H:%M} to {times[-1]:%b %d %H:%M} UTC", "",
           f"- Watched for about **{hours:.1f} hours** ({len(scans)} scans, one every ~{typical:.0f}s"
           + (f"; {len(errors)} failed" if errors else "") + ").",
           f"- Matches listed on both venues per scan: **{avg_pairs:.1f}** on average."]
    if ok:
        out.append(f"- Markets seen per scan: Kalshi {sum(r.get('kalshi_markets', 0) for r in ok) / len(ok):.0f}, "
                   f"Polymarket US {sum(r.get('pmus_markets', 0) for r in ok) / len(ok):.0f}.")
    out.append(f"- Arbs: **{len(appearances)}** appearances across **{len(sightings)}** matches"
               + (f" ({', '.join(f'{g} {n}' for g, n in sorted(games.items()))})" if games else "") + ".")
    if checked:
        delay = checked[0].get("delay_s", "?")
        out.append(f"- Checked again {delay:g}s later (your reaction time): fully fillable **{full}**, "
                   f"partly **{part}**, gone **{gone}**.")
        line = f"- Profit if you'd placed every one {delay:g}s after it appeared: **${realised:,.2f}**"
        line += f", about **${per_day:,.2f} per day watched**." if enough else \
            " (too little data to estimate a daily figure)."
        out.append(line)
    if appearances:
        lt = sorted(l for _, l, _ in appearances)
        single = sum(1 for l in lt if l == 0)
        out.append(f"- How long they lasted: median {lt[len(lt) // 2]:.0f}s, longest {lt[-1]:.0f}s; "
                   f"{single} of {len(lt)} gone by the next scan.")
    if errors:
        common = max(set(errors), key=errors.count)
        out.append(f"- Most common error ({errors.count(common)}x): `{common}`")

    out.append("")
    if not ok:
        verdict = "Every scan failed, so this tells you nothing yet. See the error above."
    elif avg_pairs < 0.5:
        verdict = ("The scanner almost never found the same match on both venues, so there was nothing to "
                   "compare. Run `--probe` to see why (usually team names or a market format change).")
    elif not enough:
        verdict = (f"Too early to tell: only {hours:.1f} hours watched. Give it at least a day, ideally a "
                   f"week that includes a big tournament.")
    elif not appearances:
        verdict = f"No arbs in {hours:.0f} hours of watching. On this evidence it isn't worth running live."
    elif per_day < 1:
        verdict = (f"Arbs exist but are tiny: about ${per_day:.2f} a day after fees, even if you placed every "
                   f"one in time. Not worth your time at this budget.")
    elif per_day < 10:
        verdict = (f"Small but real: about ${per_day:.2f} a day, if you catch each one within "
                   f"{checked[0].get('delay_s', 20):g}s. Only worth it if you'd be watching anyway.")
    else:
        verdict = (f"Promising: about ${per_day:.2f} a day if you catch them in time. Watch for longer before "
                   f"trusting it, and start with small stakes.")
    out.append(f"**Verdict:** {verdict}")
    out.append("")
    out.append("Assumes both limit orders fill together at the slip prices. In practice you place one leg "
               "after the other, so real results will be a bit worse. Arbs that appear between scans "
               "aren't counted.")
    return "\n".join(out)


# --------------------------------------------------------------------------- CLI entry (called from arbscan.py)

def _parse_series(items: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for item in items:
        game, _, tickers = item.partition("=")
        game = game.strip().lower()
        if game not in GAMES or not tickers:
            raise ValueError(f"--kalshi-series wants GAME=TICKER[,TICKER], GAME one of {', '.join(GAMES)}")
        out[game] = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    return out


def run(args, fees: Dict[str, float]) -> int:
    fees = dict(fees, pm_override=any(f.split("=")[0].strip() == "polymarket_us" for f in (args.fee or [])))
    games = [g.strip().lower() for g in (args.games or ",".join(GAMES)).split(",") if g.strip()]
    bad = [g for g in games if g not in GAMES]
    if bad:
        print(f"Unknown game(s): {', '.join(bad)}. Choose from {', '.join(GAMES)}.", file=sys.stderr)
        return 2
    try:
        series = _parse_series(args.kalshi_series or [])
        aliases = load_aliases(args.aliases)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(e, file=sys.stderr)
        return 2

    replay = None
    if args.demo or args.from_file:
        path = args.from_file or os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_esports.json")
        try:
            with open(path, encoding="utf-8") as f:
                replay = json.load(f).get("responses", {})
        except (OSError, json.JSONDecodeError) as e:
            print(f"Couldn't read {path}: {e}", file=sys.stderr)
            return 1
    source = "demo data" if args.demo else (os.path.basename(args.from_file) if args.from_file else "live")

    if args.paper:
        if replay is not None:
            return paper(args, fees, games, series, aliases, http_factory=lambda: Http(replay=replay))
        return paper(args, fees, games, series, aliases)

    seen: set = set()
    while True:
        record = {} if args.save and replay is None else None
        http = Http(replay=replay, record=record)
        try:
            arbs, stats, disc, (un_k, un_p, ambiguous) = scan(
                http, games, series, aliases, fees, args.budget, args.min_profit, pages=args.pmus_pages)
        except VenueError as e:
            print(e, file=sys.stderr)
            if not args.watch or replay is not None:
                return 1
            time.sleep(args.watch)
            continue
        if record is not None:
            with open(args.save, "w", encoding="utf-8") as f:
                json.dump({"recorded_at": datetime.now(timezone.utc).isoformat(), "responses": record}, f)

        if args.probe:
            print(probe_report(disc, games, series, un_k, un_p, ambiguous, stats.pairs))
            print(f"Order books read for {stats.books_checked} matched pair(s); "
                  f"{stats.empty_books} came back empty, {stats.not_open} not open for trading.")
        elif args.json:
            print(json.dumps({"scanned_at": datetime.now(timezone.utc).isoformat(), "source": source,
                              "stats": stats.__dict__, "opportunities": [a.to_dict() for a in arbs]}, indent=2))
        else:
            fresh = [a for a in arbs if a.key() not in seen] if args.watch else arbs
            for a in fresh:
                print(render(a))
            if fresh:
                print("=" * 78)
                print(FOOTER)
                if args.beep:
                    print("\a", end="")
            kal = sum(len(v) for v in disc.kalshi.values())
            parts = [f"{kal} Kalshi + {len(disc.pmus)} Polymarket US esports markets",
                     f"{stats.pairs} on both", f"{len(arbs)} arb"]
            if stats.gross_only:
                parts.append(f"{stats.gross_only} gross-only (fees/depth ate them)")
            if stats.not_open:
                parts.append(f"{stats.not_open} not open for trading")
            if stats.empty_books:
                parts.append(f"{stats.empty_books} with an empty order book (run --probe if this is all of them)")
            if replay is None:
                parts.append(f"{http.calls} API calls")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {source}: " + ", ".join(parts))
            if disc.notes and not args.watch:
                for n in disc.notes:
                    print(f"note: {n}", file=sys.stderr)

        if args.log and arbs:
            new = [a for a in arbs if a.key() not in seen]
            if new:
                exists = os.path.exists(args.log)
                with open(args.log, "a", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    if not exists:
                        w.writerow(["seen_at", "game", "event", "pct", "outlay", "profit", "legs"])
                    for a in new:
                        w.writerow([datetime.now(timezone.utc).isoformat(), GAMES[a.game]["name"], a.title,
                                    f"{a.pct:.3f}", a.outlay, a.profit,
                                    " | ".join(f"{VENUE_NAMES[l.venue]}: {l.contract} {l.contracts}@{cents(l.limit)}"
                                               for l in a.legs)])
        seen |= {a.key() for a in arbs}

        if not args.watch or replay is not None:
            return 0
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            return 0
