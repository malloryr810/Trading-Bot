"""
Scoring engine.

Aggregates Signal objects from all analysis modules using the
weighted formula defined in docs/scoring_rules.md:
  Technical    35%
  Fundamental  25%
  News/Sentiment 25%
  Risk         15%

Produces a composite score and a final Rating for the StockReport.
"""
