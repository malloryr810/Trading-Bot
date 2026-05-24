# Investment Bot

A modular, personal stock analysis and decision-support tool built in Python.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> All output should be treated as a starting point for your own due diligence.

---

## Purpose

Analyze individual stocks using market data, technical indicators, company
fundamentals, and risk signals — then produce a structured, scored plain-text
research report to support personal investment decisions.

## What Is Implemented

| Module | Description |
|--------|-------------|
| `app/data/market_data.py` | Fetches and validates historical OHLCV price data via yfinance |
| `app/data/fundamentals.py` | Fetches company fundamentals (P/E, margins, growth, D/E, FCF, beta) via yfinance |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/models/fundamentals.py` | Typed `CompanyFundamentals` Pydantic model |
| `app/analysis/technicals.py` | Computes SMA 20/50/200, RSI 14, MACD, volume SMA; produces 7 typed Signals |
| `app/analysis/fundamentals_analysis.py` | Produces 5 typed Signals from valuation, profitability, growth, debt, and cash flow |
| `app/analysis/risk_analysis.py` | Produces 4–5 typed Signals from volatility, drawdown, trend, liquidity, and beta |
| `app/analysis/scoring.py` | Composite scoring engine; weights Technical 35%, Fundamental 25%, Risk 15% |
| `app/reports/stock_report.py` | Generates a formatted plain-text research report from a Rating and its Signals |
| `app/main.py` | CLI entry point — orchestrates the full pipeline and prints the report |

All implemented modules have full unit test coverage with no live API calls (515 tests).

## Running the CLI

```bash
python -m app.main AAPL
```

Output is a full composite research report covering technical, fundamental, and risk
analysis. This tool does not place trades.

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
| Risk | 15% |
| News | Reserved (not yet active) |

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

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running Tests

```bash
pytest
```

## Usage Examples

```python
from app.data.market_data import get_price_history
from app.data.fundamentals import get_company_fundamentals
from app.analysis.technicals import (
    calculate_technical_indicators,
    summarize_technical_signals,
    build_technical_signals,
)
from app.analysis.fundamentals_analysis import build_fundamental_signals
from app.analysis.risk_analysis import analyze_risk_conditions
from app.analysis.scoring import score_signals
from app.reports.stock_report import generate_stock_report

# Fetch data
price_data   = get_price_history("AAPL")
fundamentals = get_company_fundamentals("AAPL")

# Build signals
tech_signals  = build_technical_signals(summarize_technical_signals(
                    calculate_technical_indicators(price_data)))
fund_signals  = build_fundamental_signals(fundamentals)
risk_signals  = analyze_risk_conditions(price_data, beta=fundamentals.beta)

# Score and report
rating = score_signals("AAPL", tech_signals + fund_signals + risk_signals)
report = generate_stock_report("AAPL", rating, rating.signals_used)
print(report)
```

## Project Structure

```
app/
  main.py                          # CLI entry point
  config.py                        # Env-var settings via python-dotenv
  data/
    market_data.py                 # OHLCV price history (implemented)
    fundamentals.py                # Company fundamentals (implemented)
    news_data.py                   # News/sentiment fetcher (stub)
    storage.py                     # Data persistence (stub)
  analysis/
    technicals.py                  # Technical indicators and signals (implemented)
    fundamentals_analysis.py       # Fundamental signals (implemented)
    risk_analysis.py               # Risk signals (implemented)
    scoring.py                     # Composite scoring engine (implemented)
    news_analysis.py               # News/sentiment signals (stub)
  reports/
    stock_report.py                # Plain-text report generator (implemented)
    report_generator.py            # Full report orchestration (stub)
    templates.py                   # Report templates (stub)
  models/
    signal.py                      # Signal Pydantic model (implemented)
    rating.py                      # Rating Pydantic model (implemented)
    fundamentals.py                # CompanyFundamentals Pydantic model (implemented)
    stock_report.py                # StockReport Pydantic model (stub)
tests/                             # pytest suite (515 tests, no live API calls)
docs/                              # Architecture, scoring rules, data sources, dev log
prompts/                           # Claude prompts used during development
```

## What Future Versions May Add

- News / sentiment analysis (wires into the reserved 25% NEWS weight)
- Watchlist scanning across multiple tickers
- Backtesting signals against historical price data
- Paper trading simulation
