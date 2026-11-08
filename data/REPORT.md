# Paper test: Nov 05 03:46 to Nov 08 19:38 UTC

- Watched for about **87.0 hours** (6904 scans, one every ~45s).
- Matches listed on both venues per scan: **8.2** on average.
- Markets seen per scan: Kalshi 107, Polymarket US 22.
- Arbs: **36** appearances across **11** matches (CS2 29, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **25**, partly **1**, gone **10**; profit if placed then **$30.24**, about **$8.34 per day watched**.
- After 20s (by hand): fully fillable **2**, partly **0**, gone **34**; profit if placed then **$0.10**, about **$0.03 per day watched**.
- How long they lasted: median 0s, longest 180s; 35 of 36 gone by the next scan.

**Verdict:** Small but real: about $8.34 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.03 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23552** posted across **95** matches (reposted each scan); average **$8.06** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **83** (0.4% of bids).
- Profit if hedged instantly (best case): **$68.63**, about **$18.93 per day watched**.
- Profit if hedged when spotted (worst case, median 26s after the fill): **$-21.19**, about **$-5.84 per day watched**.
- Fills that lose money when hedged late: **57**; couldn't fully hedge: **2**.

**Maker verdict:** Depends on hedging speed: about $18.93 a day if the hedge goes in instantly, $-5.84 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
