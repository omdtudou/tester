# Paper test: Nov 05 03:46 to Nov 09 13:44 UTC

- Watched for about **104.7 hours** (8322 scans, one every ~45s).
- Matches listed on both venues per scan: **8.1** on average.
- Markets seen per scan: Kalshi 104, Polymarket US 21.
- Arbs: **53** appearances across **12** matches (CS2 39, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **36**, partly **4**, gone **13**; profit if placed then **$52.43**, about **$12.01 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **49**; profit if placed then **$28.64**, about **$6.56 per day watched**.
- How long they lasted: median 0s, longest 180s; 52 of 53 gone by the next scan.

**Verdict:** Promising: about $12.01 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $6.56 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **26521** posted across **115** matches (reposted each scan); average **$7.62** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **106** (0.4% of bids).
- Profit if hedged instantly (best case): **$113.97**, about **$26.12 per day watched**.
- Profit if hedged when spotted (worst case, median 29s after the fill): **$-52.39**, about **$-12.01 per day watched**.
- Fills that lose money when hedged late: **76**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $26.12 a day if the hedge goes in instantly, $-12.01 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
