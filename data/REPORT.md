# Paper test: Nov 05 03:46 to Nov 12 08:26 UTC

- Watched for about **166.4 hours** (13155 scans, one every ~45s).
- Matches listed on both venues per scan: **10.0** on average.
- Markets seen per scan: Kalshi 98, Polymarket US 21.
- Arbs: **74** appearances across **19** matches (CS2 60, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **47**, partly **5**, gone **22**; profit if placed then **$74.22**, about **$10.70 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **70**; profit if placed then **$28.64**, about **$4.13 per day watched**.
- How long they lasted: median 0s, longest 180s; 73 of 74 gone by the next scan.

**Verdict:** Promising: about $10.70 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $4.13 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **53601** posted across **205** matches (reposted each scan); average **$6.11** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **139** (0.3% of bids).
- Profit if hedged instantly (best case): **$134.99**, about **$19.47 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-93.91**, about **$-13.54 per day watched**.
- Fills that lose money when hedged late: **99**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $19.47 a day if the hedge goes in instantly, $-13.54 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
