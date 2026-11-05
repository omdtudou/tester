# Paper test: Nov 05 03:46 to Nov 05 08:45 UTC

- Watched for about **4.5 hours** (360 scans, one every ~45s).
- Matches listed on both venues per scan: **12.0** on average.
- Markets seen per scan: Kalshi 110, Polymarket US 23.
- Arbs: **0** appearances across **0** matches.

**Verdict:** Too early to tell: only 4.5 hours watched. Give it at least a day, ideally a week that includes a big tournament.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **1043** posted across **8** matches (reposted each scan); average **$14.29** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **0** (0.0% of bids).

**Maker verdict:** Too early to tell.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
