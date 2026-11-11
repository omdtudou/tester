# Paper test: Nov 05 03:46 to Nov 11 19:41 UTC

- Watched for about **156.2 hours** (12346 scans, one every ~45s).
- Matches listed on both venues per scan: **9.7** on average.
- Markets seen per scan: Kalshi 98, Polymarket US 21.
- Arbs: **73** appearances across **18** matches (CS2 59, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **47**, partly **5**, gone **21**; profit if placed then **$74.22**, about **$11.41 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **69**; profit if placed then **$28.64**, about **$4.40 per day watched**.
- How long they lasted: median 0s, longest 180s; 72 of 73 gone by the next scan.

**Verdict:** Promising: about $11.41 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $4.40 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **49753** posted across **179** matches (reposted each scan); average **$6.17** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **139** (0.3% of bids).
- Profit if hedged instantly (best case): **$134.99**, about **$20.75 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-93.91**, about **$-14.43 per day watched**.
- Fills that lose money when hedged late: **99**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $20.75 a day if the hedge goes in instantly, $-14.43 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
