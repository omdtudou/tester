# Paper test: Nov 05 03:46 to Nov 05 20:46 UTC

- Watched for about **16.4 hours** (1307 scans, one every ~45s).
- Matches listed on both venues per scan: **9.1** on average.
- Markets seen per scan: Kalshi 107, Polymarket US 21.
- Arbs: **11** appearances across **5** matches (CS2 10, Dota 2 1).
- After 2s (bot speed): fully fillable **9**, partly **0**, gone **2**; profit if placed then **$5.03**, about **$7.36 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **11**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 0s; 11 of 11 gone by the next scan.

**Verdict:** Small but real: about $7.36 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **3786** posted across **15** matches (reposted each scan); average **$14.29** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **11** (0.3% of bids).
- Profit if hedged instantly (best case): **$14.32**, about **$20.94 per day watched**.
- Profit if hedged when spotted (worst case, median 22s after the fill): **$-8.61**, about **$-12.59 per day watched**.
- Fills that lose money when hedged late: **6**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $20.94 a day if the hedge goes in instantly, $-12.59 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
