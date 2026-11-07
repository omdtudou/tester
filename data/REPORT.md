# Paper test: Nov 05 03:46 to Nov 07 21:55 UTC

- Watched for about **65.3 hours** (5174 scans, one every ~45s).
- Matches listed on both venues per scan: **8.9** on average.
- Markets seen per scan: Kalshi 105, Polymarket US 22.
- Arbs: **26** appearances across **6** matches (CS2 20, Dota 2 2, League of Legends 4).
- After 2s (bot speed): fully fillable **19**, partly **0**, gone **7**; profit if placed then **$21.01**, about **$7.72 per day watched**.
- After 20s (by hand): fully fillable **1**, partly **0**, gone **25**; profit if placed then **$0.09**, about **$0.03 per day watched**.
- How long they lasted: median 0s, longest 180s; 25 of 26 gone by the next scan.

**Verdict:** Small but real: about $7.72 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.03 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **19821** posted across **74** matches (reposted each scan); average **$8.67** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **72** (0.4% of bids).
- Profit if hedged instantly (best case): **$65.51**, about **$24.07 per day watched**.
- Profit if hedged when spotted (worst case, median 27s after the fill): **$-62.26**, about **$-22.88 per day watched**.
- Fills that lose money when hedged late: **49**; couldn't fully hedge: **1**.

**Maker verdict:** Depends on hedging speed: about $24.07 a day if the hedge goes in instantly, $-22.88 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
