# Paper test: Nov 05 03:46 to Nov 07 12:01 UTC

- Watched for about **55.4 hours** (4395 scans, one every ~45s).
- Matches listed on both venues per scan: **9.0** on average.
- Markets seen per scan: Kalshi 104, Polymarket US 22.
- Arbs: **19** appearances across **3** matches (CS2 13, Dota 2 2, League of Legends 4).
- After 2s (bot speed): fully fillable **14**, partly **0**, gone **5**; profit if placed then **$18.97**, about **$8.22 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **19**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 180s; 18 of 19 gone by the next scan.

**Verdict:** Small but real: about $8.22 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **16100** posted across **62** matches (reposted each scan); average **$9.47** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **48** (0.3% of bids).
- Profit if hedged instantly (best case): **$52.84**, about **$22.89 per day watched**.
- Profit if hedged when spotted (worst case, median 30s after the fill): **$-95.49**, about **$-41.36 per day watched**.
- Fills that lose money when hedged late: **36**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $22.89 a day if the hedge goes in instantly, $-41.36 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
