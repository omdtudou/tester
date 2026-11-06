# Paper test: Nov 05 03:46 to Nov 06 13:59 UTC

- Watched for about **33.4 hours** (2657 scans, one every ~45s).
- Matches listed on both venues per scan: **8.8** on average.
- Markets seen per scan: Kalshi 100, Polymarket US 22.
- Arbs: **19** appearances across **3** matches (CS2 13, Dota 2 2, League of Legends 4).
- After 2s (bot speed): fully fillable **14**, partly **0**, gone **5**; profit if placed then **$18.97**, about **$13.64 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **19**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 180s; 18 of 19 gone by the next scan.

**Verdict:** Promising: about $13.64 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **6937** posted across **27** matches (reposted each scan); average **$9.82** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **43** (0.6% of bids).
- Profit if hedged instantly (best case): **$50.15**, about **$36.06 per day watched**.
- Profit if hedged when spotted (worst case, median 29s after the fill): **$-86.89**, about **$-62.48 per day watched**.
- Fills that lose money when hedged late: **31**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $36.06 a day if the hedge goes in instantly, $-62.48 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
