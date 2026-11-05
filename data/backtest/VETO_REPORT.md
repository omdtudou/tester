# Map-veto backtest (Valorant, Kalshi)

Generated 2026-11-05T06:07:43Z. Public data only; nothing was traded.

## Verdict

No edge found: map records do say a little about who wins, but Kalshi's price an hour before the start already includes it, and betting the gap showed no reliable profit after fees.

## Data

- kalshi matches: 1655
- used (pre price, veto, map records): 1174
- with a post-veto price: 1105
- dates: 2026-01-15 to 2026-11-01
- top-tier matches (VCT leagues, Masters, Champions): 604
- left out: not found on vlr.gg 268; no veto on vlr.gg 176; no Kalshi price an hour before 37; not settled yes/no 15; no date in ticker 8; not two markets 1
- start time check, vlr.gg minus Kalshi: median +0 min (middle half +0 to +0)
- examples not found on vlr.gg: 2026-11-01T13:00 Team relaxcis vs Team Samuraj; 2026-10-31T13:30 Team relaxcis vs Team Samuraj; 2026-10-31T11:10 Team GPK vs Team Redgar; 2026-10-12T16:00 BBL Esports vs Team NVus; 2026-10-09T19:00 Team NVus vs Pcific Esports; 2026-10-09T16:00 BBL Esports vs Fire Flux Esports; 2026-10-08T19:00 BBL Esports vs Pcific Esports; 2026-10-08T16:00 Fire Flux Esports vs Team NVus

## How well each predicted the winner

Lower is better. 1105 matches with all three prices.

| Prediction | Log loss | Brier |
|---|---|---|
| Kalshi, 1 h before | 0.6313 | 0.2210 |
| Map model (1 h price + maps) | 0.6441 | 0.2258 |
| Kalshi, 10 min after start | 0.6080 | 0.2122 |

## Does the map information matter?

- Map records on their own, ignoring the price: weight 0.35 (± 0.15). Above 0 by more than twice the ± means they do say something about who wins.
- Beyond Kalshi's price an hour before: weight on the map model's adjustment 0.11 (± 0.16). Above 0 by more than twice the ± means map records add information to the pre-veto price; 1.0 means the model's adjustment is the right size.
- After the market moved: weight on the gap between model and post price 0.08 (± 0.11). Above 0 by more than twice the ± would mean the market under-reacts.
- Market moved between the two checkpoints in 1044 of 1105 matches. Where the model expected a move of 5+ points, the price moved its way in 318 of 628 (51%).
- Size of the move compared with the model's: 0.01 (1.0 = moves as much as the model says).

## Betting the gap at the post-veto price (10 min after start, Kalshi taker fee included)

| Bet when model is this far from the price | Bets | Won | Avg return per $ | 90% range |
|---|---|---|---|---|
| 3¢ | 722 | 327 | -4.7% | -12.3% to +3.0% |
| 5¢ | 584 | 267 | -2.2% | -10.6% to +6.2% |
| 10¢ | 311 | 136 | +3.3% | -8.8% to +16.0% |

Assumes each bet fills at the quoted price. Small markets often have only a few dollars there, so real results would be worse for anything but small bets.

## Big matches versus small ones

| Slice | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |
|---|---|---|---|---|
| Top tier (VCT leagues, Masters, Champions) | 582 | 0.07 (± 0.16) | 312 | +2.6% |
| Everything else | 523 | 0.08 (± 0.16) | 272 | -7.8% |
| Tighter markets (spread ≤ 2¢ an hour before) | 769 | 0.02 (± 0.14) | 414 | -1.7% |
| Wider markets (spread > 2¢ an hour before) | 336 | 0.18 (± 0.19) | 170 | -3.6% |

## Sensitivity to the post checkpoint

| Minutes after scheduled start | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |
|---|---|---|---|---|
| +0 | 1144 | 0.03 (± 0.12) | 572 | +0.9% |
| +10 | 1105 | 0.08 (± 0.11) | 584 | -2.2% |
| +20 | 1108 | -0.02 (± 0.10) | 659 | -10.6% |

## Method and limits

- Prices: Kalshi 1-minute candles for the first team's market; mid of bid and ask (spread ≤ 15¢), else last trade. Pre = 60 min before the scheduled start in the event ticker; post = 10 min after.
- Maps: picks and decider from the vlr.gg veto, in order. Map records: vlr.gg team stats for the 120 days ending the day before the match, so nothing from the future leaks in.
- Model: the pre price turned into a per-map chance, then moved by each team's map win rate relative to its overall rate (shrunk with 5 pseudo-maps). No settings were tuned on this data.
- The exact time of each veto isn't recorded, so the checkpoints are fixed offsets from the scheduled start. A late start or an early veto blurs the before/after split.
- Results with fewer than a few hundred matches have wide ranges; treat a small positive return as noise unless the 90% range is above zero.
