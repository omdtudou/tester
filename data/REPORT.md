# Paper test: Nov 05 03:46 to Nov 10 19:49 UTC

- Watched for about **133.9 hours** (10598 scans, one every ~45s).
- Matches listed on both venues per scan: **9.2** on average.
- Markets seen per scan: Kalshi 103, Polymarket US 21.
- Arbs: **67** appearances across **16** matches (CS2 53, Dota 2 2, League of Legends 12).
- After 2s (bot speed): fully fillable **45**, partly **4**, gone **18**; profit if placed then **$61.20**, about **$10.97 per day watched**.
- After 20s (by hand): fully fillable **4**, partly **0**, gone **63**; profit if placed then **$28.64**, about **$5.13 per day watched**.
- How long they lasted: median 0s, longest 180s; 66 of 67 gone by the next scan.

**Verdict:** Promising: about $10.97 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $5.13 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **41946** posted across **153** matches (reposted each scan); average **$6.62** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **132** (0.3% of bids).
- Profit if hedged instantly (best case): **$128.53**, about **$23.03 per day watched**.
- Profit if hedged when spotted (worst case, median 28s after the fill): **$-98.16**, about **$-17.59 per day watched**.
- Fills that lose money when hedged late: **96**; couldn't fully hedge: **3**.

**Maker verdict:** Depends on hedging speed: about $23.03 a day if the hedge goes in instantly, $-17.59 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
