# Paper test: Nov 05 03:46 to Nov 11 18:08 UTC

- Watched for about **154.6 hours** (12226 scans, one every ~45s).
- Matches listed on both venues per scan: **9.6** on average.
- Markets seen per scan: Kalshi 99, Polymarket US 21.
- Arbs: **70** appearances across **18** matches (CS2 56, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **46**, partly **5**, gone **19**; profit if placed then **$63.37**, about **$9.84 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **66**; profit if placed then **$28.64**, about **$4.45 per day watched**.
- How long they lasted: median 0s, longest 180s; 69 of 70 gone by the next scan.

**Verdict:** Small but real: about $9.84 a day, if a bot places each one within 2s. Probably not worth the risk of automating two-venue trades for this. By hand (20s) it would be about $4.45 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **48949** posted across **172** matches (reposted each scan); average **$6.15** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **139** (0.3% of bids).
- Profit if hedged instantly (best case): **$134.99**, about **$20.96 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-93.91**, about **$-14.58 per day watched**.
- Fills that lose money when hedged late: **99**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $20.96 a day if the hedge goes in instantly, $-14.58 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
