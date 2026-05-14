# Investment Bot

A modular, personal stock analysis and decision-support tool built in Python.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> All output should be treated as a starting point for your own due diligence.

---

## Purpose

Analyze individual stocks using market data, technical indicators, fundamentals,
news sentiment, and risk signals — then produce a structured, scored report to
support personal investment decisions.

## What Is Implemented

| Module | Description |
|--------|-------------|
| `app/data/market_data.py` | Fetches and validates historical OHLCV price data via yfinance |
| `app/analysis/technicals.py` | Computes SMA, RSI, MACD, volume SMA, daily return; produces a signal summary |
| `app/models/signal.py` | Typed `Signal` Pydantic model with enums for category, direction, and strength |
| `app/analysis/technicals.py` — `build_technical_signals` | Converts a technical summary dict into 7 typed `Signal` objects |
| `app/models/rating.py` | Typed `Rating` model that the scoring engine returns |
| `app/analysis/scoring.py` | Technical-only scoring from `Signal` objects into a `Rating` |
| `app/main.py` | CLI entry point — runs the full pipeline and prints a terminal summary |

All implemented modules have unit test coverage with no live API calls.

## Running the CLI

```bash
python -m app.main AAPL
```

Output is a technical-only analysis. Fundamentals, news, and risk are not yet included. This tool does not place trades.

## What Is Not Yet Implemented

- Fundamental analysis
- News / sentiment analysis
- Risk analysis
- Composite scoring engine
- Report generation
- Trading of any kind

## Data Flow

```
app/data/ → app/analysis/ → app/analysis/scoring.py → app/reports/
```

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
from app.analysis.technicals import calculate_technical_indicators, summarize_technical_signals

# Fetch one year of daily OHLCV data
price_data = get_price_history("AAPL")

# Add technical indicator columns to the DataFrame
indicators = calculate_technical_indicators(price_data)

# Get a summary dict of the latest signals
summary = summarize_technical_signals(indicators)
print(summary["trend"])          # "bullish" | "bearish" | "mixed"
print(summary["rsi_condition"])  # "overbought" | "oversold" | "neutral"
print(summary["macd_condition"]) # "bullish" | "bearish" | "neutral"
```

## Project Structure

```
app/
  main.py          # CLI entry point
  config.py        # Env-var settings via python-dotenv
  data/            # Data fetchers — market_data.py implemented
  analysis/        # Analysis modules — technicals.py, scoring.py implemented
  reports/         # Report rendering (not yet implemented)
  models/          # Shared Pydantic models — signal.py, rating.py implemented
  utils/           # Logging and helpers
tests/             # pytest suite (41 tests, no live API calls)
data/
  raw/             # Cached API responses (git-ignored)
  processed/       # Cleaned data (git-ignored)
  reports/         # Generated reports (git-ignored)
docs/              # Architecture, scoring rules, data sources, development log
prompts/           # Claude prompts used during development
```

See `docs/architecture.md` for the full layer design and `docs/scoring_rules.md`
for the planned composite score formula.

## What Future Versions May Add

- Fundamental and news/sentiment analysis
- Composite scoring (Technical 35% · Fundamental 25% · News 25% · Risk 15%)
- Watchlist scanning across multiple tickers
- Backtesting signals against historical price data
- Paper trading simulation
