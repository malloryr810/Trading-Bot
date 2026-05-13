# Investment Bot

A modular, personal stock analysis and decision-support tool built in Python.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> All output should be treated as a starting point for your own due diligence.

---

## Purpose

Analyze individual stocks using market data, technical indicators, fundamentals,
news sentiment, and risk signals — then produce a structured report with a
scored recommendation.

## Current Scope (v1)

- Single-ticker analysis run from the command line
- Data fetched via yfinance (no paid API required to start)
- Composite score across four weighted categories (technical, fundamental, news, risk)
- Plain-text / Markdown report written to `data/reports/`

## What Future Versions May Add

- Watchlist scanning across multiple tickers
- Scheduled daily digest reports
- Backtesting signals against historical price data
- Paper trading simulation with performance tracking
- Live trading with strict guardrails (position size limits, drawdown stops)

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd Trading-Bot

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in any API keys you want to use
```

## Usage

```bash
# Run the placeholder entry point
python app/main.py
```

Full CLI usage (e.g. `--ticker AAPL`) will be documented once the first
analysis module is implemented.

## Project Structure

```
app/
  main.py                  # Entry point
  config.py                # Env-var-based settings
  data/                    # Data fetchers (market, fundamentals, news)
  analysis/                # Signal generators (technicals, fundamentals, news, risk, scoring)
  reports/                 # Report renderer and templates
  models/                  # Shared Pydantic models (Signal, Rating, StockReport)
  utils/                   # Logging and general helpers
tests/                     # pytest test suite
data/
  raw/                     # Cached API responses (git-ignored)
  processed/               # Cleaned data (git-ignored)
  reports/                 # Generated reports (git-ignored)
notebooks/                 # Exploratory analysis
docs/                      # Project plan, architecture, scoring rules, data sources
prompts/                   # Claude prompts used during development
```

See `docs/architecture.md` for a full description of the layer design.
