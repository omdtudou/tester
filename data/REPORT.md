# Paper test: Nov 05 03:46 to Nov 07 18:52 UTC

- Watched for about **62.3 hours** (4934 scans, one every ~45s).
- Matches listed on both venues per scan: **9.1** on average.
- Markets seen per scan: Kalshi 106, Polymarket US 22.
- Arbs: **23** appearances across **5** matches (CS2 17, Dota 2 2, League of Legends 4).
- After 2s (bot speed): fully fillable **17**, partly **0**, gone **6**; profit if placed then **$20.90**, about **$8.06 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **23**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 180s; 22 of 23 gone by the next scan.

**Verdict:** Small but real: about $8.06 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **18963** posted across **73** matches (reposted each scan); average **$8.88** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **53** (0.3% of bids).
- Profit if hedged instantly (best case): **$53.43**, about **$20.60 per day watched**.
- Profit if hedged when spotted (worst case, median 26s after the fill): **$-98.03**, about **$-37.79 per day watched**.
- Fills that lose money when hedged late: **39**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $20.60 a day if the hedge goes in instantly, $-37.79 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
