"""Build the esports research workbook (Excel) from the collected public data.

    python tools/build_workbook.py --out esports_research.xlsx

Reads data/backtest (Valorant: Kalshi candles + vlr.gg) and, when present,
data/dataset/<series>.json (CS2, LoL, Dota 2: Kalshi only). Derived columns and
every summary are Excel formulas, so filtering or changing the fee cell updates
them.
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import timedelta

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import veto_backtest as vb  # noqa: E402
from esports import team_key  # noqa: E402

FONT = "Arial"
GAMES = [("CS2", "KXCS2GAME"), ("LoL", "KXLOLGAME"), ("Dota 2", "KXDOTA2GAME")]
FIRST = 4                    # first data row in match sheets
START = "'Start here'"
FEE_CELL = f"{START}!$C$8"
CONTRACTS_CELL = f"{START}!$C$9"

SECTION_FILL = {"Match": "D9D9D9", "Prices": "DDEBF7", "Result": "E2EFDA", "Maps": "FCE4D6",
                "Model": "E4DFEC", "Betting": "FFF2CC", "Links": "EDEDED"}
PCT = "0.0%"
PTS = '+0.0%;-0.0%;0.0%'
RET = '+0.0%;-0.0%;0.0%'
THIN = Side(style="thin", color="BFBFBF")


# --------------------------------------------------------------------------- helpers

def region(event: str) -> str:
    ev = (event or "").lower()
    if vb.event_group(event) == "International":
        return "International"
    for key, name in (("americas", "Americas"), ("north america", "North America"), ("brazil", "Brazil"),
                      ("latam", "LATAM"), ("emea", "EMEA"), ("pacific", "Pacific"), ("china", "China"),
                      ("korea", "Korea"), ("japan", "Japan"), ("oceania", "Oceania"),
                      ("southeast asia", "Southeast Asia"), ("south asia", "South Asia")):
        if key in ev:
            return name
    for key in ("spain", "france", "dach", "türkiye", "turkiye", "italy", "portugal", "polska", "nordic",
                "northern europe", "east", "mena", "uk", "benelux", "project blender", "monsters"):
        if key in ev:
            return "EMEA"
    return "Other"


def orient(q, fav_is_a):
    """A quote for team A's market, seen from the favourite's side."""
    if not q:
        return None, None, None
    mid, bid, ask = q["mid"], q.get("bid"), q.get("ask")
    if not fav_is_a:
        mid, bid, ask = 1 - mid, (1 - ask) if ask is not None else None, (1 - bid) if bid is not None else None
    r4 = lambda x: None if x is None else round(x, 4)  # noqa: E731  (cents; avoids float fuzz at bucket edges)
    return r4(mid), r4(bid), r4(ask)


def fresh(q, minutes):
    """Drop a quote at/after the start if it is older than an hour before the start."""
    if q and minutes >= 0 and q["age_s"] > (minutes + 60) * 60:
        return None
    return q


def same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and team_key(a) == team_key(b)


def record_text(rec, m):
    if rec is None or not m:
        return None
    w, l = rec.get(m.strip().lower(), [0, 0])
    return f"{w}–{l}"


def overall_text(rec):
    if rec is None:
        return None
    return f"{sum(v[0] for v in rec.values())}–{sum(v[1] for v in rec.values())}"


# --------------------------------------------------------------------------- data

def valorant_rows(cache):
    rows_k, _ = vb.kalshi_matches(cache["kalshi"].get("markets", []))
    index = vb.ResultIndex(cache["vlr_results"].get("rows", []))
    out, maps_out = [], []
    for r in rows_k:
        hit, a_is_1 = vb.find_vlr(r, index)
        if not hit:
            continue
        info = cache["vlr_info"].get(str(hit["id"]))
        if not info or info.get("forfeit"):
            continue
        candles = cache["candles"].get(r["ticker_a"])
        if candles is None:
            continue
        t0 = vb.match_t0(r, info, hit)
        qa = {m: fresh(vb.quote_at(candles, t0 + timedelta(minutes=m)), m) for m in (-120, -60, -10, 10)}
        ref = qa[-10] or qa[-60]
        if not ref:
            continue
        fav_is_a = ref["mid"] >= 0.5
        n_a, n_b = (info["n1"], info["n2"]) if a_is_1 else (info["n2"], info["n1"])
        g_a, g_b = ((info.get("g1") or hit["g1"]), (info.get("g2") or hit["g2"]))
        if not a_is_1:
            g_a, g_b = g_b, g_a
        id_a, id_b = (info["t1"], info["t2"]) if a_is_1 else (info["t2"], info["t1"])
        s_a, s_b = (info.get("s1"), info.get("s2")) if a_is_1 else (info.get("s2"), info.get("s1"))
        fav, dog = (n_a, n_b) if fav_is_a else (n_b, n_a)
        fav_tag, dog_tag = (g_a, g_b) if fav_is_a else (g_b, g_a)
        s_f, s_d = (s_a, s_b) if fav_is_a else (s_b, s_a)
        fav_won = r["a_won"] == fav_is_a
        end = (t0 - timedelta(days=1)).date().isoformat()
        rec_a, rec_b = cache["vlr_stats"].get(f"{id_a}|{end}"), cache["vlr_stats"].get(f"{id_b}|{end}")
        rec_f, rec_d = (rec_a, rec_b) if fav_is_a else (rec_b, rec_a)
        maps = vb.series_maps(info) or []
        picker = {}
        for kind, m, team in info.get("veto") or []:
            if kind.lower() == "decider":
                picker[m] = "Decider"
            elif kind.lower() == "pick":
                t = (team or "").strip().lower()
                if t and t in ((info.get("g1") or "").lower(), (info.get("g2") or "").lower()):
                    is_team1 = t == (info.get("g1") or "").lower()
                    picker[m] = "Fav" if is_team1 == (a_is_1 == fav_is_a) else "Dog"
                else:
                    picker[m] = ("Fav" if same(team, fav_tag) or same(team, fav)
                                 else "Dog" if same(team, dog_tag) or same(team, dog) else team)
        # Where the veto text is missing, vlr.gg's per-map "picked by" tag fills in.
        for i, g in enumerate(info.get("games") or []):
            if len(g) < 5 or not g[0] or g[0] in picker:
                continue
            t = (g[4] or "").strip().lower()
            if t and t in ((info.get("g1") or "").lower(), (info.get("g2") or "").lower()):
                picker[g[0]] = "Fav" if (t == (info.get("g1") or "").lower()) == (a_is_1 == fav_is_a) else "Dog"
            elif not t and maps and g[0] == maps[-1] and len(maps) == (info.get("bo") or 0):
                picker[g[0]] = "Decider"
        model = None
        if maps and qa[-60] and rec_a is not None and rec_b is not None:
            p_a = vb.model_prob(qa[-60]["mid"], maps, rec_a, rec_b)
            model = round(p_a if fav_is_a else 1 - p_a, 4)
        local = t0.astimezone(vb.ET)
        row = {
            "date": local.replace(tzinfo=None, second=0, microsecond=0), "time": local.strftime("%H:%M"),
            "weekday": local.strftime("%a"), "fav": fav, "dog": dog, "event": info.get("event") or hit["ev"],
            "group": vb.event_group(info.get("event") or hit["ev"]), "region": region(info.get("event") or hit["ev"]),
            "stage": " – ".join(x for x in (info.get("stage"), info.get("bracket")) if x) or None,
            "bo": info.get("bo") or len(maps) or None, "patch": info.get("patch") or None,
            "won": 1 if fav_won else 0,
            "score": f"{s_f}–{s_d}" if s_f is not None and s_d is not None else None,
            "maps_played": (s_f or 0) + (s_d or 0) if s_f is not None else None,
            "volume": round(r["volume"]), "vlr": f"https://www.vlr.gg/{hit['id']}", "ticker": r["event"],
            "model": model, "fav_overall": overall_text(rec_f), "dog_overall": overall_text(rec_d),
        }
        for key, m in (("c2h", -120), ("c1h", -60), ("c10", -10), ("a10", 10)):
            row[key] = orient(qa[m], fav_is_a)[0]
        _, row["bid10"], row["ask10"] = orient(qa[-10], fav_is_a)
        row["distance"] = None if row["maps_played"] is None or not row["bo"] else (
            "Yes" if row["maps_played"] == row["bo"] else "No")
        games = {g[0]: g for g in info.get("games") or [] if len(g) >= 5}
        for i in range(3):
            m = maps[i] if i < len(maps) else None
            row[f"map{i + 1}"] = m
            row[f"pick{i + 1}"] = picker.get(m) if m else None
            row[f"frec{i + 1}"] = record_text(rec_f, m)
            row[f"drec{i + 1}"] = record_text(rec_d, m)
            g = games.get(m) if m else None
            row[f"res{i + 1}"] = None
            if g is not None:
                if not g[1] or g[2] is None or g[3] is None:
                    row[f"res{i + 1}"] = "not played"
                else:
                    sf, sd = (g[2], g[3]) if (a_is_1 == fav_is_a) else (g[3], g[2])
                    row[f"res{i + 1}"] = f"{'Fav' if sf > sd else 'Dog'} {max(sf, sd)}–{min(sf, sd)}"
        row["other_maps"] = ", ".join(maps[3:]) or None
        out.append(row)
        # One row per played map.
        for i, m in enumerate(maps):
            g = games.get(m)
            if g is None or not g[1] or g[2] is None or g[3] is None:
                continue
            sf, sd = (g[2], g[3]) if (a_is_1 == fav_is_a) else (g[3], g[2])
            pk = picker.get(m)
            maps_out.append({
                "date": row["date"], "event": row["event"], "group": row["group"], "map": m, "order": i + 1,
                "pick": pk if pk in ("Fav", "Dog", "Decider") else None, "fav": fav, "dog": dog,
                "c10": row["c10"], "fav_won_map": 1 if sf > sd else 0,
                "picker_won": (None if pk not in ("Fav", "Dog") else
                               1 if (pk == "Fav") == (sf > sd) else 0),
                "rf": sf, "rd": sd, "frec": record_text(rec_f, m), "drec": record_text(rec_d, m),
                "won": row["won"]})
    out.sort(key=lambda x: x["date"], reverse=True)
    maps_out.sort(key=lambda x: (x["date"], x["order"]), reverse=True)
    return out, maps_out


def kalshi_only_rows(path):
    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    out = []
    for ev, m in store.get("matches", {}).items():
        q = {}
        for off in (-120, -60, -30, -10, 0, 10):
            v = m["q"].get(str(off))
            q[off] = fresh({"bid": v[0], "ask": v[1], "last": v[2], "mid": v[3], "age_s": v[4]}, off) if v else None
        ref = q[-10] or q[-60]
        if not ref:
            continue
        fav_is_a = ref["mid"] >= 0.5
        t0 = vb.parse_iso(m["start"])
        local = t0.astimezone(vb.ET)
        row = {"date": local.replace(tzinfo=None), "time": local.strftime("%H:%M"), "weekday": local.strftime("%a"),
               "fav": m["team_a"] if fav_is_a else m["team_b"], "dog": m["team_b"] if fav_is_a else m["team_a"],
               "won": 1 if m["a_won"] == fav_is_a else 0, "volume": round(m["volume"]), "ticker": ev}
        for key, off in (("c2h", -120), ("c1h", -60), ("c30", -30), ("c10", -10), ("c0", 0), ("a10", 10)):
            row[key] = orient(q[off], fav_is_a)[0]
        _, row["bid10"], row["ask10"] = orient(q[-10], fav_is_a)
        out.append(row)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out, store


# --------------------------------------------------------------------------- sheet writing

def style_header(cell, fill):
    cell.font = Font(name=FONT, bold=True, size=10)
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    cell.border = Border(bottom=THIN, top=THIN, left=THIN, right=THIN)


class Col:
    def __init__(self, key, header, section, width=10, fmt=None, formula=None, note=None):
        self.key, self.header, self.section, self.width = key, header, section, width
        self.fmt, self.formula, self.note = fmt, formula, note
        self.letter = None


def write_matches(ws, cols, rows, summary_keys, title):
    """Row 1: live summary of the filtered rows. Row 2: sections. Row 3: headers."""
    for i, c in enumerate(cols, start=1):
        c.letter = get_column_letter(i)
    L = {c.key: c.letter for c in cols}
    last = FIRST + max(len(rows), 1) - 1
    # sections
    i = 0
    while i < len(cols):
        j = i
        while j + 1 < len(cols) and cols[j + 1].section == cols[i].section:
            j += 1
        cell = ws.cell(row=2, column=i + 1, value=cols[i].section)
        style_header(cell, SECTION_FILL[cols[i].section])
        if j > i:
            ws.merge_cells(start_row=2, start_column=i + 1, end_row=2, end_column=j + 1)
        i = j + 1
    for idx, c in enumerate(cols, start=1):
        cell = ws.cell(row=3, column=idx, value=c.header)
        style_header(cell, SECTION_FILL[c.section])
        ws.column_dimensions[c.letter].width = c.width
    ws.row_dimensions[3].height = 54
    # data
    for n, r in enumerate(rows):
        rr = FIRST + n
        for idx, c in enumerate(cols, start=1):
            if c.formula:
                v = c.formula(rr, L)
            else:
                v = r.get(c.key)
            cell = ws.cell(row=rr, column=idx, value=v)
            if c.fmt:
                cell.number_format = c.fmt
            if c.key == "vlr" and v:
                cell.value = "open"
                cell.hyperlink = v
                cell.font = Font(name=FONT, size=10, color="0563C1", underline="single")
    # live summary (SUBTOTAL ignores rows hidden by a filter)
    ws.cell(row=1, column=1, value=f"{title}: filter any column, this row updates →").font = Font(
        name=FONT, bold=True, size=10)
    a = L[cols[0].key]
    items = [("Matches shown", f"SUBTOTAL(103,{a}{FIRST}:{a}{last})", "0")] + summary_keys(L, last)
    place_summary(ws, items, [c.width for c in cols], start_col=4)
    ws.freeze_panes = ws.cell(row=FIRST, column=4)
    ws.auto_filter.ref = f"A3:{cols[-1].letter}{last}"
    # colour returns
    for c in cols:
        if c.key in ("ret_fav", "ret_dog", "edge_model"):
            rng = f"{c.letter}{FIRST}:{c.letter}{last}"
            ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"],
                                                          font=Font(color="006100")))
            ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"],
                                                          font=Font(color="9C0006")))
    return L, last


def place_summary(ws, items, widths, start_col):
    """Each item as one text cell ("Fav won: 66.0%"), spaced so the text has room."""
    col = start_col
    for label, formula, fmt in items:
        text_fmt = "0" if fmt == "0" else ("+0.0%;-0.0%;0.0%" if fmt == RET else "0.0%")
        cell = ws.cell(row=1, column=col, value=f'="{label}: "&TEXT({formula},"{text_fmt}")')
        cell.font = Font(name=FONT, bold=True, size=10, color="1F4E79")
        need = len(label) + 10
        room = 0
        while room < need and col <= len(widths):
            room += widths[col - 1]
            col += 1


def betting_cols():
    def fee_fav(r, L):
        a = f"{L['ask10']}{r}"
        return f'=IF({a}="","",ROUNDUP(ROUND({FEE_CELL}*{CONTRACTS_CELL}*{a}*(1-{a}),6),2)/{CONTRACTS_CELL})'

    def ret_fav(r, L):
        a, f, w = f"{L['ask10']}{r}", f"{L['fee_fav']}{r}", f"{L['won']}{r}"
        return f'=IF({a}="","",IF({w}=1,1,0)/({a}+{f})-1)'

    def fee_dog(r, L):
        b = f"{L['bid10']}{r}"
        return f'=IF({b}="","",ROUNDUP(ROUND({FEE_CELL}*{CONTRACTS_CELL}*(1-{b})*{b},6),2)/{CONTRACTS_CELL})'

    def ret_dog(r, L):
        b, f, w = f"{L['bid10']}{r}", f"{L['fee_dog']}{r}", f"{L['won']}{r}"
        return f'=IF({b}="","",IF({w}=0,1,0)/((1-{b})+{f})-1)'

    return [Col("fee_fav", "Fee buying fav ($/contract)", "Betting", 10, "$0.0000", fee_fav),
            Col("ret_fav", "Return buying fav at its ask, 10 min before (per $1, after fee)", "Betting", 13, RET, ret_fav),
            Col("fee_dog", "Fee buying dog ($/contract)", "Betting", 10, "$0.0000", fee_dog),
            Col("ret_dog", "Return buying dog at its ask, 10 min before (per $1, after fee)", "Betting", 13, RET, ret_dog)]


def price_formula_cols(extra_moves=True):
    def spread(r, L):
        return f'=IF(OR({L["bid10"]}{r}="",{L["ask10"]}{r}=""),"",{L["ask10"]}{r}-{L["bid10"]}{r})'

    def move1(r, L):
        return f'=IF(OR({L["c1h"]}{r}="",{L["c10"]}{r}=""),"",{L["c10"]}{r}-{L["c1h"]}{r})'

    def move2(r, L):
        return f'=IF(OR({L["c10"]}{r}="",{L["a10"]}{r}=""),"",{L["a10"]}{r}-{L["c10"]}{r})'

    cols = [Col("spread", "Spread 10 min before", "Prices", 8, PTS, spread),
            Col("move1", "Move: 1 h → 10 min before", "Prices", 9, PTS, move1)]
    if extra_moves:
        cols.append(Col("move2", "Move: 10 min before → 10 min after start", "Prices", 10, PTS, move2))
    return cols


def match_summary(L, last):
    rng = lambda k: f"{L[k]}{FIRST}:{L[k]}{last}"  # noqa: E731
    return [("Fav won", f"SUBTOTAL(101,{rng('won')})", PCT),
            ("Avg fav chance 10 min before", f"SUBTOTAL(101,{rng('c10')})", PCT),
            ("Return buying fav", f"SUBTOTAL(101,{rng('ret_fav')})", RET),
            ("Return buying dog", f"SUBTOTAL(101,{rng('ret_dog')})", RET)]


def valorant_cols(with_results):
    cols = [Col("date", "Date & time (New York)", "Match", 17, "yyyy-mm-dd hh:mm"),
            Col("fav", "Favorite (10 min before)", "Match", 20),
            Col("dog", "Underdog", "Match", 20),
            Col("weekday", "Day", "Match", 5),
            Col("event", "Event", "Match", 30),
            Col("group", "Event type", "Match", 13),
            Col("region", "Region", "Match", 11),
            Col("stage", "Stage", "Match", 18),
            Col("bo", "Best of", "Match", 6),
            Col("patch", "Patch", "Match", 7),
            Col("c1h", "Fav chance 1 h before", "Prices", 9, PCT),
            Col("c10", "Fav chance 10 min before", "Prices", 9, PCT),
            Col("a10", "Fav chance 10 min after start", "Prices", 9, PCT),
            Col("bid10", "Fav bid 10 min before", "Prices", 8, PCT),
            Col("ask10", "Fav ask 10 min before", "Prices", 8, PCT)]
    cols += price_formula_cols()
    cols += [Col("won", "Fav won (1 = yes)", "Result", 7),
             Col("score", "Series score (fav–dog)", "Result", 8),
             Col("maps_played", "Maps played", "Result", 7),
             Col("distance", "Went the distance", "Result", 8)]
    for i in (1, 2, 3):
        cols += [Col(f"map{i}", f"Map {i}", "Maps", 9),
                 Col(f"pick{i}", f"Map {i} picked by", "Maps", 8)]
        if with_results:
            cols.append(Col(f"res{i}", f"Map {i} result", "Maps", 10))
        cols += [Col(f"frec{i}", f"Fav record on map {i} (120 days)", "Maps", 9),
                 Col(f"drec{i}", f"Dog record on map {i} (120 days)", "Maps", 9)]
    cols += [Col("other_maps", "Maps 4–5 (Bo5)", "Maps", 12),
             Col("fav_overall", "Fav all maps (120 days)", "Maps", 9),
             Col("dog_overall", "Dog all maps (120 days)", "Maps", 9),
             Col("model", "Map model: fav chance", "Model", 9, PCT),
             Col("edge_model", "Map model minus price 10 min before", "Model", 10, PTS,
                 lambda r, L: f'=IF(OR({L["model"]}{r}="",{L["c10"]}{r}=""),"",{L["model"]}{r}-{L["c10"]}{r})')]
    cols += betting_cols()
    cols += [Col("volume", "Kalshi volume, whole market (contracts) — includes live trading", "Links", 12, "#,##0"),
             Col("vlr", "vlr.gg", "Links", 7),
             Col("ticker", "Kalshi event", "Links", 34)]
    return cols


def kalshi_cols():
    cols = [Col("date", "Date & time (New York)", "Match", 17, "yyyy-mm-dd hh:mm"),
            Col("fav", "Favorite (10 min before)", "Match", 22),
            Col("dog", "Underdog", "Match", 22),
            Col("weekday", "Day", "Match", 5),
            Col("c1h", "Fav chance 1 h before", "Prices", 9, PCT),
            Col("c30", "Fav chance 30 min before", "Prices", 9, PCT),
            Col("c10", "Fav chance 10 min before", "Prices", 9, PCT),
            Col("c0", "Fav chance at start", "Prices", 9, PCT),
            Col("a10", "Fav chance 10 min after start", "Prices", 9, PCT),
            Col("bid10", "Fav bid 10 min before", "Prices", 8, PCT),
            Col("ask10", "Fav ask 10 min before", "Prices", 8, PCT)]
    cols += price_formula_cols()
    cols += [Col("won", "Fav won (1 = yes)", "Result", 7)]
    cols += betting_cols()
    cols += [Col("volume", "Kalshi volume, whole market (contracts) — includes live trading", "Links", 12, "#,##0"),
             Col("ticker", "Kalshi event", "Links", 34)]
    return cols


# --------------------------------------------------------------------------- summary sheets

def table_header(ws, row, headers, widths=None, fill="DDEBF7"):
    for i, h in enumerate(headers, start=1):
        style_header(ws.cell(row=row, column=i, value=h), fill)
        if widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.row_dimensions[row].height = 42


def stat_formulas(sheet, L, last, conds):
    """Standard stats for rows matching COUNTIFS-style conditions [(key, criteria_expr)]."""
    rng = lambda k: f"'{sheet}'!${L[k]}${FIRST}:${L[k]}${last}"  # noqa: E731
    crit = ",".join(f"{rng(k)},{c}" for k, c in conds)
    n = f"COUNTIFS({crit})"
    price = f"AVERAGEIFS({rng('c10')},{crit})"
    won = f"AVERAGEIFS({rng('won')},{crit})"
    retf = f"AVERAGEIFS({rng('ret_fav')},{crit})"
    retd = f"AVERAGEIFS({rng('ret_dog')},{crit})"
    return n, price, won, retf, retd


def write_stat_row(ws, row, label_cells, sheet, L, last, conds):
    """Columns after the labels: matches, avg price, fav won, gap, ±, verdict, ret fav, ret dog."""
    c0 = len(label_cells) + 1
    for i, v in enumerate(label_cells, start=1):
        ws.cell(row=row, column=i, value=v)
    n, price, won, retf, retd = stat_formulas(sheet, L, last, conds)
    col = lambda k: get_column_letter(c0 + k)  # noqa: E731
    ws.cell(row=row, column=c0, value=f"={n}").number_format = "#,##0"
    ws.cell(row=row, column=c0 + 1, value=f'=IFERROR({price},"")').number_format = PCT
    ws.cell(row=row, column=c0 + 2, value=f'=IFERROR({won},"")').number_format = PCT
    ws.cell(row=row, column=c0 + 3, value=f'=IFERROR({col(2)}{row}-{col(1)}{row},"")').number_format = PTS
    ws.cell(row=row, column=c0 + 4,
            value=f'=IFERROR(1.645*SQRT({col(1)}{row}*(1-{col(1)}{row})/{col(0)}{row}),"")').number_format = PTS
    ws.cell(row=row, column=c0 + 5, value=(
        f'=IF({col(0)}{row}<30,"too few",IF(ABS({col(3)}{row})>{col(4)}{row},'
        f'IF({col(3)}{row}>0,"fav under-priced","fav over-priced"),"no clear gap"))'))
    ws.cell(row=row, column=c0 + 6, value=f'=IFERROR({retf},"")').number_format = RET
    ws.cell(row=row, column=c0 + 7, value=f'=IFERROR({retd},"")').number_format = RET


STAT_HEADERS = ["Matches", "Avg fav chance 10 min before", "Fav actually won", "Gap (won − chance)",
                "± noise (90%)", "Read", "Avg return buying fav", "Avg return buying dog"]
STAT_WIDTHS = [9, 11, 10, 10, 9, 15, 11, 11]


def colour_stats(ws, first_row, last_row, c0):
    for k in (3, 6, 7):
        letter = get_column_letter(c0 + k)
        rng = f"{letter}{first_row}:{letter}{last_row}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="006100")))
        ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"], font=Font(color="9C0006")))
    letter = get_column_letter(c0 + 5)
    rng = f"{letter}{first_row}:{letter}{last_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"fav under-priced"'],
                                                  fill=PatternFill("solid", fgColor="C6EFCE")))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"fav over-priced"'],
                                                  fill=PatternFill("solid", fgColor="FFC7CE")))


def by_price_sheet(wb, sheets):
    ws = wb.create_sheet("By price")
    ws["A1"] = "Does the favorite win as often as its price says? Buckets by the favorite's chance 10 minutes before the start."
    ws["A1"].font = Font(name=FONT, bold=True, size=11)
    ws["A2"] = ("Gap = how often the favorite really won minus its average price. A gap bigger than the ± noise, "
                "with a positive average return, is a candidate edge.")
    row = 4
    edges = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0001]
    for game, (sheet, L, last) in sheets.items():
        ws.cell(row=row, column=1, value=game).font = Font(name=FONT, bold=True, size=11)
        row += 1
        table_header(ws, row, ["From", "To"] + STAT_HEADERS, [8, 8] + STAT_WIDTHS)
        row += 1
        first = row
        for lo, hi in zip(edges, edges[1:]):
            ws.cell(row=row, column=1, value=lo).number_format = "0%"
            ws.cell(row=row, column=2, value=min(hi, 1.0)).number_format = "0%"
            write_stat_row(ws, row, [lo, min(hi, 1.0)], sheet, L, last,
                           [("c10", f'">="&A{row}'), ("c10", f'"<"&IF(B{row}>=1,1.0001,B{row})')])
            ws.cell(row=row, column=1).number_format = "0%"
            ws.cell(row=row, column=2).number_format = "0%"
            row += 1
        write_stat_row(ws, row, ["All", ""], sheet, L, last, [("c10", '">=0"')])
        ws.cell(row=row, column=1).font = Font(name=FONT, bold=True, size=10)
        colour_stats(ws, first, row, 3)
        row += 3
    ws.freeze_panes = "A4"


def price_moves_sheet(wb, sheets):
    ws = wb.create_sheet("Price moves")
    ws["A1"] = "Does following the late money work? Buckets by how the favorite's price moved from 1 hour to 10 minutes before."
    ws["A1"].font = Font(name=FONT, bold=True, size=11)
    ws["A2"] = "Returns are for buying at 10 minutes before, after the move has happened."
    row = 4
    buckets = [("Fell 5+ points", -1, -0.05), ("Fell 2–5 points", -0.05, -0.02), ("Flat (within 2)", -0.02, 0.02),
               ("Rose 2–5 points", 0.02, 0.05), ("Rose 5+ points", 0.05, 1)]
    for game, (sheet, L, last) in sheets.items():
        ws.cell(row=row, column=1, value=game).font = Font(name=FONT, bold=True, size=11)
        row += 1
        table_header(ws, row, ["Move", "From", "To"] + STAT_HEADERS, [16, 7, 7] + STAT_WIDTHS)
        row += 1
        first = row
        for label, lo, hi in buckets:
            write_stat_row(ws, row, [label, lo, hi], sheet, L, last,
                           [("move1", f'">="&B{row}'), ("move1", f'"<"&C{row}')])
            ws.cell(row=row, column=2).number_format = PTS
            ws.cell(row=row, column=3).number_format = PTS
            row += 1
        colour_stats(ws, first, row - 1, 4)
        row += 2
    ws.freeze_panes = "A4"


def slices_sheet(wb, sheets, val_rows):
    ws = wb.create_sheet("Slices")
    ws["A1"] = "Quick cuts. Each row: the same stats as By price, for one slice of matches."
    ws["A1"].font = Font(name=FONT, bold=True, size=11)
    row = 3
    table_header(ws, row, ["Game", "Cut", "Value"] + STAT_HEADERS, [9, 14, 22] + STAT_WIDTHS)
    row += 1
    first = row
    for game, (sheet, L, last) in sheets.items():
        write_stat_row(ws, row, [game, "All", "all matches"], sheet, L, last, [("c10", '">=0"')])
        row += 1
        cuts = [("Day", "weekday", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])]
        if game == "Valorant":
            cuts = [("Event type", "group", ["International", "VCT league", "Challengers", "Game Changers", "Other"]),
                    ("Region", "region", [k for k, _ in Counter(r["region"] for r in val_rows).most_common()]),
                    ("Best of", "bo", [1, 3, 5])] + cuts
        cuts.append(("Spread 10 min before", "spread", None))
        for cut, key, values in cuts:
            if values is None:
                for label, lo, hi in (("tight (≤ 2¢)", 0, 0.0201), ("medium (2–5¢)", 0.0201, 0.0501),
                                      ("wide (> 5¢)", 0.0501, 1)):
                    write_stat_row(ws, row, [game, cut, label], sheet, L, last,
                                   [(key, f'">="&{lo}'), (key, f'"<"&{hi}')])
                    row += 1
                continue
            for v in values:
                crit = f'"{v}"' if isinstance(v, str) else str(v)
                write_stat_row(ws, row, [game, cut, v], sheet, L, last, [(key, crit)])
                row += 1
    colour_stats(ws, first, row - 1, 4)
    ws.freeze_panes = "D4"
    ws.auto_filter.ref = f"A3:K{row - 1}"


def by_team_sheet(wb, sheets, team_lists, min_matches=5):
    ws = wb.create_sheet("By team")
    ws["A1"] = (f"Teams with {min_matches}+ matches: do they win more or less than Kalshi expects? "
                "Expected wins = sum of their chances 10 minutes before.")
    ws["A1"].font = Font(name=FONT, bold=True, size=11)
    ws["A2"] = ("With hundreds of teams, a few will look great or terrible by luck alone. Treat a team as "
                "interesting only with many matches and a gap far outside the ± noise.")
    row = 4
    headers = ["Game", "Team", "Matches", "Wins", "Expected wins", "Wins above expected", "± noise (90%)",
               "Times favorite", "Avg return backing them (after fee)"]
    table_header(ws, row, headers, [9, 26, 9, 8, 10, 11, 10, 10, 13])
    row += 1
    first = row
    for game, teams in team_lists.items():
        sheet, L, last = sheets[game]
        rng = lambda k: f"'{sheet}'!${L[k]}${FIRST}:${L[k]}${last}"  # noqa: E731
        for t in teams:
            ws.cell(row=row, column=1, value=game)
            ws.cell(row=row, column=2, value=t)
            b = f"$B{row}"
            ws.cell(row=row, column=3, value=f"=COUNTIF({rng('fav')},{b})+COUNTIF({rng('dog')},{b})")
            ws.cell(row=row, column=4, value=f"=COUNTIFS({rng('fav')},{b},{rng('won')},1)+COUNTIFS({rng('dog')},{b},{rng('won')},0)")
            ws.cell(row=row, column=5, value=(f"=SUMIFS({rng('c10')},{rng('fav')},{b})"
                                              f"+COUNTIFS({rng('dog')},{b},{rng('c10')},\">=0\")"
                                              f"-SUMIFS({rng('c10')},{rng('dog')},{b})")).number_format = "0.0"
            ws.cell(row=row, column=6, value=f"=D{row}-E{row}").number_format = "+0.0;-0.0;0.0"
            ws.cell(row=row, column=7, value=f"=1.645*SQRT(E{row}*(1-E{row}/C{row}))").number_format = "0.0"
            ws.cell(row=row, column=8, value=f"=COUNTIF({rng('fav')},{b})")
            ws.cell(row=row, column=9, value=(
                f"=IFERROR((SUMIFS({rng('ret_fav')},{rng('fav')},{b})+SUMIFS({rng('ret_dog')},{rng('dog')},{b}))"
                f"/(COUNTIFS({rng('fav')},{b},{rng('ret_fav')},\">-2\")+COUNTIFS({rng('dog')},{b},{rng('ret_dog')},\">-2\")),\"\")"
            )).number_format = RET
            row += 1
    for letter in ("F", "I"):
        rng_ = f"{letter}{first}:{letter}{row - 1}"
        ws.conditional_formatting.add(rng_, CellIsRule(operator="greaterThan", formula=["0"], font=Font(color="006100")))
        ws.conditional_formatting.add(rng_, CellIsRule(operator="lessThan", formula=["0"], font=Font(color="9C0006")))
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:I{row - 1}"


def by_event_sheet(wb, sheet, L, last, events):
    ws = wb.create_sheet("By event")
    ws["A1"] = "Valorant events: is the favorite priced right in each one?"
    ws["A1"].font = Font(name=FONT, bold=True, size=11)
    row = 3
    table_header(ws, row, ["Event", "Event type"] + STAT_HEADERS, [40, 13] + STAT_WIDTHS)
    row += 1
    first = row
    for ev, grp in events:
        write_stat_row(ws, row, [ev, grp], sheet, L, last, [("event", f'"{ev}"')])
        row += 1
    colour_stats(ws, first, row - 1, 3)
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"A3:J{row - 1}"


def maps_sheets(wb, maps_rows):
    ws = wb.create_sheet("Valorant maps")
    cols = [("date", "Date & time (New York)", 17, "yyyy-mm-dd hh:mm"), ("map", "Map", 9, None),
            ("order", "Map no.", 6, None), ("pick", "Picked by", 8, None), ("fav", "Favorite", 20, None),
            ("dog", "Underdog", 20, None), ("event", "Event", 30, None), ("group", "Event type", 13, None),
            ("c10", "Fav series chance 10 min before", 10, PCT), ("fav_won_map", "Fav won this map (1 = yes)", 8, None),
            ("picker_won", "Picking team won this map (1 = yes)", 9, None), ("rf", "Fav rounds", 6, None),
            ("rd", "Dog rounds", 6, None), ("frec", "Fav record on map (120 days)", 9, None),
            ("drec", "Dog record on map (120 days)", 9, None), ("won", "Fav won the series", 8, None)]
    for i, (k, h, w, f) in enumerate(cols, start=1):
        style_header(ws.cell(row=3, column=i, value=h), SECTION_FILL["Maps"])
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[3].height = 54
    for n, r in enumerate(maps_rows):
        for i, (k, h, w, f) in enumerate(cols, start=1):
            c = ws.cell(row=FIRST + n, column=i, value=r.get(k))
            if f:
                c.number_format = f
    last = FIRST + max(len(maps_rows), 1) - 1
    L = {k: get_column_letter(i) for i, (k, *_r) in enumerate(cols, start=1)}
    ws["A1"] = "Every played Valorant map: filter any column, this row updates →"
    ws["A1"].font = Font(name=FONT, bold=True, size=10)
    items = [("Maps shown", f"SUBTOTAL(103,A{FIRST}:A{last})", "0"),
             ("Fav won map", f"SUBTOTAL(101,{L['fav_won_map']}{FIRST}:{L['fav_won_map']}{last})", PCT),
             ("Picking team won map", f"SUBTOTAL(101,{L['picker_won']}{FIRST}:{L['picker_won']}{last})", PCT)]
    place_summary(ws, items, [c[2] for c in cols], start_col=4)
    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols))}{last}"

    s = wb.create_sheet("By map")
    s["A1"] = "Valorant maps: how often the picking team and the favorite win each map."
    s["A1"].font = Font(name=FONT, bold=True, size=11)
    s["A2"] = "Map wins are not Kalshi bets (Kalshi prices the series), but they show which maps swing results."
    headers = ["Map", "Times played", "Picked (not decider)", "Picking team won", "± noise (90%)",
               "As decider", "Fav won map", "Fav won map when fav picked", "Fav won map when dog picked",
               "Fav won map as decider"]
    table_header(s, 4, headers, [10, 9, 9, 10, 9, 9, 10, 11, 11, 11], fill="FCE4D6")
    rng = lambda k: f"'Valorant maps'!${L[k]}${FIRST}:${L[k]}${last}"  # noqa: E731
    row = 5
    for m, _ in Counter(r["map"] for r in maps_rows).most_common():
        a = f"$A{row}"
        s.cell(row=row, column=1, value=m)
        s.cell(row=row, column=2, value=f"=COUNTIF({rng('map')},{a})")
        s.cell(row=row, column=3, value=f"=COUNTIFS({rng('map')},{a},{rng('picker_won')},\">=0\")")
        s.cell(row=row, column=4, value=f'=IFERROR(AVERAGEIFS({rng("picker_won")},{rng("map")},{a}),"")').number_format = PCT
        s.cell(row=row, column=5, value=f'=IFERROR(1.645*SQRT(0.25/C{row}),"")').number_format = PTS
        s.cell(row=row, column=6, value=f'=COUNTIFS({rng("map")},{a},{rng("pick")},"Decider")')
        s.cell(row=row, column=7, value=f'=IFERROR(AVERAGEIFS({rng("fav_won_map")},{rng("map")},{a}),"")').number_format = PCT
        for col, who in ((8, "Fav"), (9, "Dog"), (10, "Decider")):
            s.cell(row=row, column=col, value=(f'=IFERROR(AVERAGEIFS({rng("fav_won_map")},{rng("map")},{a},'
                                               f'{rng("pick")},"{who}"),"")')).number_format = PCT
        row += 1
    s.cell(row=row, column=1, value="All maps").font = Font(name=FONT, bold=True, size=10)
    s.cell(row=row, column=2, value=f"=COUNTA({rng('map')})")
    s.cell(row=row, column=3, value=f"=COUNTIF({rng('picker_won')},\">=0\")")
    s.cell(row=row, column=4, value=f'=IFERROR(AVERAGE({rng("picker_won")}),"")').number_format = PCT
    s.cell(row=row, column=5, value=f'=IFERROR(1.645*SQRT(0.25/C{row}),"")').number_format = PTS
    s.cell(row=row, column=6, value=f'=COUNTIF({rng("pick")},"Decider")')
    s.cell(row=row, column=7, value=f'=IFERROR(AVERAGE({rng("fav_won_map")}),"")').number_format = PCT
    for col, who in ((8, "Fav"), (9, "Dog"), (10, "Decider")):
        s.cell(row=row, column=col, value=f'=IFERROR(AVERAGEIFS({rng("fav_won_map")},{rng("pick")},"{who}"),"")').number_format = PCT
    s.freeze_panes = "B5"


def start_sheet(wb, counts, generated, notes):
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 90
    ws["B2"] = "Esports prediction-market research workbook"
    ws["B2"].font = Font(name=FONT, bold=True, size=14)
    ws["B3"] = f"Built {generated} from public data only (Kalshi's public API; vlr.gg via vlrdevapi). Nothing here was traded."
    ws["B5"] = "Settings (change these and every sheet updates)"
    ws["B5"].font = Font(name=FONT, bold=True, size=11)
    lever_font = Font(name=FONT, size=10, color="0000FF")
    lever_fill = PatternFill("solid", fgColor="FFFF00")
    ws["B8"], ws["C8"], ws["D8"] = "Kalshi taker fee rate", 0.07, "Kalshi charges ceil(rate × contracts × price × (1 − price)) in cents per order."
    ws["B9"], ws["C9"], ws["D9"] = "Contracts per order", 100, "Only affects how the fee rounds up to a whole cent."
    for c in ("C8", "C9"):
        ws[c].font = lever_font
        ws[c].fill = lever_fill
    ws["B7"] = "Setting"
    ws["C7"] = "Value"
    ws["D7"] = "What it does"
    for c in ("B7", "C7", "D7"):
        style_header(ws[c], "D9D9D9")
    r = 11
    ws.cell(row=r, column=2, value="What's inside").font = Font(name=FONT, bold=True, size=11)
    r += 1
    for name, desc in counts:
        ws.cell(row=r, column=2, value=name).font = Font(name=FONT, bold=True, size=10)
        ws.cell(row=r, column=4, value=desc)
        r += 1
    r += 1
    ws.cell(row=r, column=2, value="How to hunt for an edge").font = Font(name=FONT, bold=True, size=11)
    r += 1
    tips = [
        ("1. Filter a matches sheet", "Use the filter arrows in row 3. Row 1 recalculates for the rows you can see: "
                                      "how often the favorite won, its average price, and the average return of "
                                      "buying either side 10 minutes before the start, after Kalshi's fee."),
        ("2. A real edge needs", "a positive average return after fees, a few hundred matches, the same result in "
                                 "both halves of the dates (filter by date), and a reason the market would miss it."),
        ("3. Beware of luck", "Try 50 filters and a few will look great by chance. The ± noise columns show how big a "
                              "gap luck alone produces about 9 times in 10."),
        ("4. Beware of hindsight", "Volume, series score, maps played and 'went the distance' are only known after the "
                                   "match. Filtering on them leaks the result (series that go to a third map trade "
                                   "about twice as much). Use them to understand, never to pick bets."),
        ("5. Prices", "Kalshi 1-minute candles: the middle of bid and ask (if the gap is 15¢ or less), else the last "
                      "trade. 'Favorite' = the team priced 50% or more 10 minutes before (1 hour before if missing). "
                      "Returns assume your order fills at the ask shown, which is only true for small bets in thin markets."),
        ("6. Times", "Scheduled start from Kalshi's event ticker, New York time. vlr.gg times agreed to the minute "
                     "for most Valorant matches."),
    ]
    for a, b in tips:
        ws.cell(row=r, column=2, value=a).font = Font(name=FONT, bold=True, size=10)
        ws.cell(row=r, column=2).alignment = Alignment(vertical="top")
        ws.cell(row=r, column=4, value=b).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 42
        r += 1
    r += 1
    ws.cell(row=r, column=2, value="Already tested").font = Font(name=FONT, bold=True, size=11)
    r += 1
    for a, b in notes:
        ws.cell(row=r, column=2, value=a).font = Font(name=FONT, bold=True, size=10)
        ws.cell(row=r, column=2).alignment = Alignment(vertical="top")
        ws.cell(row=r, column=4, value=b).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 42
        r += 1


def apply_font(wb):
    """Arial everywhere, keeping bold, italics and colours."""
    plain = Font(name=FONT, size=10)
    cache = {}
    for w in wb.worksheets:
        for row in w.iter_rows():
            for c in row:
                f = c.font
                if f is None or f.name == FONT:
                    continue
                if not (f.b or f.i or f.u or (f.color is not None and f.color.rgb not in (None, "FF000000"))):
                    c.font = plain
                    continue
                key = (f.b, f.i, f.u, f.sz, f.color.rgb if f.color is not None else None)
                if key not in cache:
                    cache[key] = Font(name=FONT, size=f.sz or 10, bold=f.b, italic=f.i, underline=f.u, color=f.color)
                c.font = cache[key]


# --------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", default="data/backtest")
    ap.add_argument("--dataset", default="data/dataset")
    ap.add_argument("--out", default="esports_research.xlsx")
    ap.add_argument("--min-team-matches", type=int, default=5)
    args = ap.parse_args(argv)

    cache = vb.Cache(args.backtest)
    val, val_maps = valorant_rows(cache)
    with_results = bool(val_maps)
    others = {}
    for game, series in GAMES:
        path = os.path.join(args.dataset, f"{series}.json")
        if os.path.exists(path):
            rows, store = kalshi_only_rows(path)
            if rows:
                others[game] = (rows, store)

    wb = Workbook()
    sheets = {}
    ws = wb.create_sheet("Valorant matches")
    L, last = write_matches(ws, valorant_cols(with_results), val, match_summary, "Valorant")
    sheets["Valorant"] = ("Valorant matches", L, last)
    if with_results:
        maps_sheets(wb, val_maps)
    for game, (rows, _) in others.items():
        ws = wb.create_sheet(f"{game} matches")
        L2, last2 = write_matches(ws, kalshi_cols(), rows, match_summary, game)
        sheets[game] = (f"{game} matches", L2, last2)

    by_price_sheet(wb, sheets)
    price_moves_sheet(wb, sheets)
    slices_sheet(wb, sheets, val)
    team_lists = {}
    for game, rows in [("Valorant", val)] + [(g, r) for g, (r, _) in others.items()]:
        cnt = Counter([r["fav"] for r in rows] + [r["dog"] for r in rows])
        team_lists[game] = [t for t, n in cnt.most_common() if n >= args.min_team_matches]
    by_team_sheet(wb, sheets, team_lists, args.min_team_matches)
    events = Counter((r["event"], r["group"]) for r in val)
    by_event_sheet(wb, *sheets["Valorant"], [e for e, _ in events.most_common()])

    span = lambda rows: f"{min(r['date'] for r in rows):%b %d, %Y} to {max(r['date'] for r in rows):%b %d, %Y}"  # noqa: E731
    counts = [("Valorant matches", f"{len(val):,} Kalshi Valorant matches joined to vlr.gg ({span(val)}): prices at "
                                   "three times, result, veto, map records, map-model chance, returns.")]
    if with_results:
        counts.append(("Valorant maps", f"{len(val_maps):,} played maps with the picking team and the score."))
    for game, (rows, store) in others.items():
        counts.append((f"{game} matches", f"{len(rows):,} Kalshi {game} matches ({span(rows)}): prices at five "
                                         f"times, result, returns. Kalshi only, so no maps or events."))
    counts += [("By price", "Is the favorite priced right at each price level? (classic favorite/longshot check)"),
               ("Price moves", "Does following the late price move pay?"),
               ("Slices", "Event type, region, best-of, day of week and spread, for each game."),
               ("By team", "Teams that win more or less than Kalshi expects."),
               ("By event", "Valorant events, one row each.")]
    if with_results:
        counts.append(("By map", "Which maps the picking team and the favorite win."))
    notes = [("Map-veto edge (Valorant)", "No edge: map records say a little about who wins, but Kalshi's price an "
                                          "hour before already includes it, and betting the gap showed no reliable "
                                          "profit after fees. Full report: data/backtest/VETO_REPORT.md in the repo."),
             ("Kalshi vs Polymarket arbitrage", "Paper test running until Nov 12; see data/REPORT.md in the repo.")]
    from datetime import datetime
    start_sheet(wb, counts, datetime.now().strftime("%b %d, %Y"), notes)
    wb.move_sheet("Start here", offset=-wb.index(wb["Start here"]))
    apply_font(wb)
    wb.save(args.out)
    print(json.dumps({"out": args.out, "valorant": len(val), "valorant_maps": len(val_maps),
                      **{g: len(r) for g, (r, _) in others.items()},
                      "teams": {g: len(t) for g, t in team_lists.items()}}))


if __name__ == "__main__":
    main()
