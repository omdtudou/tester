# Paper test: Nov 05 03:46 to Nov 05 19:25 UTC

- Watched for about **15.1 hours** (1199 scans, one every ~45s).
- Matches listed on both venues per scan: **9.3** on average.
- Markets seen per scan: Kalshi 109, Polymarket US 21.
- Arbs: **5** appearances across **3** matches (CS2 4, Dota 2 1).
- After 2s (bot speed): fully fillable **4**, partly **0**, gone **1**; profit if placed then **$2.06**, about **$3.28 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **5**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 0s; 5 of 5 gone by the next scan.

**Verdict:** Small but real: about $3.28 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **3663** posted across **15** matches (reposted each scan); average **$14.68** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **6** (0.2% of bids).
- Profit if hedged instantly (best case): **$3.83**, about **$6.10 per day watched**.
- Profit if hedged when spotted (worst case, median 20s after the fill): **$-0.46**, about **$-0.73 per day watched**.
- Fills that lose money when hedged late: **3**; couldn't fully hedge: **0**.

**Maker verdict:** Small: about $6.10 a day at best. Probably not worth the risk of automating it.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
