# Paper test: Nov 05 03:46 to Nov 12 15:08 UTC

- Watched for about **173.0 hours** (13660 scans, one every ~45s).
- Matches listed on both venues per scan: **10.3** on average.
- Markets seen per scan: Kalshi 99, Polymarket US 21.
- Arbs: **84** appearances across **22** matches (CS2 61, Dota 2 11, League of Legends 12).
- After 2s (bot speed): fully fillable **52**, partly **6**, gone **26**; profit if placed then **$91.55**, about **$12.70 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **80**; profit if placed then **$28.64**, about **$3.97 per day watched**.
- How long they lasted: median 0s, longest 180s; 83 of 84 gone by the next scan.

**Verdict:** Promising: about $12.70 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $3.97 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **57487** posted across **208** matches (reposted each scan); average **$6.41** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **149** (0.3% of bids).
- Profit if hedged instantly (best case): **$139.92**, about **$19.41 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-132.45**, about **$-18.38 per day watched**.
- Fills that lose money when hedged late: **109**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $19.41 a day if the hedge goes in instantly, $-18.38 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
