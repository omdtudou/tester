# Paper test: Nov 05 03:46 to Nov 09 19:42 UTC

- Watched for about **109.8 hours** (8721 scans, one every ~45s).
- Matches listed on both venues per scan: **8.1** on average.
- Markets seen per scan: Kalshi 103, Polymarket US 21.
- Arbs: **63** appearances across **15** matches (CS2 49, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **43**, partly **4**, gone **16**; profit if placed then **$60.72**, about **$13.27 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **59**; profit if placed then **$28.64**, about **$6.26 per day watched**.
- How long they lasted: median 0s, longest 180s; 62 of 63 gone by the next scan.

**Verdict:** Promising: about $13.27 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $6.26 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **27406** posted across **120** matches (reposted each scan); average **$7.43** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **121** (0.4% of bids).
- Profit if hedged instantly (best case): **$119.48**, about **$26.11 per day watched**.
- Profit if hedged when spotted (worst case, median 29s after the fill): **$-69.50**, about **$-15.19 per day watched**.
- Fills that lose money when hedged late: **88**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $26.11 a day if the hedge goes in instantly, $-15.19 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
