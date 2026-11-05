# Paper test: Nov 05 03:46 to Nov 05 16:26 UTC

- Watched for about **12.1 hours** (960 scans, one every ~45s).
- Matches listed on both venues per scan: **9.6** on average.
- Markets seen per scan: Kalshi 110, Polymarket US 21.
- Arbs: **0** appearances across **0** matches.

**Verdict:** No arbs in 12 hours of watching. On this evidence it isn't worth running live.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **3394** posted across **13** matches (reposted each scan); average **$15.71** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **0** (0.0% of bids).

**Maker verdict:** No resting bid got filled at a profitable price, so the maker version doesn't look worth building on this data.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
