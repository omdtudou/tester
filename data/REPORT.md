# Paper test: Nov 05 03:32 to Nov 05 03:39 UTC

- Watched for about **0.1 hours** (10 scans, one every ~45s).
- Matches listed on both venues per scan: **0.0** on average.
- Markets seen per scan: Kalshi 108, Polymarket US 0.
- Arbs: **0** appearances across **0** matches.

**Verdict:** The scanner almost never found the same match on both venues, so there was nothing to compare. Run `--probe` to see why (usually team names or a market format change).

Assumes both limit orders fill together at the slip prices. In practice you place one leg after the other, so real results will be a bit worse. Arbs that appear between scans aren't counted.
