# Paper test: Nov 05 03:46 to Nov 08 21:43 UTC

- Watched for about **89.1 hours** (7073 scans, one every ~45s).
- Matches listed on both venues per scan: **8.1** on average.
- Markets seen per scan: Kalshi 106, Polymarket US 22.
- Arbs: **46** appearances across **11** matches (CS2 39, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **31**, partly **3**, gone **12**; profit if placed then **$45.30**, about **$12.20 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **42**; profit if placed then **$28.64**, about **$7.71 per day watched**.
- How long they lasted: median 0s, longest 180s; 45 of 46 gone by the next scan.

**Verdict:** Promising: about $12.20 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $7.71 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23677** posted across **95** matches (reposted each scan); average **$8.02** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **95** (0.4% of bids).
- Profit if hedged instantly (best case): **$91.73**, about **$24.71 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$1.14**, about **$0.31 per day watched**.
- Fills that lose money when hedged late: **65**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $24.71 a day if the hedge goes in instantly, $0.31 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
