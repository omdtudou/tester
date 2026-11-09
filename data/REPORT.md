# Paper test: Nov 05 03:46 to Nov 09 00:46 UTC

- Watched for about **92.0 hours** (7312 scans, one every ~45s).
- Matches listed on both venues per scan: **8.0** on average.
- Markets seen per scan: Kalshi 105, Polymarket US 21.
- Arbs: **49** appearances across **12** matches (CS2 39, Dota 2 2, League of Legends 8).
- After 2s (bot speed): fully fillable **33**, partly **3**, gone **13**; profit if placed then **$47.68**, about **$12.44 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **45**; profit if placed then **$28.64**, about **$7.47 per day watched**.
- How long they lasted: median 0s, longest 180s; 48 of 49 gone by the next scan.

**Verdict:** Promising: about $12.44 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $7.47 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23932** posted across **102** matches (reposted each scan); average **$8.11** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **100** (0.4% of bids).
- Profit if hedged instantly (best case): **$99.64**, about **$25.99 per day watched**.
- Profit if hedged when spotted (worst case, median 29s after the fill): **$-13.24**, about **$-3.45 per day watched**.
- Fills that lose money when hedged late: **70**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $25.99 a day if the hedge goes in instantly, $-3.45 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
