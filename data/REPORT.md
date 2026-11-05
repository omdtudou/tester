# Paper test: Nov 05 03:46 to Nov 05 22:17 UTC

- Watched for about **17.9 hours** (1427 scans, one every ~45s).
- Matches listed on both venues per scan: **8.9** on average.
- Markets seen per scan: Kalshi 105, Polymarket US 21.
- Arbs: **14** appearances across **5** matches (CS2 13, Dota 2 1).
- After 2s (bot speed): fully fillable **12**, partly **0**, gone **2**; profit if placed then **$15.17**, about **$20.32 per day watched**.
- After 20s (by hand): fully fillable **0**, partly **0**, gone **14**; profit if placed then **$0.00**, about **$0.00 per day watched**.
- How long they lasted: median 0s, longest 180s; 13 of 14 gone by the next scan.

**Verdict:** Promising: about $20.32 a day, if a bot places each one within 2s. Worth building the automated version carefully and starting with small stakes. By hand (20s) it would be about $0.00 a day.

## Maker strategy (simulated)

- Resting Kalshi bids that would lock a profit if hedged: **3933** posted across **15** matches (reposted each scan); average **$13.84** locked per bid if fully filled.
- Filled (someone sold into the bid before the next scan): **24** (0.6% of bids).
- Profit if hedged instantly (best case): **$34.69**, about **$46.47 per day watched**.
- Profit if hedged when spotted (worst case, median 26s after the fill): **$-72.78**, about **$-97.50 per day watched**.
- Fills that lose money when hedged late: **16**; couldn't fully hedge: **0**.

**Maker verdict:** Depends on hedging speed: about $46.47 a day if the hedge goes in instantly, $-97.50 if it lags. Only worth building if the bot hedges within a second.

Fills are judged from Kalshi's public trade history: a bid counts as filled when a seller traded at or below its price. That's optimistic about getting filled (the bid is assumed first in line) and pessimistic about the hedge (spotted up to one scan late).

Assumes both limit orders fill together at the slip prices. In practice one leg goes in before the other, so real results will be a bit worse. Arbs that appear and vanish between scans (every ~45s) aren't counted, so a fast bot could catch some this test misses.
