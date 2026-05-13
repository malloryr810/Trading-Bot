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

## Rating Thresholds (placeholder)

| Composite score | Rating      |
|-----------------|-------------|
| 80–100          | Strong Buy  |
| 65–79           | Buy         |
| 45–64           | Hold        |
| 30–44           | Sell        |
| 0–29            | Strong Sell |

## Risk Override

Risk conditions can act as hard blockers regardless of composite score.
A `risk_block` flag on a `Signal` overrides a Buy rating to Hold,
and a Hold to Sell, until the condition clears.

## Notes

- Thresholds are initial estimates and should be tuned against historical data
- Weights are subject to change after backtesting (v3.0)
- Individual signal definitions will be documented inline in each analysis module
