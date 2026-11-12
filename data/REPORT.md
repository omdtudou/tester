# Paper test: Nov 05 03:46 to Nov 12 16:18 UTC

- Watched for about **174.1 hours** (13749 scans, one every ~45s).
- Matches listed on both venues per scan: **10.4** on average.
- Markets seen per scan: Kalshi 99, Polymarket US 21.
- Arbs: **91** appearances across **23** matches (CS2 61, Dota 2 18, League of Legends 12).
- After 2s (bot speed): fully fillable **56**, partly **6**, gone **29**; profit if placed then **$117.18**, about **$16.15 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **87**; profit if placed then **$28.64**, about **$3.95 per day watched**.
- How long they lasted: median 0s, longest 180s; 89 of 91 gone by the next scan.

**Verdict:** Promising: about $16.15 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $3.95 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **57902** posted across **208** matches (reposted each scan); average **$6.37** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **163** (0.3% of bids).
- Profit if hedged instantly (best case): **$154.31**, about **$21.27 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-181.27**, about **$-24.98 per day watched**.
- Fills that lose money when hedged late: **118**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $21.27 a day if the hedge goes in instantly, $-24.98 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
