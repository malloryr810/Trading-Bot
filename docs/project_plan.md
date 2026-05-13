# Project Plan

## Goal

Build a modular, personal investment analysis tool that produces structured
decision-support reports for individual stocks. The system is a research
assistant, not an automated trading system.

## Version 1 — Single-Ticker Report MVP

- Accept a ticker symbol as input
- Fetch price history and basic fundamentals via yfinance
- Compute a small set of technical indicators (SMA, RSI)
- Run a lightweight fundamental check (P/E, EPS trend)
- Aggregate into a composite score using the weighted formula in `scoring_rules.md`
- Output a plain-text or Markdown report to `data/reports/`

Success criteria: running `python app/main.py --ticker AAPL` produces a
readable, structured report with a clear Buy / Hold / Sell recommendation
and the reasoning behind it.

## Future Expansion

| Phase | Capability |
|-------|-----------|
| v1.1 | News and sentiment scoring via a news API |
| v1.2 | Risk analysis (volatility, beta, sector exposure) |
| v2.0 | Watchlist scanning — run analysis across a list of tickers |
| v2.1 | Scheduled reports (daily digest) |
| v3.0 | Backtesting framework against historical signals |
| v3.1 | Paper trading simulation with performance tracking |
| v4.0 | Live trading with strict position-size and drawdown guardrails |

Phases v3+ require additional review before implementation.
