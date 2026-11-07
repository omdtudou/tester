# Paper test: Nov 05 03:46 to Nov 07 19:23 UTC

- Watched for about **62.8 hours** (4974 scans, one every ~45s).
- Matches listed on both venues per scan: **9.0** on average.
- Markets seen per scan: Kalshi 106, Polymarket US 22.
- Arbs: **24** appearances across **6** matches (CS2 18, Dota 2 2, League of Legends 4).
- After 2s (bot speed): fully fillable **17**, partly **0**, gone **7**; profit if placed then **$20.90**, about **$7.99 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **24**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 180s; 23 of 24 gone by the next scan.

**Verdict:** Small but real: about $7.99 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **19171** posted across **74** matches (reposted each scan); average **$8.83** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **54** (0.3% of bids).
- Profit if hedged instantly (best case): **$53.45**, about **$20.44 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-98.01**, about **$-37.47 per day watched**.
- Fills that lose money when hedged late: **39**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $20.44 a day if the hedge goes in instantly, $-37.47 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
