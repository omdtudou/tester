# Paper test: Nov 05 03:46 to Nov 08 19:15 UTC

- Watched for about **86.6 hours** (6874 scans, one every ~45s).
- Matches listed on both venues per scan: **8.2** on average.
- Markets seen per scan: Kalshi 107, Polymarket US 22.
- Arbs: **33** appearances across **10** matches (CS2 26, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **24**, partly **1**, gone **8**; profit if placed then **$30.23**, about **$8.37 per day watched**.
- After 20s (by hand): fully fillable **2**, partly **0**, gone **31**; profit if placed then **$0.10**, about **$0.03 per day watched**.
- How long they lasted: median 0s, longest 180s; 32 of 33 gone by the next scan.

**Verdict:** Small but real: about $8.37 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.03 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23498** posted across **95** matches (reposted each scan); average **$8.08** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **80** (0.3% of bids).
- Profit if hedged instantly (best case): **$67.99**, about **$18.83 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-18.88**, about **$-5.23 per day watched**.
- Fills that lose money when hedged late: **55**; couldn't fully hedge: **2**.

**Maker verdict:** Depends on hedging speed: about $18.83 a day if the hedge goes in instantly, $-5.23 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
