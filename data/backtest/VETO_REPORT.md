# Map-veto backtest (Valorant, Kalshi)

Generated 2026-11-05T05:54:17Z. Public data only; nothing was traded.

## Verdict

No edge found: map records did not predict winners better than Kalshi's own price, even before the veto. The market already knows what the map stats know.

## Data

- kalshi matches: 1655
- used (pre price, veto, map records): 1340
- with a post-veto price: 1255
- dates: 2026-01-15 to 2026-11-01
- top-tier matches (VCT leagues, Masters, Champions): 81
- left out: not found on vlr.gg 268; no Kalshi price an hour before 46; not settled yes/no 15; no date in ticker 8; not two markets 1; no veto on vlr.gg 1
- start time check, vlr.gg minus Kalshi: median +0 min (middle half +0 to +0)
- examples not found on vlr.gg: 2026-11-01T13:00 Team relaxcis vs Team Samuraj; 2026-10-31T13:30 Team relaxcis vs Team Samuraj; 2026-10-31T11:10 Team GPK vs Team Redgar; 2026-10-12T16:00 BBL Esports vs Team NVus; 2026-10-09T19:00 Team NVus vs Pcific Esports; 2026-10-09T16:00 BBL Esports vs Fire Flux Esports; 2026-10-08T19:00 BBL Esports vs Pcific Esports; 2026-10-08T16:00 Fire Flux Esports vs Team NVus

## How well each predicted the winner

Lower is better. 1255 matches with all three prices.

| Prediction | Log loss | Brier |
|---|---|---|
| Kalshi, 1 h before | 0.6166 | 0.2145 |
| Map model (1 h price + maps) | 0.6295 | 0.2197 |
| Kalshi, 10 min after start | 0.5898 | 0.2043 |

## Does the map information matter?

- Before the veto: weight on the map model's adjustment 0.09 (± 0.16). Above 0 by more than twice the ± means map records add information to the pre-veto price; 1.0 means the model's adjustment is the right size.
- After the market moved: weight on the gap between model and post price 0.02 (± 0.11). Above 0 by more than twice the ± would mean the market under-reacts.
- Market moved between the two checkpoints in 1187 of 1255 matches. Where the model expected a move of 5+ points, the price moved its way in 366 of 711 (51%).
- Size of the move compared with the model's: 0.03 (1.0 = moves as much as the model says).

## Betting the gap at the post-veto price (10 min after start, Kalshi taker fee included)

| Bet when model is this far from the price | Bets | Won | Avg return per $ | 90% range |
|---|---|---|---|---|
| 3¢ | 804 | 352 | -8.3% | -15.2% to -1.1% |
| 5¢ | 648 | 283 | -6.5% | -14.5% to +2.2% |
| 10¢ | 344 | 143 | -0.4% | -12.6% to +12.1% |

Assumes each bet fills at the quoted price. Small markets often have only a few dollars there, so real results would be worse for anything but small bets.

## Big matches versus small ones

| Slice | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |
|---|---|---|---|---|
| Top tier (VCT leagues, Masters, Champions) | 76 | 0.08 (± 0.39) | 45 | -19.8% |
| Everything else | 1179 | 0.02 (± 0.11) | 603 | -5.5% |
| Busier markets (top half by volume) | 628 | 0.23 (± 0.14) | 363 | +12.2% |
| Quieter markets (bottom half by volume) | 627 | -0.23 (± 0.16) | 285 | -30.2% |

## Sensitivity to the post checkpoint

| Minutes after scheduled start | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |
|---|---|---|---|---|
| +0 | 1306 | -0.05 (± 0.12) | 636 | -3.8% |
| +10 | 1255 | 0.02 (± 0.11) | 648 | -6.5% |
| +20 | 1256 | -0.07 (± 0.09) | 736 | -15.8% |

## Method and limits

- Prices: Kalshi 1-minute candles for the first team's market; mid of bid and ask (spread ≤ 15¢), else last trade. Pre = 60 min before the scheduled start in the event ticker; post = 10 min after.
- Maps: picks and decider from the vlr.gg veto, in order. Map records: vlr.gg team stats for the 120 days ending the day before the match, so nothing from the future leaks in.
- Model: the pre price turned into a per-map chance, then moved by each team's map win rate relative to its overall rate (shrunk with 5 pseudo-maps). No settings were tuned on this data.
- The exact time of each veto isn't recorded, so the checkpoints are fixed offsets from the scheduled start. A late start or an early veto blurs the before/after split.
- Results with fewer than a few hundred matches have wide ranges; treat a small positive return as noise unless the 90% range is above zero.
