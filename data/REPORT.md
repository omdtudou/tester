# Paper test: Nov 05 03:46 to Nov 12 18:14 UTC

- Watched for about **176.1 hours** (13898 scans, one every ~45s).
- Matches listed on both venues per scan: **10.4** on average.
- Markets seen per scan: Kalshi 99, Polymarket US 21.
- Arbs: **96** appearances across **24** matches (CS2 63, Dota 2 21, League of Legends 12).
- After 2s (bot speed): fully fillable **59**, partly **6**, gone **31**; profit if placed then **$133.68**, about **$18.22 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **92**; profit if placed then **$28.64**, about **$3.90 per day watched**.
- How long they lasted: median 0s, longest 180s; 94 of 96 gone by the next scan.

**Verdict:** Promising: about $18.22 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $3.90 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **58846** posted across **213** matches (reposted each scan); average **$6.28** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **169** (0.3% of bids).
- Profit if hedged instantly (best case): **$191.51**, about **$26.10 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-290.69**, about **$-39.62 per day watched**.
- Fills that lose money when hedged late: **123**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $26.10 a day if the hedge goes in instantly, $-39.62 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
