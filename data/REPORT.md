# Paper test: Nov 05 03:46 to Nov 08 20:58 UTC

- Watched for about **88.4 hours** (7013 scans, one every ~45s).
- Matches listed on both venues per scan: **8.1** on average.
- Markets seen per scan: Kalshi 107, Polymarket US 22.
- Arbs: **45** appearances across **11** matches (CS2 38, Dota 2 2, League of Legends 5).
- After 2s (bot speed): fully fillable **30**, partly **3**, gone **12**; profit if placed then **$43.61**, about **$11.85 per day watched**.
- After 20s (by hand): fully fillable **3**, partly **0**, gone **42**; profit if placed then **$2.12**, about **$0.58 per day watched**.
- How long they lasted: median 0s, longest 180s; 44 of 45 gone by the next scan.

**Verdict:** Promising: about $11.85 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $0.58 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **23608** posted across **95** matches (reposted each scan); average **$8.05** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **93** (0.4% of bids).
- Profit if hedged instantly (best case): **$85.07**, about **$23.11 per day watched**.
- Profit if hedged when spotted (worst case, median 27s after the fill): **$-43.84**, about **$-11.91 per day watched**.
- Fills that lose money when hedged late: **65**; couldn't fully hedge: **2**.

**Maker verdict:** Depends on hedging speed: about $23.11 a day if the hedge goes in instantly, $-11.91 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
