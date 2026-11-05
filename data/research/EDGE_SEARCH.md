# Edge search

Each idea is fitted on the earlier half of the matches and tested unchanged on the later half. Effect > 0 means the favorite wins more than its price says (for a feature: when the feature is higher). Returns: betting the side the earlier-half fit prefers by 3¢+, at the ask 10 min before, after Kalshi's fee.

## Valorant

Earlier half: 668 matches before 2026-06-17. Later half: 669 matches from then on.

| Idea | Earlier half: effect (± ) p | Later half: effect (±) p | After correcting for 12 ideas | Later-half bets | Avg return (90% range) |
|---|---|---|---|---|---|
| Favorite-longshot bias | +0.34 (± 0.19) p=0.07 | +0.17 (± 0.18) p=0.34 | p=1.00 | 196 | -2.1% (-14.3 to +10.3) |
| Late price move | +0.81 (± 0.37) p=0.03 | +0.12 (± 0.26) p=0.64 | p=1.00 | 137 | +6.6% (-6.8 to +19.5) |
| Thin markets | -0.10 (± 0.12) p=0.42 | -0.13 (± 0.16) p=0.42 | p=1.00 | 0 | – |
| Near coin flips | -0.35 (± 0.20) p=0.09 | -0.26 (± 0.22) p=0.25 | p=1.00 | 78 | +7.9% (-10.6 to +25.9) |
| Overnight matches (midnight–8am New York) | +0.25 (± 0.17) p=0.16 | -0.05 (± 0.14) p=0.71 | p=1.00 | 189 | -7.0% (-16.1 to +2.1) |
| Teams beating their prices | -0.06 (± 0.06) p=0.30 | -0.03 (± 0.05) p=0.56 | p=1.00 | 92 | -5.8% (-26.3 to +15.3) |
| Recent form | +0.08 (± 0.31) p=0.80 | -0.10 (± 0.28) p=0.74 | p=1.00 | 0 | – |
| Rematch within 30 days | -0.32 (± 0.25) p=0.21 | -0.22 (± 0.25) p=0.38 | p=1.00 | 61 | -1.8% (-23.2 to +20.9) |
| Lower-tier events | -0.03 (± 0.12) p=0.78 | +0.05 (± 0.12) p=0.65 | p=1.00 | 0 | – |
| Top-tier events | -0.13 (± 0.12) p=0.27 | -0.14 (± 0.13) p=0.28 | p=1.00 | 0 | – |
| Best of 5 | +0.22 (± 0.30) p=0.47 | -0.13 (± 0.29) p=0.66 | p=1.00 | 38 | -6.8% (-27.4 to +13.4) |
| Rest days | -0.04 (± 0.02) p=0.12 | -0.03 (± 0.02) p=0.24 | p=1.00 | 96 | +10.5% (-10.6 to +33.5) |

- **Favorite-longshot bias**: Are favorites under- or over-priced more the further from 50%? (feature: the price's log-odds)
- **Late price move**: Does the move from 1 h to 10 min before keep going (follow it) or reverse (fade it)?
- **Thin markets**: Is the favorite mispriced when the spread 10 min before is over 3¢?
- **Near coin flips**: Is the favorite mispriced when priced 50–55%?
- **Overnight matches (midnight–8am New York)**: Thin US trading hours
- **Teams beating their prices**: Do teams that beat (or missed) their prices in their last 10 matches keep doing so? (feature: fav's summed surprise minus dog's)
- **Recent form**: Last-5 win rate, favorite minus underdog
- **Rematch within 30 days**: Does the winner of their last meeting win more than priced? (+1 = favorite won it, −1 = underdog did)
- **Lower-tier events**: Challengers, Game Changers and other non-VCT events
- **Top-tier events**: VCT leagues, Masters, Champions, EWC
- **Best of 5**: Longer series favor the better team; is that priced?
- **Rest days**: Days since each team's previous vlr.gg match (capped at 14), favorite minus underdog

## CS2

Earlier half: 2706 matches before 2026-08-24. Later half: 2706 matches from then on.

| Idea | Earlier half: effect (± ) p | Later half: effect (±) p | After correcting for 8 ideas | Later-half bets | Avg return (90% range) |
|---|---|---|---|---|---|
| Favorite-longshot bias | +0.19 (± 0.09) p=0.03 | +0.21 (± 0.09) p=0.02 | p=0.15 | 3 | -54.6% (-100.0 to -9.2) |
| Late price move | +0.10 (± 0.20) p=0.63 | +0.08 (± 0.20) p=0.69 | p=1.00 | 6 | -26.0% (-77.6 to +25.3) |
| Thin markets | -0.01 (± 0.06) p=0.82 | +0.13 (± 0.06) p=0.05 | p=0.32 | 2 | -100.0% (-100.0 to -100.0) |
| Near coin flips | +0.01 (± 0.10) p=0.93 | +0.13 (± 0.10) p=0.21 | p=1.00 | 0 | – |
| Overnight matches (midnight–8am New York) | -0.02 (± 0.07) p=0.75 | -0.04 (± 0.08) p=0.59 | p=1.00 | 2 | -100.0% (-100.0 to -100.0) |
| Teams beating their prices | -0.04 (± 0.03) p=0.20 | +0.02 (± 0.02) p=0.39 | p=1.00 | 26 | -27.9% (-55.9 to -0.3) |
| Recent form | -0.10 (± 0.14) p=0.48 | +0.10 (± 0.14) p=0.49 | p=1.00 | 2 | -100.0% (-100.0 to -100.0) |
| Rematch within 30 days | -0.04 (± 0.15) p=0.81 | -0.08 (± 0.11) p=0.49 | p=1.00 | 1 | -100.0% (-100.0 to -100.0) |

- **Favorite-longshot bias**: Are favorites under- or over-priced more the further from 50%? (feature: the price's log-odds)
- **Late price move**: Does the move from 1 h to 10 min before keep going (follow it) or reverse (fade it)?
- **Thin markets**: Is the favorite mispriced when the spread 10 min before is over 3¢?
- **Near coin flips**: Is the favorite mispriced when priced 50–55%?
- **Overnight matches (midnight–8am New York)**: Thin US trading hours
- **Teams beating their prices**: Do teams that beat (or missed) their prices in their last 10 matches keep doing so? (feature: fav's summed surprise minus dog's)
- **Recent form**: Last-5 win rate, favorite minus underdog
- **Rematch within 30 days**: Does the winner of their last meeting win more than priced? (+1 = favorite won it, −1 = underdog did)

## LoL

Earlier half: 1112 matches before 2026-07-25. Later half: 1112 matches from then on.

| Idea | Earlier half: effect (± ) p | Later half: effect (±) p | After correcting for 8 ideas | Later-half bets | Avg return (90% range) |
|---|---|---|---|---|---|
| Favorite-longshot bias | +0.17 (± 0.12) p=0.16 | -0.01 (± 0.11) p=0.96 | p=1.00 | 0 | – |
| Late price move | +0.73 (± 0.29) p=0.01 | +0.18 (± 0.25) p=0.48 | p=1.00 | 101 | -5.5% (-18.5 to +7.8) |
| Thin markets | +0.14 (± 0.14) p=0.31 | +0.17 (± 0.18) p=0.34 | p=1.00 | 0 | – |
| Near coin flips | -0.00 (± 0.21) p=0.98 | +0.41 (± 0.19) p=0.03 | p=0.26 | 0 | – |
| Overnight matches (midnight–8am New York) | -0.04 (± 0.11) p=0.70 | +0.01 (± 0.13) p=0.93 | p=1.00 | 0 | – |
| Teams beating their prices | -0.10 (± 0.05) p=0.07 | -0.04 (± 0.04) p=0.37 | p=1.00 | 255 | -1.0% (-10.5 to +8.2) |
| Recent form | -0.02 (± 0.20) p=0.94 | -0.14 (± 0.23) p=0.54 | p=1.00 | 0 | – |
| Rematch within 30 days | -0.07 (± 0.18) p=0.72 | -0.11 (± 0.15) p=0.45 | p=1.00 | 70 | +0.4% (-14.4 to +15.4) |

- **Favorite-longshot bias**: Are favorites under- or over-priced more the further from 50%? (feature: the price's log-odds)
- **Late price move**: Does the move from 1 h to 10 min before keep going (follow it) or reverse (fade it)?
- **Thin markets**: Is the favorite mispriced when the spread 10 min before is over 3¢?
- **Near coin flips**: Is the favorite mispriced when priced 50–55%?
- **Overnight matches (midnight–8am New York)**: Thin US trading hours
- **Teams beating their prices**: Do teams that beat (or missed) their prices in their last 10 matches keep doing so? (feature: fav's summed surprise minus dog's)
- **Recent form**: Last-5 win rate, favorite minus underdog
- **Rematch within 30 days**: Does the winner of their last meeting win more than priced? (+1 = favorite won it, −1 = underdog did)

## Dota 2

Earlier half: 547 matches before 2026-08-15. Later half: 549 matches from then on.

| Idea | Earlier half: effect (± ) p | Later half: effect (±) p | After correcting for 8 ideas | Later-half bets | Avg return (90% range) |
|---|---|---|---|---|---|
| Favorite-longshot bias | +0.21 (± 0.20) p=0.29 | +0.30 (± 0.19) p=0.12 | p=0.93 | 32 | -10.8% (-42.2 to +20.5) |
| Late price move | -0.21 (± 0.41) p=0.62 | -0.55 (± 0.36) p=0.13 | p=0.93 | 3 | -35.6% (-100.0 to +28.8) |
| Thin markets | -0.39 (± 0.15) p=0.01 | +0.03 (± 0.16) p=0.83 | p=1.00 | 178 | -12.8% (-29.5 to +5.3) |
| Near coin flips | -0.39 (± 0.21) p=0.06 | +0.04 (± 0.28) p=0.88 | p=1.00 | 51 | -9.9% (-33.2 to +13.5) |
| Overnight matches (midnight–8am New York) | -0.08 (± 0.14) p=0.56 | +0.12 (± 0.16) p=0.45 | p=1.00 | 0 | – |
| Teams beating their prices | +0.06 (± 0.05) p=0.29 | +0.04 (± 0.06) p=0.53 | p=1.00 | 42 | -0.6% (-30.2 to +28.1) |
| Recent form | +0.55 (± 0.29) p=0.06 | +0.31 (± 0.32) p=0.33 | p=1.00 | 100 | -17.7% (-33.6 to -0.5) |
| Rematch within 30 days | -0.30 (± 0.26) p=0.26 | +0.13 (± 0.24) p=0.60 | p=1.00 | 24 | -14.5% (-39.9 to +10.4) |

- **Favorite-longshot bias**: Are favorites under- or over-priced more the further from 50%? (feature: the price's log-odds)
- **Late price move**: Does the move from 1 h to 10 min before keep going (follow it) or reverse (fade it)?
- **Thin markets**: Is the favorite mispriced when the spread 10 min before is over 3¢?
- **Near coin flips**: Is the favorite mispriced when priced 50–55%?
- **Overnight matches (midnight–8am New York)**: Thin US trading hours
- **Teams beating their prices**: Do teams that beat (or missed) their prices in their last 10 matches keep doing so? (feature: fav's summed surprise minus dog's)
- **Recent form**: Last-5 win rate, favorite minus underdog
- **Rematch within 30 days**: Does the winner of their last meeting win more than priced? (+1 = favorite won it, −1 = underdog did)
