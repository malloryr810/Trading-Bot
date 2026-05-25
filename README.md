# Investment Bot

A modular, personal stock analysis and decision-support tool built in Python.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> All output should be treated as a starting point for your own due diligence.

---

## Purpose

Analyze individual stocks using market data, technical indicators, company
fundamentals, news sentiment, and risk signals — then produce a structured,
scored plain-text research report to support personal investment decisions.

## What Is Implemented

| Module | Description |
|--------|-------------|
| `app/data/market_data.py` | Fetches and validates historical OHLCV price data via yfinance |
| `app/data/fundamentals.py` | Fetches company fundamentals (P/E, margins, growth, D/E, FCF, beta) via yfinance |
| `app/data/news_data.py` | Fetches recent news headlines via yfinance; returns typed `NewsItem` objects |
| `app/data/storage.py` | Saves plain-text reports (`.txt`) and structured results (`.json`) to local disk |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/models/fundamentals.py` | Typed `CompanyFundamentals` Pydantic model |
| `app/models/news.py` | Typed `NewsItem` Pydantic model |
| `app/analysis/technicals.py` | Computes SMA 20/50/200, RSI 14, MACD, volume SMA; produces 7 typed Signals |
| `app/analysis/fundamentals_analysis.py` | Produces 5 typed Signals from valuation, profitability, growth, debt, and cash flow |
| `app/analysis/news_analysis.py` | Produces 3 typed NEWS Signals via keyword matching (sentiment, risk headlines, coverage) |
| `app/analysis/risk_analysis.py` | Produces 4–5 typed Signals from volatility, drawdown, trend, liquidity, and beta |
| `app/analysis/scoring.py` | Composite scoring engine; weights Technical 35%, Fundamental 25%, News 25%, Risk 15% |
| `app/reports/stock_report.py` | Generates a formatted plain-text research report from a Rating and its Signals |
| `app/main.py` | CLI entry point — orchestrates the full pipeline and prints the report |

All implemented modules have full unit test coverage with no live API calls (812 tests).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the CLI

```bash
# Print report to terminal
python -m app.main AAPL

# Save plain-text report to outputs/reports/
python -m app.main AAPL --save-report

# Save structured JSON result to outputs/results/
python -m app.main AAPL --save-json

# Save both
python -m app.main AAPL --save-report --save-json
```

Output is a full composite research report covering technical, fundamental, news
sentiment, and risk analysis. This tool does not place trades.

## Running Tests

```bash
pytest
```

## Data Flow

```
app/data/ → app/analysis/ → app/analysis/scoring.py → app/reports/
```

Each layer has one job: data modules fetch and validate, analysis modules produce
signals, scoring aggregates signals into a Rating, reports format the Rating for output.

## Scoring

The composite score is a weighted average of active signal categories, re-normalised
to 100% when a category has no signals. Base weights:

| Category | Base Weight |
|----------|-------------|
| Technical | 35% |
| Fundamental | 25% |
| News | 25% |
| Risk | 15% |

Each signal contributes a `score_impact` in `[-1.0, 1.0]`. Impacts are summed,
clamped to `[-1, 1]`, then scaled to `[0, 100]` via `50 + impact × 50`.

Score-to-category thresholds:

| Score | Rating Category |
|-------|----------------|
| ≥ 85 | Strong Buy Candidate |
| ≥ 70 | Buy Candidate |
| ≥ 55 | Watchlist |
| ≥ 45 | Hold |
| ≥ 30 | Avoid |
| < 30 | Sell / Exit Warning |

## Project Structure

```
app/
  main.py                          # CLI entry point
  config.py                        # Env-var settings via python-dotenv
  data/
    market_data.py                 # OHLCV price history
    fundamentals.py                # Company fundamentals
    news_data.py                   # Recent news headlines
    storage.py                     # Saves reports and JSON results to disk
  analysis/
    technicals.py                  # Technical indicators and signals
    fundamentals_analysis.py       # Fundamental signals
    news_analysis.py               # News sentiment signals
    risk_analysis.py               # Risk signals
    scoring.py                     # Composite scoring engine
  reports/
    stock_report.py                # Plain-text report generator
    report_generator.py            # Stub — full report orchestration (not yet implemented)
    templates.py                   # Stub — report templates (not yet implemented)
  models/
    signal.py                      # Signal Pydantic model
    rating.py                      # Rating Pydantic model
    fundamentals.py                # CompanyFundamentals Pydantic model
    news.py                        # NewsItem Pydantic model
    stock_report.py                # Stub — top-level StockReport model (not yet implemented)
tests/                             # pytest suite (812 tests, no live API calls)
docs/                              # Architecture, scoring rules, data sources, dev log
```

## What Is Not Included (By Design)

This project intentionally does not implement:

- Live or paper trading
- Broker API integrations
- Order execution of any kind
- Automatic position management
- Margin or options trading
- Portfolio automation
- Watchlist scanning (planned, not yet built)
- Backtesting (planned, not yet built)
- ML/LLM sentiment models
- Database or cloud storage
