# Paper test: Nov 05 03:46 to Nov 12 19:39 UTC

- Watched for about **177.5 hours** (14008 scans, one every ~45s).
- Matches listed on both venues per scan: **10.5** on average.
- Markets seen per scan: Kalshi 98, Polymarket US 21.
- Arbs: **102** appearances across **27** matches (CS2 69, Dota 2 21, League of Legends 12).
- After 2s (bot speed): fully fillable **60**, partly **6**, gone **36**; profit if placed then **$141.75**, about **$19.17 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **98**; profit if placed then **$28.64**, about **$3.87 per day watched**.
- How long they lasted: median 0s, longest 180s; 100 of 102 gone by the next scan.

**Verdict:** Promising: about $19.17 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $3.87 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **59651** posted across **215** matches (reposted each scan); average **$6.24** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **180** (0.3% of bids).
- Profit if hedged instantly (best case): **$196.90**, about **$26.62 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-294.97**, about **$-39.88 per day watched**.
- Fills that lose money when hedged late: **130**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $26.62 a day if the hedge goes in instantly, $-39.88 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
