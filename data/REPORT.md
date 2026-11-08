# Paper test: Nov 05 03:46 to Nov 08 20:28 UTC

- Watched for about **87.9 hours** (6973 scans, one every ~45s).
- Matches listed on both venues per scan: **8.2** on average.
- Markets seen per scan: Kalshi 107, Polymarket US 22.
- Arbs: **42** appearances across **11** matches (CS2 35, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **28**, partly **2**, gone **12**; profit if placed then **$32.75**, about **$8.95 per day watched**.
- After 20s (by hand): fully fillable **3**, partly **0**, gone **39**; profit if placed then **$2.12**, about **$0.58 per day watched**.
- How long they lasted: median 0s, longest 180s; 41 of 42 gone by the next scan.

**Verdict:** Small but real: about $8.95 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.58 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23599** posted across **95** matches (reposted each scan); average **$8.05** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **89** (0.4% of bids).
- Profit if hedged instantly (best case): **$70.97**, about **$19.39 per day watched**.
- Profit if hedged when spotted (worst case, median 26s after the fill): **$-26.03**, about **$-7.11 per day watched**.
- Fills that lose money when hedged late: **62**; couldn't fully hedge: **2**.

**Maker verdict:** Depends on hedging speed: about $19.39 a day if the hedge goes in instantly, $-7.11 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
