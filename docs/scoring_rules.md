# Scoring Rules

## Composite Score Formula

The final score is a weighted sum of four sub-scores, each normalized to 0–100.

| Category          | Weight | Source module              |
|-------------------|--------|---------------------------|
| Technical signals | 35%    | `analysis/technicals.py`  |
| Fundamental signals | 25%  | `analysis/fundamentals_analysis.py` |
| News / sentiment  | 25%    | `analysis/news_analysis.py` |
| Risk conditions   | 15%    | `analysis/risk_analysis.py` |

**Composite = (Tech × 0.35) + (Fund × 0.25) + (News × 0.25) + (Risk × 0.15)**

## Rating Thresholds (implemented)

These are the thresholds used by `app/analysis/scoring.py`:

| Score range | Category              |
|-------------|-----------------------|
| ≥ 85        | Strong Buy Candidate  |
| ≥ 70        | Buy Candidate         |
| ≥ 55        | Watchlist             |
| ≥ 45        | Hold                  |
| ≥ 30        | Avoid                 |
| < 30        | Sell / Exit Warning   |

Thresholds are initial estimates and may be tuned after backtesting.

## Risk Override (planned, not yet implemented)

Future versions may allow risk conditions to act as hard blockers regardless
of composite score (e.g., overriding a Buy to Hold until a condition clears).

## Notes

- Thresholds are initial estimates and should be tuned against historical data
- Weights are subject to change after backtesting (v3.0)
- Individual signal definitions will be documented inline in each analysis module
