# Map-veto backtest (Valorant, Kalshi)

Generated 2026-11-05T05:05:43Z. Public data only; nothing was traded.

## Verdict

Too few matches to judge (26; needs about 100 or more). Run the collector further back (--since) and report again.

## Data

- kalshi matches: 1359
- used (pre price, veto, map records): 27
- with a post-veto price: 26
- dates: 2026-10-23 to 2026-11-01
- VCT (top tier) matches: 16
- left out: not found on vlr.gg 1282; no start time in ticker 304; vlr details not fetched yet 50; not settled yes/no 15; not two markets 1
- start time check, vlr.gg minus Kalshi: median +0 min (middle half +0 to +25)
- examples not found on vlr.gg: 2026-11-01T13:00 Team relaxcis vs Team Samuraj; 2026-10-31T18:00 KRÜ Blaze vs Shopify Rebellion GC; 2026-10-31T13:30 Team relaxcis vs Team Samuraj; 2026-10-31T11:10 Team GPK vs Team Redgar; 2026-10-30T21:00 KRÜ Blaze vs MIBR Female; 2026-10-30T18:00 Gentle Mates GC vs Shopify Rebellion GC; 2026-10-28T18:00 MIBR Female vs SK Nebula; 2026-10-27T21:00 KRÜ Blaze vs Shopify Rebellion GC

## How well each predicted the winner

Lower is better. 26 matches with all three prices.

| Prediction | Log loss | Brier |
|---|---|---|
| Kalshi, 1 h before | 0.6952 | 0.2508 |
| Map model (1 h price + maps) | 0.7437 | 0.2689 |
| Kalshi, 10 min after start | 0.6295 | 0.2229 |

## Does the map information matter?

- Before the veto: weight on the map model's adjustment -0.86 (± 1.07). Above 0 by more than twice the ± means map records add information to the pre-veto price; 1.0 means the model's adjustment is the right size.
- After the market moved: weight on the gap between model and post price -1.00 (± 0.98). Above 0 by more than twice the ± would mean the market under-reacts.
- Market moved between the two checkpoints in 23 of 26 matches. Where the model expected a move of 5+ points, the price moved its way in 8 of 15 (53%).
- Size of the move compared with the model's: -0.07 (1.0 = moves as much as the model says).

## Betting the gap at the post-veto price (10 min after start, Kalshi taker fee included)

| Bet when model is this far from the price | Bets | Won | Avg return per $ | 90% range |
|---|---|---|---|---|
| 3¢ | 14 | 4 | -40.1% | -84.0% to +4.7% |
| 5¢ | 10 | 3 | -32.1% | -85.2% to +28.6% |
| 10¢ | 6 | 2 | -24.1% | -100.0% to +53.8% |

Assumes each bet fills at the quoted price. Small markets often have only a few dollars there, so real results would be worse for anything but small bets.

## Sensitivity to the post checkpoint

| Minutes after scheduled start | Matches | Leftover weight (±) | Bets at 5¢ | Avg return |
|---|---|---|---|---|
| +0 | 25 | -0.07 (± 0.57) | 12 | -12.3% |
| +10 | 26 | -1.00 (± 0.98) | 10 | -32.1% |
| +20 | 26 | -0.36 (± 0.68) | 16 | -44.1% |

## Method and limits

- Prices: Kalshi 1-minute candles for the first team's market; mid of bid and ask (spread ≤ 15¢), else last trade. Pre = 60 min before the scheduled start in the event ticker; post = 10 min after.
- Maps: picks and decider from the vlr.gg veto, in order. Map records: vlr.gg team stats for the 120 days ending the day before the match, so nothing from the future leaks in.
- Model: the pre price turned into a per-map chance, then moved by each team's map win rate relative to its overall rate (shrunk with 5 pseudo-maps). No settings were tuned on this data.
- The exact time of each veto isn't recorded, so the checkpoints are fixed offsets from the scheduled start. A late start or an early veto blurs the before/after split.
- Results with fewer than a few hundred matches have wide ranges; treat a small positive return as noise unless the 90% range is above zero.
