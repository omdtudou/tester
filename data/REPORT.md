# Paper test: Nov 05 03:46 to Nov 10 12:29 UTC

- Watched for about **126.6 hours** (10028 scans, one every ~45s).
- Matches listed on both venues per scan: **9.0** on average.
- Markets seen per scan: Kalshi 103, Polymarket US 21.
- Arbs: **66** appearances across **15** matches (CS2 52, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **44**, partly **4**, gone **18**; profit if placed then **$60.97**, about **$11.56 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **62**; profit if placed then **$28.64**, about **$5.43 per day watched**.
- How long they lasted: median 0s, longest 180s; 65 of 66 gone by the next scan.

**Verdict:** Promising: about $11.56 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $5.43 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **37728** posted across **150** matches (reposted each scan); average **$6.99** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **129** (0.3% of bids).
- Profit if hedged instantly (best case): **$128.05**, about **$24.27 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-97.91**, about **$-18.56 per day watched**.
- Fills that lose money when hedged late: **95**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $24.27 a day if the hedge goes in instantly, $-18.56 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
