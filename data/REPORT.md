# Paper test: Nov 05 03:46 to Nov 12 13:41 UTC

- Watched for about **171.5 hours** (13550 scans, one every ~45s).
- Matches listed on both venues per scan: **10.3** on average.
- Markets seen per scan: Kalshi 99, Polymarket US 21.
- Arbs: **77** appearances across **21** matches (CS2 61, Dota 2 4, League of Legends 12).
- After 2s (bot speed): fully fillable **47**, partly **6**, gone **24**; profit if placed then **$74.27**, about **$10.39 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **73**; profit if placed then **$28.64**, about **$4.01 per day watched**.
- How long they lasted: median 0s, longest 180s; 76 of 77 gone by the next scan.

**Verdict:** Promising: about $10.39 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $4.01 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **56868** posted across **206** matches (reposted each scan); average **$6.45** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **142** (0.2% of bids).
- Profit if hedged instantly (best case): **$137.32**, about **$19.21 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-111.39**, about **$-15.58 per day watched**.
- Fills that lose money when hedged late: **102**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $19.21 a day if the hedge goes in instantly, $-15.58 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
