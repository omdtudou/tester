# Paper test: Nov 05 03:46 to Nov 09 20:28 UTC

- Watched for about **110.6 hours** (8781 scans, one every ~45s).
- Matches listed on both venues per scan: **8.1** on average.
- Markets seen per scan: Kalshi 103, Polymarket US 21.
- Arbs: **65** appearances across **15** matches (CS2 51, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **44**, partly **4**, gone **17**; profit if placed then **$60.97**, about **$13.23 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **61**; profit if placed then **$28.64**, about **$6.22 per day watched**.
- How long they lasted: median 0s, longest 180s; 64 of 65 gone by the next scan.

**Verdict:** Promising: about $13.23 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $6.22 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **27681** posted across **120** matches (reposted each scan); average **$7.39** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **127** (0.5% of bids).
- Profit if hedged instantly (best case): **$126.11**, about **$27.37 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-91.58**, about **$-19.88 per day watched**.
- Fills that lose money when hedged late: **93**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $27.37 a day if the hedge goes in instantly, $-19.88 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
