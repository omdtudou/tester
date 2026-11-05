# arbscan

A fee-aware arbitrage scanner for **Kalshi**, **Polymarket** and **Pinnacle**, with an
**esports mode** that reads Kalshi's and Polymarket US's live order books directly.

It finds matches where backing every outcome across venues returns more than it costs,
*after* each venue's trading fees. For each one it prints an exact bet slip: how many
contracts, the most to pay, and what you'll make.

It does **not** place bets. You place them yourself, as limit orders (see
[Placing the bets](#placing-the-bets)).

## Two modes

| | Sports mode (default) | Esports mode (`--esports`) |
|---|---|---|
| Games | NBA, NFL, NHL, soccer, college… | Valorant, CS2, League of Legends, Dota 2 |
| Data | The Odds API (free key, limited credits) | Kalshi + Polymarket US public APIs (no key, free) |
| Prices | Best price only | Full order books, sized to what's for sale |
| Pinnacle | Fair-price reference (value bets) | Not used |

## Quick start

Needs Python 3.8 or newer and nothing else to install.

```bash
python arbscan.py --demo                    # sports mode on sample data
python arbscan.py --esports --demo          # esports mode on sample data
python -m unittest test_arbscan test_esports
```

### Esports, live

No key needed:

```bash
python arbscan.py --esports --probe                     # first run: see what each venue lists and what matched
python arbscan.py --esports                             # all four games
python arbscan.py --esports --games valorant,cs2 --budget 200
python arbscan.py --esports --watch 60 --beep --log esports.csv
```

**Run `--probe` first.** I built esports mode from the venues' published API docs and couldn't
call the live APIs while writing it. The probe shows:
- how many matches each venue lists
- which matched and which didn't (and why)
- a sample of Polymarket US's raw market fields

If something looks off, save the raw responses with `--probe --save probe.json` and replay them
with `--from-file probe.json`. That file is what's needed to fix a mapping problem.

### Sports, live

Get a free key from [The Odds API](https://the-odds-api.com) (500 credits a month), then:

```bash
export ODDS_API_KEY=your_key              # Windows: set ODDS_API_KEY=your_key
python arbscan.py                         # every live game + the next 8 starting
python arbscan.py --sports basketball_nba,icehockey_nhl --budget 250
```

## Esports mode in detail

1. **Lists matches on both venues.**
   - Kalshi: the series-winner markets (`KXVALORANTGAME`, `KXCS2GAME`, `KXLOLGAME`, and
     `KXDOTA2GAME`, which is unconfirmed and skipped if it doesn't exist).
   - Polymarket US: markets found by searching each game.
   - Single-map, prop and best-of-2 markets are dropped. Best-of-2 is dropped because those
     matches can end in a draw.
2. **Pairs a match only when it's clearly the same match.**
   - Same game.
   - The same two teams, after cleaning up names. "Team Liquid" equals "Liquid" and "Leviatán
     Esports" equals "Leviatan", but "Spirit Academy" never equals "Spirit".
   - Dates within a day or two.
   - If the same teams appear twice and there's no date to tell them apart, the match is skipped.
3. **Knows which team each contract is for.**
   - Polymarket US lists both teams in one market, with a "long" side and a "short" side.
   - Kalshi has a separate market for each team, so backing team A can mean YES on A or NO on B.
     The scanner checks both.
4. **Walks the real order books** level by level to find the most profitable size within your
   budget, with fees rounded up per price level. If the book is thinner than your budget, the
   slip says so.

```
ARB  +2.19% guaranteed after fees  (sized from live order books)
League of Legends | League of Legends: T1 vs Gen.G (BO5) - Worlds | Sat Nov 07 10:00 AM | Series winner BO5
  1. Kalshi         YES "Gen.G"        BUY 102 at <= 59¢ (avg 59¢)   $60.18 + $1.73 fee
     KXLOLGAME-26NOV071000T1GEN-GEN
  2. Polymarket US  "T1"               BUY 102 at <= 36¢ (avg 36¢)   $36.72 + $1.18 fee
     aec-lol-t1-gen-2026-11-07
  Outlay $99.81 -> pays $102.00 whichever team wins -> profit $2.19
```

**Team names that differ between venues** can be added in a JSON file:

```json
{"Movistar KOI": "KOI", "Team Falcons": "Falcons Esports"}
```

```bash
python arbscan.py --esports --aliases aliases.json
```

**Esports-specific risk.** If a match is forfeited, cancelled or postponed, Kalshi's esports
contracts may settle at the "last fair price". Polymarket US uses its own rule, often 50-50.
In that case one leg doesn't pay what the other assumes, so the hedge can break. Every esports
slip carries this warning.

## Paper test: does it actually make money?

This measures, without placing a single order:
- how often esports arbs show up
- whether each one is still there **20 seconds later**, roughly the time it takes you to act
- what you'd have made if you'd placed every slip then

### On GitHub (your computer can stay off)

The included workflow (`.github/workflows/paper-test.yml`) runs on GitHub's servers for free.
Every 10 minutes it watches for 7 minutes, logs everything to `data/paper.jsonl`, and rewrites
`data/REPORT.md`. It switches itself off after the `STOP_AFTER` date in the workflow file.

1. Create a new **public** repository on GitHub. Public repos get unlimited free Actions
   minutes; a private one would use up the free allowance in about two days. The log only
   contains public market prices.
2. Put everything from this folder at the root of the repository, including the hidden
   `.github` folder.
3. In the repository's **Actions** tab, enable workflows if asked. Then open **paper-test** and
   click **Run workflow**, or wait for the next 10-minute mark.
4. Read `data/REPORT.md` whenever you like.

GitHub's scheduler sometimes runs late. The report only counts time actually spent watching, so
gaps don't skew the numbers.

### On your own computer

```bash
python arbscan.py --paper --hours 168        # a week; leave it running
python arbscan.py --report paper.jsonl       # summary, any time
```

### What the report says

```
- Watched for about 160.2 hours (9,870 scans, one every ~45s).
- Arbs: 14 appearances across 9 matches (CS2 8, Valorant 4, League of Legends 2).
- Checked again 20s later (your reaction time): fully fillable 5, partly 3, gone 6.
- Profit if you'd placed every one 20s after it appeared: $11.40, about $1.71 per day watched.
**Verdict:** Small but real ...
```

(The numbers above are an example, not a result.) The report won't estimate a daily figure from
less than 6 hours of data. It also assumes both legs fill together, so real results would be
slightly worse.

## Reading a sports-mode slip

```
ARB  +1.02% guaranteed after fees
NBA | Los Angeles Lakers @ Boston Celtics | LIVE | Moneyline
  1. Kalshi         Boston Celtics       BUY 101 contracts at <= 52¢   $52.52 + $1.77 fee  [10s old]
  2. Polymarket US  Los Angeles Lakers   BUY 101 shares at <= 44¢      $44.44 + $1.25 fee  [5s old]
  Outlay $99.98 -> pays at least $101.00 whichever way it goes -> profit $1.02
```

- **ARB:** guaranteed only if both legs fill at those prices. Sports mode sees only the best
  price, not how much is available, so check the order book before betting.
- **VALUE:** a single bet priced better than Pinnacle's no-vig fair line. It has positive
  expected value but can lose. Turn these off with `--no-value`.
- **Quote age:** the number in brackets is how old the price is. Old quotes are dropped
  automatically (by default after 60 s for live games and 10 min before the start).

## Placing the bets

1. **Use limit orders at the price shown, never market orders.** If the price has moved, the
   order won't fill, and you've lost nothing.
2. **Place the thinner leg first.** Place the second leg only once the first has filled. If the
   first fills only partly, scale the second down to match.
3. **Check that both markets settle the same way.** Look at overtime, postponement,
   cancellation, forfeits and, for the NFL, ties.

## Venues and fees

| Venue | Default role | Taker fee |
|---|---|---|
| Kalshi | bet on | `0.07 × contracts × p × (1 − p)`, rounded up to the cent |
| Polymarket US | bet on | `0.05 × shares × p × (1 − p)` |
| Polymarket (global) | off | `0.05 × shares × p × (1 − p)`; not open to US residents |
| Pinnacle | sports reference | none; doesn't accept US customers |

**Fees change.** Override a rate with `--fee kalshi=0.07`. Resting (maker) orders cost less: often
nothing, though on some major sports series Kalshi charges makers a quarter of the taker rate.

**Choosing where you bet.** In sports mode, `--bet-on` picks the venues you trade on. Add
`pinnacle` only if it's legal where you are. You can also add any bookmaker The Odds API
carries, e.g. `--bet-on kalshi,draftkings`.

## All options

| Option | Default | What it does |
|---|---|---|
| `--esports` | off | esports mode |
| `--games` | all | `valorant,cs2,lol,dota2` (esports) |
| `--probe` | off | show listings and matching instead of arbs (esports) |
| `--aliases FILE` | | team-name aliases (esports) |
| `--kalshi-series GAME=TICKER` | | override a Kalshi series ticker (esports) |
| `--sports` | `upcoming` | sport keys, or `upcoming` (sports) |
| `--markets` | `h2h` | `h2h`, `spreads`, `totals` (sports) |
| `--budget` | `100` | max total outlay per arb, $ |
| `--min-profit` | `0.25` | min guaranteed return after fees, % |
| `--min-ev` / `--value-stake` | `2` / `25` | value-bet threshold % / stake $ (sports) |
| `--max-age` / `--max-age-pregame` | `60` / `600` | drop quotes older than this, seconds (sports) |
| `--fee VENUE=RATE` | | override a taker fee rate |
| `--watch N` | off | rescan every N seconds, showing only new opportunities |
| `--json`, `--log FILE`, `--beep` | | JSON output, CSV log, terminal bell |
| `--save FILE`, `--from-file FILE` | | record raw responses and replay them later |
| `--paper` | off | paper-trade esports: log arbs and recheck each one |
| `--recheck` | `20` | seconds before the recheck (paper) |
| `--minutes` / `--hours` | | stop a paper run after this long |
| `--paper-log FILE` | `paper.jsonl` | where the paper log goes |
| `--report FILE` | | summarise a paper log |

## What it doesn't do

- **Order placement.** Both exchanges have trading APIs, but a half-filled arb leaves you with
  a one-sided bet, so you place the orders.
- **Sports-mode depth.** Only esports mode reads the real order books. Sports mode still uses
  The Odds API's best price.
- **Global Polymarket in esports mode.** It uses Polymarket US, the version open to US residents.

## Ideas taken from polymarket-arbitrage, and what was left out

- **Taken:** reading Kalshi's and Polymarket's order books from their free public APIs. That's
  what esports mode does, and it removes the paid data feed and the guesswork about size.
- **Left out:**
  - **Text-similarity matching.** It paired "Lakers vs Celtics" with "Lakers vs Warriors".
    arbscan requires the same two teams on compatible dates.
  - **"First outcome = YES".** It can put both legs on the same team. arbscan reads Polymarket
    US's long/short flag.
  - **Flat fee guesses.** arbscan uses each venue's published fee formula.
  - **Simulation mode and unfinished auto-trading.**
