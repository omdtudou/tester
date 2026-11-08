# Paper test: Nov 05 03:46 to Nov 08 10:48 UTC

- Watched for about **78.2 hours** (6194 scans, one every ~45s).
- Matches listed on both venues per scan: **8.7** on average.
- Markets seen per scan: Kalshi 108, Polymarket US 22.
- Arbs: **27** appearances across **7** matches (CS2 20, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **19**, partly **0**, gone **8**; profit if placed then **$21.01**, about **$6.45 per day watched**.
- After 20s (by hand): fully fillable **1**, partly **0**, gone **26**; profit if placed then **$0.09**, about **$0.03 per day watched**.
- How long they lasted: median 0s, longest 180s; 26 of 27 gone by the next scan.

**Verdict:** Small but real: about $6.45 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $0.03 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **22876** posted across **90** matches (reposted each scan); average **$8.18** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **78** (0.3% of bids).
- Profit if hedged instantly (best case): **$67.98**, about **$20.87 per day watched**.
- Profit if hedged when spotted (worst case, median 27s after the fill): **$-18.72**, about **$-5.75 per day watched**.
- Fills that lose money when hedged late: **53**; couldn't fully hedge: **2**.

**Maker verdict:** Depends on hedging speed: about $20.87 a day if the hedge goes in instantly, $-5.75 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
