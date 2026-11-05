# Paper test: Nov 05 03:46 to Nov 05 18:27 UTC

- Watched for about **14.1 hours** (1120 scans, one every ~45s).
- Matches listed on both venues per scan: **9.4** on average.
- Markets seen per scan: Kalshi 109, Polymarket US 21.
- Arbs: **1** appearances across **1** matches (CS2 1).
- After 2s (bot speed): fully fillable **1**, partly **0**, gone **0**; profit if placed then **$1.12**, about **$1.91 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **1**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 0s; 1 of 1 gone by the next scan.

**Verdict:** Small but real: about $1.91 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **3608** posted across **13** matches (reposted each scan); average **$14.89** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **1** (0.0% of bids).
- Profit if hedged instantly (best case): **$1.85**, about **$3.15 per day watched**.
- Profit if hedged when spotted (worst case, median 22s after the fill): **$-0.66**, about **$-1.12 per day watched**.
- Fills that lose money when hedged late: **1**; couldn't fully hedge: **0**.

**Maker verdict:** Small: about $3.15 a day at best. Probably not worth the risk of automating it.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
