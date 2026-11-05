"""Map-veto backtest: does knowing the maps beat Kalshi's price? (Valorant)

Read-only. Uses public data only: Kalshi's settled match markets and 1-minute
price candles, and vlr.gg (through the vlrdevapi package) for each match's map
veto and each team's map record before the match.

For every settled Kalshi Valorant match that can be found on vlr.gg:
  1. "pre"   = Kalshi price an hour before the scheduled start (usually before
               the veto is public).
  2. "model" = the pre price adjusted for the picked maps, using each team's map
               win rates over the previous 120 days (shrunk toward the team's
               overall rate, so a 2-0 record on a map does not count as 100%).
  3. "post"  = Kalshi price 10 minutes after the scheduled start (veto public,
               first map at most a few rounds in).
Then it asks:
  - Do map records carry information at all? (model beats pre)
  - Does the market move the way the map records say, before the match?
  - Is anything left after the market has moved? (model beats post, and
    betting the gap would have made money after Kalshi's fee)

    python veto_backtest.py --collect --since 2026-06-01      # fetch (cached)
    python veto_backtest.py --report                           # analyse cache
"""
from __future__ import annotations

import argparse
import bisect
import functools
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from esports import TEAM_FILLER, team_key

ET = ZoneInfo("America/New_York")
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXVALORANTGAME"
PRE_MIN = -60          # minutes from scheduled start
POST_MIN = 10
POST_SENSITIVITY = (0, 10, 20)
CANDLE_WINDOW = (-120, 45)
RECORD_DAYS = 120
SHRINK = 5.0           # pseudo-maps pulling a map win rate toward the team's overall rate
MATCH_WINDOW_H = 18
KALSHI_FEE = 0.07


# --------------------------------------------------------------------------- time

def kalshi_start(event_ticker: str) -> Optional[datetime]:
    """KXVALORANTGAME-26SEP290500G2PR -> 2026-09-29 05:00 New York time, as UTC."""
    import re
    suffix = event_ticker.split("-", 1)[1] if "-" in event_ticker else ""
    m = re.match(r"(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?=[A-Z0-9])", suffix)
    if not m:
        return None
    try:
        day = datetime.strptime(f"{m.group(1)}{m.group(2).title()}{m.group(3)}", "%y%b%d")
        local = day.replace(hour=int(m.group(4)), minute=int(m.group(5)), tzinfo=ET)
    except ValueError:
        return None
    return local.astimezone(timezone.utc)


def kalshi_day(event_ticker: str) -> Optional[datetime]:
    """Older tickers carry only a date (KXVALORANTGAME-26APR02FUTGM): noon New York that day."""
    import re
    suffix = event_ticker.split("-", 1)[1] if "-" in event_ticker else ""
    m = re.match(r"(\d{2})([A-Z]{3})(\d{2})", suffix)
    if not m:
        return None
    try:
        day = datetime.strptime(f"{m.group(1)}{m.group(2).title()}{m.group(3)}", "%y%b%d")
    except ValueError:
        return None
    return day.replace(hour=12, tzinfo=ET).astimezone(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- Kalshi

def http_get(path: str, params: Dict, min_interval: float = 0.15) -> Optional[dict]:
    url = f"{KALSHI}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    for attempt in range(5):
        time.sleep(min_interval)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arbscan-veto-backtest"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 4:
                raise RuntimeError(f"{e} for {url}") from e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"gave up on {url}")


def kalshi_markets(get: Callable = http_get, series: str = SERIES) -> List[dict]:
    """Settled markets from the live tier (via events) and the archive tier."""
    out: Dict[str, dict] = {}
    cursor = None
    while True:
        d = get("/events", {"series_ticker": series, "status": "settled", "with_nested_markets": "true",
                            "limit": 200, "cursor": cursor}) or {}
        for e in d.get("events") or []:
            for m in e.get("markets") or []:
                out[m["ticker"]] = dict(_slim_market(m), tier="live")
        cursor = d.get("cursor")
        if not cursor:
            break
    cursor = None
    while True:
        d = get("/historical/markets", {"series_ticker": series, "limit": 1000, "cursor": cursor}) or {}
        for m in d.get("markets") or []:
            out.setdefault(m["ticker"], dict(_slim_market(m), tier="historical"))
        cursor = d.get("cursor")
        if not cursor:
            break
    return list(out.values())


def _slim_market(m: dict) -> dict:
    vol = m.get("volume_fp", m.get("volume"))
    try:
        vol = float(vol or 0)
    except (TypeError, ValueError):
        vol = 0.0
    return {"ticker": m.get("ticker"), "event": m.get("event_ticker"), "team": m.get("yes_sub_title") or "",
            "result": (m.get("result") or "").lower(), "volume": vol}


def kalshi_matches(markets: List[dict]) -> Tuple[List[dict], Dict[str, int]]:
    """One row per settled two-team match. Team A is the first market by ticker."""
    by_event: Dict[str, List[dict]] = {}
    for m in markets:
        if m.get("event"):
            by_event.setdefault(m["event"], []).append(m)
    rows, skipped = [], {}
    for ev, ms in by_event.items():
        ms = sorted(ms, key=lambda m: m["ticker"])
        start, kind = kalshi_start(ev), "time"
        if start is None:
            start, kind = kalshi_day(ev), "date"
        why = None
        if len(ms) != 2:
            why = "not two markets"
        elif sorted(m["result"] for m in ms) != ["no", "yes"]:
            why = "not settled yes/no"
        elif start is None:
            why = "no date in ticker"
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        a, b = ms
        rows.append({"event": ev, "start": iso(start), "kind": kind, "team_a": a["team"], "team_b": b["team"],
                     "ticker_a": a["ticker"], "a_won": a["result"] == "yes", "tier": a["tier"],
                     "volume": a["volume"] + b["volume"]})
    rows.sort(key=lambda r: r["start"], reverse=True)
    return rows, skipped


def kalshi_candles(get: Callable, ticker: str, tier: str, t0: datetime, series: str = SERIES) -> List[list]:
    start = int((t0 + timedelta(minutes=CANDLE_WINDOW[0])).timestamp())
    end = int((t0 + timedelta(minutes=CANDLE_WINDOW[1])).timestamp())
    params = {"start_ts": start, "end_ts": end, "period_interval": 1}
    path = (f"/historical/markets/{ticker}/candlesticks" if tier == "historical"
            else f"/series/{series}/markets/{ticker}/candlesticks")
    d = get(path, params) or {}
    return [c for c in (compact_candle(x) for x in d.get("candlesticks") or []) if c]


def _px(d: Optional[dict], key: str = "close") -> Optional[float]:
    """Kalshi prices come as "0.5500" strings (…_dollars) or as cents."""
    if not isinstance(d, dict):
        return None
    v = d.get(f"{key}_dollars")
    if v not in (None, ""):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    v = d.get(key)
    if v in (None, ""):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 100 if v > 1 else v


def compact_candle(c: dict) -> Optional[list]:
    ts = c.get("end_period_ts")
    if ts is None:
        return None
    return [int(ts), _px(c.get("yes_bid")), _px(c.get("yes_ask")), _px(c.get("price"))]


def quote_at(candles: List[list], when: datetime) -> Optional[dict]:
    """Latest candle that ended at or before `when`: bid, ask, last trade, mid."""
    ts = when.timestamp()
    best = None
    for c in candles:
        if c[0] <= ts and (best is None or c[0] > best[0]):
            best = c
    if best is None:
        return None
    _, bid, ask, last = best
    bid = bid if bid and 0 < bid < 1 else None
    ask = ask if ask and 0 < ask < 1 else None
    if bid is not None and ask is not None and bid < ask and ask - bid <= 0.15:
        mid = (bid + ask) / 2
    elif last is not None and 0 < last < 1:
        mid = last
    else:
        return None
    return {"bid": bid, "ask": ask, "last": last, "mid": mid, "age_s": ts - best[0]}


# --------------------------------------------------------------------------- vlr.gg

@functools.lru_cache(maxsize=None)
def _key(name: str) -> str:
    return team_key(name)


def same_team(kalshi_name: str, vlr_name: str, vlr_tag: str = "", aliases: Optional[Dict] = None) -> bool:
    key = (lambda n: team_key(n, aliases)) if aliases else _key
    k = key(kalshi_name)
    kc = k.replace(" ", "")
    for v in (key(vlr_name), key(vlr_tag or "")):
        if v and (v == k or v.replace(" ", "") == kc):
            return True
    return False


@functools.lru_cache(maxsize=None)
def first_word(name: str) -> str:
    """First real word of a name: "MIBR Female" -> "mibr", "Team Liquid Brazil" -> "liquid"."""
    import unicodedata
    import re
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w not in TEAM_FILLER]
    return words[0] if words else ""


class ResultIndex:
    """vlr.gg results sorted by time, for quick lookups by date."""

    def __init__(self, results: List[dict]):
        pairs = sorted(((parse_iso(r["dt"]), r) for r in results if parse_iso(r.get("dt"))), key=lambda p: p[0])
        self.ts = [p[0].timestamp() for p in pairs]
        self.rows = [p[1] for p in pairs]

    def near(self, ts: float, window: float):
        i = bisect.bisect_left(self.ts, ts - window)
        while i < len(self.ts) and self.ts[i] <= ts + window:
            yield self.rows[i], self.ts[i]
            i += 1


def find_vlr(row: dict, results, aliases: Optional[Dict] = None) -> Tuple[Optional[dict], bool]:
    """The vlr.gg result for a Kalshi match. Returns (match, team_a_is_vlr_team1).

    Both teams the same name, start within 18 h (36 h when Kalshi gives only the
    date). Failing that, a looser rule for renamed sister teams ("MIBR Female" on
    Kalshi, "MIBR GC" on vlr.gg): within 4 h, each team either the same name or
    sharing its first word, and only one result fitting.
    """
    t0 = parse_iso(row["start"])
    window = (36 if row.get("kind") == "date" else MATCH_WINDOW_H) * 3600
    best, best_gap, flip = None, None, False
    loose = []
    index = results if isinstance(results, ResultIndex) else ResultIndex(results)
    for r, ts in index.near(t0.timestamp(), window):
        gap = abs(ts - t0.timestamp())
        if gap > window:
            continue
        a1, b2 = same_team(row["team_a"], r["n1"], r["g1"], aliases), same_team(row["team_b"], r["n2"], r["g2"], aliases)
        a2, b1 = same_team(row["team_a"], r["n2"], r["g2"], aliases), same_team(row["team_b"], r["n1"], r["g1"], aliases)
        if (a1 and b2) or (a2 and b1):
            if best_gap is None or gap < best_gap:
                best, best_gap, flip = r, gap, a1 and b2
            continue
        if gap > (window if row.get("kind") == "date" else 4 * 3600):
            continue
        fa, fb = first_word(row["team_a"]), first_word(row["team_b"])
        f1, f2 = first_word(r["n1"]), first_word(r["n2"])
        ok = lambda x, y: len(x) >= 3 and x == y  # noqa: E731
        straight = (a1 or ok(fa, f1)) and (b2 or ok(fb, f2))
        crossed = (a2 or ok(fa, f2)) and (b1 or ok(fb, f1))
        if straight != crossed:
            loose.append((r, straight))
    if best is not None:
        return best, flip
    if len(loose) == 1:
        return loose[0]
    return None, False


def match_t0(row: dict, info: Optional[dict], hit: dict) -> datetime:
    """Scheduled start: Kalshi's ticker time, or vlr.gg's when Kalshi gives only a date."""
    if row.get("kind") == "date":
        return parse_iso((info or {}).get("dt") or hit["dt"]) or parse_iso(row["start"])
    return parse_iso(row["start"])


def event_level(event_name: str) -> str:
    ev = (event_name or "").lower()
    lower = ("challengers", "game changers", "ascension", "threshold", "academy", "spike series")
    if any(x in ev for x in lower):
        return "lower"
    if any(x in ev for x in ("champions tour", "masters", "valorant champions")):
        return "top"
    return "lower"


def slim_result(m) -> Optional[dict]:
    d = m.model_dump(mode="json") if hasattr(m, "model_dump") else dict(m)
    t1, t2 = d.get("team1") or {}, d.get("team2") or {}
    if not d.get("match_id") or not d.get("datetime"):
        return None
    return {"id": d["match_id"], "dt": d["datetime"], "ev": d.get("event") or "",
            "n1": t1.get("name") or "", "g1": t1.get("tag") or "", "i1": t1.get("id") or 0,
            "n2": t2.get("name") or "", "g2": t2.get("tag") or "", "i2": t2.get("id") or 0}


def slim_info(s) -> dict:
    d = s.model_dump(mode="json") if hasattr(s, "model_dump") else dict(s)
    return {"dt": d.get("datetime"), "bo": d.get("best_of") or 0, "event": d.get("event_name") or "",
            "t1": (d.get("team1") or {}).get("id") or 0, "t2": (d.get("team2") or {}).get("id") or 0,
            "n1": (d.get("team1") or {}).get("name") or "", "n2": (d.get("team2") or {}).get("name") or "",
            "s1": d.get("score1"), "s2": d.get("score2"),
            "forfeit": bool((d.get("forfeit") or {}).get("forfeited")),
            "veto": [[v.get("veto_type", ""), v.get("map_name", ""), v.get("team", "")] for v in d.get("veto") or []],
            "g1": (d.get("team1") or {}).get("tag") or "", "g2": (d.get("team2") or {}).get("tag") or "",
            "stage": d.get("stage") or "", "bracket": d.get("bracket") or "", "patch": d.get("patch") or "",
            # [map, played, team1 rounds, team2 rounds, picked by (tag)]
            "games": [[g.get("map_name", ""), g.get("played", True), g.get("team1_score"), g.get("team2_score"),
                       g.get("picked_by") or ""] for g in d.get("games") or []]}


def slim_stats(st) -> Dict[str, List[int]]:
    d = st.model_dump(mode="json") if hasattr(st, "model_dump") else dict(st)
    out = {}
    for m in d.get("maps") or []:
        name = (m.get("map_name") or "").strip().lower()
        w, l = m.get("wins"), m.get("losses")
        if not name or name in ("all maps", "all"):
            continue
        if w is None or l is None:
            n = m.get("games_played") or 0
            wr = m.get("win_rate")
            if not n or wr is None:
                continue
            w = round(n * wr / 100)
            l = n - w
        out[name] = [int(w), int(l)]
    return out


# --------------------------------------------------------------------------- model

def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    e = math.exp(x)
    return e / (1 + e)


def series_prob(qs: List[float], best_of: int) -> float:
    """Chance team A wins a best-of-N given its chance on each map, in order."""
    need = best_of // 2 + 1
    states = {(0, 0): 1.0}
    won = 0.0
    for q in qs[:best_of]:
        nxt: Dict[Tuple[int, int], float] = {}
        for (a, b), p in states.items():
            if a + 1 == need:
                won += p * q
            else:
                nxt[(a + 1, b)] = nxt.get((a + 1, b), 0) + p * q
            if b + 1 < need:
                nxt[(a, b + 1)] = nxt.get((a, b + 1), 0) + p * (1 - q)
        states = nxt
    return won


def base_map_prob(p_series: float, best_of: int) -> float:
    """Per-map chance that, repeated on every map, gives the series price."""
    lo, hi = 1e-4, 1 - 1e-4
    for _ in range(60):
        mid = (lo + hi) / 2
        if series_prob([mid] * best_of, best_of) < p_series:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def map_advantage(record: Dict[str, List[int]], map_name: str, shrink: float = SHRINK) -> float:
    """How much better (in log-odds) the team does on this map than on its maps overall."""
    w_all = sum(v[0] for v in record.values())
    n_all = sum(v[0] + v[1] for v in record.values())
    wr_all = (w_all + 1) / (n_all + 2)
    w, l = record.get(map_name.strip().lower(), [0, 0])
    wr_map = (w + shrink * wr_all) / (w + l + shrink)
    return logit(wr_map) - logit(wr_all)


def series_maps(info: dict) -> Optional[List[str]]:
    """Maps in play order from the veto (picks and decider). Never uses which maps
    were actually played, since a short series would leak the result."""
    bo = info.get("bo") or 0
    maps = [m for kind, m, _ in info.get("veto") or [] if kind.lower() in ("pick", "decider") and m]
    if any(m.strip().lower() in ("n/a", "tbd", "") for m in maps[: bo or len(maps)]):
        maps = []
    if not bo and len(maps) in (1, 3, 5):
        bo = len(maps)
    if bo and len(maps) >= bo:
        return maps[:bo]
    games = [g[0] for g in info.get("games") or [] if g[0]]
    if bo and len(games) == bo and not any(g.strip().lower() in ("n/a", "tbd") for g in games):
        return games
    return None


def model_prob(p_pre: float, maps: List[str], rec_a: Dict, rec_b: Dict, k: float = 1.0) -> float:
    bo = len(maps)
    base = logit(base_map_prob(p_pre, bo))
    qs = [sigmoid(base + k * (map_advantage(rec_a, m) - map_advantage(rec_b, m))) for m in maps]
    return series_prob(qs, bo)


# --------------------------------------------------------------------------- statistics

def log_loss(ps: List[float], ys: List[int]) -> float:
    return -sum(math.log(min(max(p if y else 1 - p, 1e-6), 1)) for p, y in zip(ps, ys)) / len(ys)


def brier(ps: List[float], ys: List[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)


def fit_offset_logit(ys: List[int], offsets: List[float], xs: List[float]) -> Tuple[float, float]:
    """Fit P(y) = sigmoid(offset + beta*x). beta > 0 means x adds information."""
    beta, h = 0.0, 0.0
    for _ in range(100):
        g = h = 0.0
        for y, o, x in zip(ys, offsets, xs):
            p = sigmoid(o + beta * x)
            g += (y - p) * x
            h += p * (1 - p) * x * x
        if h <= 0:
            return 0.0, float("inf")
        step = g / h
        beta += step
        if abs(step) < 1e-10:
            break
    return beta, 1 / math.sqrt(h) if h > 0 else float("inf")


def bootstrap_mean_ci(vals: List[float], n: int = 2000, seed: int = 7, lo: float = 0.05, hi: float = 0.95):
    if not vals:
        return None, None
    rnd = random.Random(seed)
    means = sorted(sum(rnd.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return means[int(lo * n)], means[int(hi * n) - 1]


def taker_fee(price: float, contracts: int = 100) -> float:
    return math.ceil(round(KALSHI_FEE * contracts * price * (1 - price) * 100, 6)) / 100 / contracts


def simulate_bets(rows: List[dict], threshold: float, post_key: str = "post") -> List[dict]:
    """Bet the side the map model likes at the post-veto ask, if the gap is big enough."""
    bets = []
    for r in rows:
        q = r.get(post_key + "_q")
        if not q:
            continue
        p = r["model"]
        if q.get("ask") is not None and p - q["ask"] >= threshold:
            price, won = q["ask"], r["y"] == 1
        elif q.get("bid") is not None and q["bid"] - p >= threshold:
            price, won = 1 - q["bid"], r["y"] == 0
        else:
            continue
        cost = price + taker_fee(price)
        bets.append({"event": r["event"], "price": price, "won": won, "ret": ((1.0 if won else 0.0) - cost) / cost})
    return bets


# --------------------------------------------------------------------------- collect

class Cache:
    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.data = {}
        for name in ("kalshi", "candles", "vlr_results", "vlr_info", "vlr_stats"):
            path = os.path.join(folder, f"{name}.json")
            try:
                with open(path, encoding="utf-8") as f:
                    self.data[name] = json.load(f)
            except (OSError, ValueError):
                self.data[name] = {}

    def __getitem__(self, k):
        return self.data[k]

    def save(self):
        for name, val in self.data.items():
            tmp = os.path.join(self.folder, f"{name}.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(val, f, separators=(",", ":"), sort_keys=True)
            os.replace(tmp, os.path.join(self.folder, f"{name}.json"))


def collect(args, cache: Cache, get: Callable = http_get, vlr=None, log=print) -> None:
    deadline = time.time() + args.budget_minutes * 60
    since = parse_iso(args.since + "T00:00:00Z") if args.since else None

    if args.refresh_kalshi or not cache["kalshi"].get("markets"):
        log("Kalshi: listing settled matches …")
        cache["kalshi"]["markets"] = kalshi_markets(get)
        cache["kalshi"]["fetched"] = iso(datetime.now(timezone.utc))
        cache.save()
    rows, _ = kalshi_matches(cache["kalshi"]["markets"])
    if since:
        rows = [r for r in rows if parse_iso(r["start"]) >= since]
    if args.max_matches:
        rows = rows[: args.max_matches]
    log(f"Kalshi: {len(rows)} settled matches in range")
    if not rows:
        return

    if vlr is None:
        import vlrdevapi
        vlr = vlrdevapi.VLRClient(requests_per_second=args.vlr_rps, auto_detect_tz=True)

    # vlr.gg results pages, newest first, until older than the oldest Kalshi match.
    oldest = min(parse_iso(r["start"]) for r in rows) - timedelta(days=1)
    have = {r["id"]: r for r in cache["vlr_results"].get("rows", [])}
    covered_to = parse_iso(cache["vlr_results"].get("covered_to"))
    newest_needed = max(parse_iso(r["start"]) for r in rows)
    newest_have = max((parse_iso(r["dt"]) for r in have.values()), default=None)
    need_pages = covered_to is None or covered_to > oldest or newest_have is None or newest_have < newest_needed
    page = 1
    while need_pages and time.time() < deadline and page <= args.max_pages:
        try:
            res = vlr.matches.completed(page=page)
        except Exception as e:  # noqa: BLE001
            log(f"vlr results page {page}: {type(e).__name__}: {e}")
            break
        got = [x for x in (slim_result(m) for m in res.matches) if x]
        for x in got:
            have[x["id"]] = x
        page_oldest = min((parse_iso(x["dt"]) for x in got), default=None)
        if page_oldest and (covered_to is None or page_oldest < covered_to):
            covered_to = page_oldest
        if page % 10 == 0:
            log(f"vlr results: page {page}, back to {iso(page_oldest)}")
        if not got or not res.has_next_page or (page_oldest and page_oldest < oldest):
            break
        page += 1
    cache["vlr_results"]["rows"] = sorted(have.values(), key=lambda r: r["dt"], reverse=True)
    cache["vlr_results"]["covered_to"] = iso(covered_to)
    cache.save()
    results = ResultIndex(cache["vlr_results"]["rows"])
    log(f"vlr results: {len(results.rows)} matches cached, back to {iso(covered_to)}")

    aliases = load_alias_file(args.aliases)
    done = 0
    for r in rows:
        if time.time() > deadline:
            log("time budget used up; the next run continues from the cache")
            break
        hit, _ = find_vlr(r, results, aliases)
        if not hit:
            continue
        key = str(hit["id"])
        try:
            cached = cache["vlr_info"].get(key)
            # Older cache entries lack per-map scores: fetch those again.
            if cached is None or "g1" not in cached:
                cache["vlr_info"][key] = slim_info(vlr.series.info(series_id=hit["id"]))
            info = cache["vlr_info"][key]
            t0 = match_t0(r, info, hit)
            end = (t0 - timedelta(days=1)).date()
            for tid in (info.get("t1"), info.get("t2")):
                skey = f"{tid}|{end.isoformat()}"
                if tid and skey not in cache["vlr_stats"]:
                    st = vlr.team.stats(team_id=tid, date_start=end - timedelta(days=RECORD_DAYS), date_end=end)
                    cache["vlr_stats"][skey] = slim_stats(st)
            if r["ticker_a"] not in cache["candles"]:
                cache["candles"][r["ticker_a"]] = kalshi_candles(get, r["ticker_a"], r["tier"], t0)
        except Exception as e:  # noqa: BLE001
            log(f"{r['event']}: {type(e).__name__}: {e}")
            continue
        done += 1
        if done % 25 == 0:
            cache.save()
            log(f"fetched details for {done} matches")
    cache.save()
    log(f"details fetched for {done} matches this run")


def load_alias_file(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    from esports import load_aliases
    return load_aliases(path)


# --------------------------------------------------------------------------- analyse

def build_rows(cache: Cache, since: Optional[str] = None, aliases: Optional[Dict] = None):
    rows, skipped = kalshi_matches(cache["kalshi"].get("markets", []))
    if since:
        lo = parse_iso(since + "T00:00:00Z")
        rows = [r for r in rows if parse_iso(r["start"]) >= lo]
    results = ResultIndex(cache["vlr_results"].get("rows", []))
    funnel = {"kalshi matches": len(rows)}
    reasons: Dict[str, int] = dict(skipped)
    out, offsets_min, unmatched = [], [], []

    def drop(why):
        reasons[why] = reasons.get(why, 0) + 1

    for r in rows:
        hit, a_is_1 = find_vlr(r, results, aliases)
        if not hit:
            drop("not found on vlr.gg")
            if len(unmatched) < 15:
                unmatched.append(f"{r['start'][:16]} {r['team_a']} vs {r['team_b']}")
            continue
        info = cache["vlr_info"].get(str(hit["id"]))
        if not info:
            drop("vlr details not fetched yet")
            continue
        if info.get("forfeit"):
            drop("forfeit")
            continue
        maps = series_maps(info)
        if not maps:
            drop("no veto on vlr.gg")
            continue
        t0 = match_t0(r, info, hit)
        vdt = parse_iso(info.get("dt") or hit["dt"])
        if vdt and r.get("kind") != "date":
            offsets_min.append((vdt - t0).total_seconds() / 60)
        end = (t0 - timedelta(days=1)).date().isoformat()
        tid_a, tid_b = (info["t1"], info["t2"]) if a_is_1 else (info["t2"], info["t1"])
        rec_a = cache["vlr_stats"].get(f"{tid_a}|{end}")
        rec_b = cache["vlr_stats"].get(f"{tid_b}|{end}")
        if rec_a is None or rec_b is None:
            drop("map records not fetched yet")
            continue
        candles = cache["candles"].get(r["ticker_a"])
        if candles is None:
            drop("prices not fetched yet")
            continue
        pre = quote_at(candles, t0 + timedelta(minutes=PRE_MIN))
        if not pre:
            drop("no Kalshi price an hour before")
            continue
        row = dict(r, vlr_id=hit["id"], maps=maps, y=1 if r["a_won"] else 0, pre=pre["mid"],
                   pre_spread=(pre["ask"] - pre["bid"]) if pre["ask"] is not None and pre["bid"] is not None else None,
                   maps_a=sum(w + l for w, l in rec_a.values()), maps_b=sum(w + l for w, l in rec_b.values()),
                   level=event_level(info.get("event") or hit.get("ev") or ""),
                   event_name=info.get("event") or hit.get("ev") or "")
        row["model"] = model_prob(pre["mid"], maps, rec_a, rec_b)
        for m in POST_SENSITIVITY:
            q = quote_at(candles, t0 + timedelta(minutes=m))
            # A quote older than the pre checkpoint says nothing new.
            if q and q["age_s"] > (m - PRE_MIN) * 60:
                q = None
            row[f"post{m}_q"] = q
        row["post_q"] = row[f"post{POST_MIN}_q"]
        row["post"] = row["post_q"]["mid"] if row["post_q"] else None
        out.append(row)
    funnel["used (pre price, veto, map records)"] = len(out)
    funnel["with a post-veto price"] = sum(1 for r in out if r["post"] is not None)
    return out, funnel, reasons, offsets_min, unmatched


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def analyse(rows: List[dict]) -> dict:
    res: dict = {"n": len(rows)}
    both = [r for r in rows if r["post"] is not None]
    res["n_post"] = len(both)
    if not both:
        return res
    ys = [r["y"] for r in both]
    res["scores"] = {name: (log_loss([r[k] for r in both], ys), brier([r[k] for r in both], ys))
                     for name, k in (("Kalshi, 1 h before", "pre"), ("Map model (1 h price + maps)", "model"),
                                     (f"Kalshi, {POST_MIN} min after start", "post"))}
    shift = [logit(r["model"]) - logit(r["pre"]) for r in both]
    move = [logit(r["post"]) - logit(r["pre"]) for r in both]
    res["raw"] = fit_offset_logit(ys, [0.0] * len(ys), shift)
    res["info"] = fit_offset_logit(ys, [logit(r["pre"]) for r in both], shift)
    res["left"] = fit_offset_logit(ys, [logit(r["post"]) for r in both],
                                   [logit(r["model"]) - logit(r["post"]) for r in both])
    sx = sum(s * s for s in shift)
    res["slope"] = sum(s * m for s, m in zip(shift, move)) / sx if sx else 0.0
    big = [(s, m) for s, m in zip(shift, move) if abs(s) >= 0.2 and abs(m) > 1e-9]
    res["agree"] = (sum(1 for s, m in big if (s > 0) == (m > 0)), len(big))
    res["moved"] = sum(1 for m in move if abs(m) > 1e-9)
    res["bets"] = {}
    for thr in (0.03, 0.05, 0.10):
        bets = simulate_bets(both, thr)
        rets = [b["ret"] for b in bets]
        res["bets"][thr] = (len(bets), sum(b["won"] for b in bets), sum(rets) / len(rets) if rets else None,
                            bootstrap_mean_ci(rets))
    res["slices"] = {}
    spreads = sorted(r["pre_spread"] for r in both if r.get("pre_spread") is not None)
    cut = spreads[len(spreads) // 2] if spreads else 0.0
    # Liquidity is judged by the spread an hour before the start. Total volume would
    # leak the result: series that go the distance trade far more.
    for name, keep in (("Top tier (VCT leagues, Masters, Champions)", lambda r: r["level"] == "top"),
                       ("Everything else", lambda r: r["level"] != "top"),
                       (f"Tighter markets (spread ≤ {cut * 100:.0f}¢ an hour before)",
                        lambda r: r.get("pre_spread") is not None and r["pre_spread"] <= cut + 1e-9),
                       (f"Wider markets (spread > {cut * 100:.0f}¢ an hour before)",
                        lambda r: r.get("pre_spread") is not None and r["pre_spread"] > cut + 1e-9)):
        sub = [r for r in both if keep(r)]
        if len(sub) < 20:
            res["slices"][name] = (len(sub), None, None, 0, None)
            continue
        b, se = fit_offset_logit([r["y"] for r in sub], [logit(r["post"]) for r in sub],
                                 [logit(r["model"]) - logit(r["post"]) for r in sub])
        bets = simulate_bets(sub, 0.05)
        rets = [x["ret"] for x in bets]
        res["slices"][name] = (len(sub), b, se, len(bets), sum(rets) / len(rets) if rets else None)
    res["sens"] = {}
    for m in POST_SENSITIVITY:
        sub = [r for r in rows if r.get(f"post{m}_q")]
        if len(sub) < 10:
            continue
        b, se = fit_offset_logit([r["y"] for r in sub], [logit(r[f"post{m}_q"]["mid"]) for r in sub],
                                 [logit(r["model"]) - logit(r[f"post{m}_q"]["mid"]) for r in sub])
        bets = simulate_bets(sub, 0.05, post_key=f"post{m}")
        rets = [x["ret"] for x in bets]
        res["sens"][m] = (len(sub), b, se, len(bets), sum(rets) / len(rets) if rets else None)
    return res


def verdict(res: dict) -> str:
    n = res.get("n_post", 0)
    if n < 100:
        return (f"Too few matches to judge ({n}; needs about 100 or more). Run the collector further back "
                f"(--since) and report again.")
    b_info, se_info = res["info"]
    b_left, se_left = res["left"]
    n5, _, roi5, (lo5, _) = res["bets"][0.05]
    info_real = se_info < float("inf") and b_info / se_info > 2
    left_real = se_left < float("inf") and b_left / se_left > 2
    if left_real and roi5 is not None and lo5 is not None and lo5 > 0 and n5 >= 30:
        return ("Possible edge: map records still predicted winners after Kalshi's post-veto price, and betting "
                "the gap made money after fees with the lower end of the range above zero. Worth a live "
                "paper test before any money.")
    if info_real:
        return ("Map records carry real information, but Kalshi's price had already absorbed it by "
                f"{POST_MIN} minutes after the start. No edge left at the speed this test checks.")
    raw_b, raw_se = res.get("raw", (0.0, float("inf")))
    if raw_se < float("inf") and raw_b / raw_se > 2:
        return ("No edge found: map records do say a little about who wins, but Kalshi's price an hour before "
                "the start already includes it, and betting the gap showed no reliable profit after fees.")
    return ("No edge found: map records did not predict winners better than Kalshi's own price, even before "
            "the veto, and betting the gap showed no reliable profit after fees.")


def render(rows, funnel, reasons, offsets, unmatched, res) -> str:
    L = ["# Map-veto backtest (Valorant, Kalshi)", ""]
    L.append(f"Generated {iso(datetime.now(timezone.utc))}. Public data only; nothing was traded.")
    L.append("")
    L.append("## Verdict")
    L.append("")
    L.append(verdict(res))
    L.append("")
    L.append("## Data")
    L.append("")
    for k, v in funnel.items():
        L.append(f"- {k}: {v}")
    if rows:
        L.append(f"- dates: {min(r['start'] for r in rows)[:10]} to {max(r['start'] for r in rows)[:10]}")
        L.append(f"- top-tier matches (VCT leagues, Masters, Champions): {sum(1 for r in rows if r['level'] == 'top')}")
    if reasons:
        L.append("- left out: " + "; ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
    if offsets:
        s = sorted(offsets)
        L.append(f"- start time check, vlr.gg minus Kalshi: median {s[len(s) // 2]:+.0f} min "
                 f"(middle half {s[len(s) // 4]:+.0f} to {s[3 * len(s) // 4]:+.0f})")
    if unmatched:
        L.append("- examples not found on vlr.gg: " + "; ".join(unmatched[:8]))
    L.append("")
    if not res.get("n_post"):
        L.append("Not enough data yet.")
        return "\n".join(L) + "\n"
    L.append("## How well each predicted the winner")
    L.append("")
    L.append(f"Lower is better. {res['n_post']} matches with all three prices.")
    L.append("")
    L.append("| Prediction | Log loss | Brier |")
    L.append("|---|---|---|")
    for name, (ll, br) in res["scores"].items():
        L.append(f"| {name} | {ll:.4f} | {br:.4f} |")
    L.append("")
    bi, si = res["info"]
    bl, sl = res["left"]
    L.append("## Does the map information matter?")
    L.append("")
    br, sr = res["raw"]
    L.append(f"- Map records on their own, ignoring the price: weight {br:.2f} (± {sr:.2f}). Above 0 by more "
             "than twice the ± means they do say something about who wins.")
    L.append(f"- Beyond Kalshi's price an hour before: weight on the map model's adjustment {bi:.2f} (± {si:.2f}). "
             "Above 0 by more than twice the ± means map records add information to the pre-veto price; "
             "1.0 means the model's adjustment is the right size.")
    L.append(f"- After the market moved: weight on the gap between model and post price {bl:.2f} (± {sl:.2f}). "
             "Above 0 by more than twice the ± would mean the market under-reacts.")
    a, n = res["agree"]
    L.append(f"- Market moved between the two checkpoints in {res['moved']} of {res['n_post']} matches. "
             f"Where the model expected a move of 5+ points, the price moved its way in {a} of {n}"
             + (f" ({a / n:.0%})." if n else "."))
    L.append(f"- Size of the move compared with the model's: {res['slope']:.2f} (1.0 = moves as much as the model says).")
    L.append("")
    L.append(f"## Betting the gap at the post-veto price ({POST_MIN} min after start, Kalshi taker fee included)")
    L.append("")
    L.append("| Bet when model is this far from the price | Bets | Won | Avg return per $ | 90% range |")
    L.append("|---|---|---|---|---|")
    for thr, (nb, won, roi, (lo, hi)) in res["bets"].items():
        if nb:
            L.append(f"| {thr * 100:.0f}¢ | {nb} | {won} | {_pct(roi)} | {_pct(lo)} to {_pct(hi)} |")
        else:
            L.append(f"| {thr * 100:.0f}¢ | 0 | – | – | – |")
    L.append("")
    L.append("Assumes each bet fills at the quoted price. Small markets often have only a few dollars there, "
             "so real results would be worse for anything but small bets.")
    L.append("")
    if res.get("slices"):
        L.append("## Big matches versus small ones")
        L.append("")
        L.append("| Slice | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |")
        L.append("|---|---|---|---|---|")
        for name, (ns, b, se, nb, roi) in res["slices"].items():
            w = f"{b:.2f} (± {se:.2f})" if b is not None else "too few"
            L.append(f"| {name} | {ns} | {w} | {nb} | {_pct(roi) if roi is not None else '–'} |")
        L.append("")
    if res.get("sens"):
        L.append("## Sensitivity to the post checkpoint")
        L.append("")
        L.append("| Minutes after scheduled start | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |")
        L.append("|---|---|---|---|---|")
        for m, (ns, b, se, nb, roi) in sorted(res["sens"].items()):
            L.append(f"| {m:+d} | {ns} | {b:.2f} (± {se:.2f}) | {nb} | {_pct(roi) if roi is not None else '–'} |")
        L.append("")
    L.append("## Method and limits")
    L.append("")
    L.append(f"- Prices: Kalshi 1-minute candles for the first team's market; mid of bid and ask (spread ≤ 15¢), "
             f"else last trade. Pre = {-PRE_MIN} min before the scheduled start in the event ticker; "
             f"post = {POST_MIN} min after.")
    L.append(f"- Maps: picks and decider from the vlr.gg veto, in order. Map records: vlr.gg team stats for the "
             f"{RECORD_DAYS} days ending the day before the match, so nothing from the future leaks in.")
    L.append(f"- Model: the pre price turned into a per-map chance, then moved by each team's map win rate "
             f"relative to its overall rate (shrunk with {SHRINK:.0f} pseudo-maps). No settings were tuned on "
             f"this data.")
    L.append("- The exact time of each veto isn't recorded, so the checkpoints are fixed offsets from the "
             "scheduled start. A late start or an early veto blurs the before/after split.")
    L.append("- Results with fewer than a few hundred matches have wide ranges; treat a small positive return "
             "as noise unless the 90% range is above zero.")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--collect", action="store_true", help="fetch data into the cache")
    ap.add_argument("--report", action="store_true", help="analyse the cache and print the report")
    ap.add_argument("--data", default="data/backtest", help="cache folder")
    ap.add_argument("--since", default=None, help="only matches from this date (YYYY-MM-DD)")
    ap.add_argument("--max-matches", type=int, default=0, help="limit matches fetched (newest first)")
    ap.add_argument("--max-pages", type=int, default=2000, help="limit vlr.gg results pages")
    ap.add_argument("--budget-minutes", type=float, default=50, help="stop fetching after this long")
    ap.add_argument("--vlr-rps", type=float, default=2.0, help="vlr.gg requests per second")
    ap.add_argument("--refresh-kalshi", action="store_true", help="re-list Kalshi markets")
    ap.add_argument("--aliases", default="aliases.json", help="team name aliases (JSON)")
    ap.add_argument("--out", default=None, help="write the report here as well as printing it")
    args = ap.parse_args(argv)
    if not (args.collect or args.report):
        ap.error("choose --collect and/or --report")
    cache = Cache(args.data)
    if args.collect:
        collect(args, cache, log=lambda s: print(s, file=sys.stderr, flush=True))
    if args.report:
        rows, funnel, reasons, offsets, unmatched = build_rows(cache, args.since, load_alias_file(args.aliases))
        text = render(rows, funnel, reasons, offsets, unmatched, analyse(rows))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
