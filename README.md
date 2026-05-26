# Investment Bot

A modular, personal stock research and decision-support tool built in Python.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> All output should be treated as a starting point for your own due diligence,
> not as a recommendation to buy, sell, or hold any security.

---

## What It Does

Analyze individual stocks using market data, technical indicators, company
fundamentals, news sentiment, and risk signals — then produce a structured,
scored plain-text research report. Run a single ticker or scan an entire watchlist.

This tool prints reports. It does not place trades.

## Features

- **Technical analysis** — SMA 20/50/200, RSI 14, MACD, volume SMA; 7 typed signals
- **Fundamental analysis** — P/E, profit margin, revenue/EPS growth, debt-to-equity, free cash flow; 5 signals
- **News sentiment** — keyword-based sentiment, risk headline detection, coverage density; 3 signals
- **Risk analysis** — volatility, max drawdown, recent trend, liquidity, beta; 4–5 signals
- **Composite scoring** — weighted across all four signal categories; maps to a rated category
- **Structured StockReport model** — typed Pydantic output for downstream use or export
- **Plain-text reports** — terminal-readable, section-by-section output
- **Markdown reports** — clean Markdown documents for single tickers and watchlists (`--save-markdown`)
- **JSON export** — structured result files for single tickers and watchlists
- **Watchlist scanning** — analyze multiple tickers from a plain-text file; ranked summary table with company name and price
- **Watchlist export** — save watchlist summaries as plain text, Markdown, or JSON
- **Improved market data validation** — full OHLCV column, null-check, and numeric-type validation
- **argparse CLI** — full flag support including `--help`

## What Is Not Included (By Design)

This project intentionally does not implement:

- Live or paper trading
- Broker API integrations
- Order execution of any kind
- Automatic position management
- Margin or options trading
- Portfolio automation
- ML/LLM sentiment models
- Database or cloud storage
- Backtesting (planned for a future phase)

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the CLI

### Single-ticker analysis

```bash
# Print report to terminal
python -m app.main AAPL

# Save plain-text report to outputs/reports/
python -m app.main AAPL --save-report

# Save Markdown report to outputs/reports/
python -m app.main AAPL --save-markdown

# Save structured JSON result to outputs/results/
python -m app.main AAPL --save-json

# Save all three
python -m app.main AAPL --save-report --save-markdown --save-json
```

### Watchlist analysis

```bash
# Print ranked summary table to terminal
python -m app.main --watchlist watchlists/default.txt

# Save plain-text summary to outputs/reports/
python -m app.main --watchlist watchlists/default.txt --save-report

# Save Markdown report to outputs/reports/
python -m app.main --watchlist watchlists/default.txt --save-markdown

# Save JSON results to outputs/results/
python -m app.main --watchlist watchlists/default.txt --save-json
```

### Help

```bash
python -m app.main --help
```

### Watchlist file format

Plain text, one ticker per line. Blank lines and lines starting with `#` are ignored.
Tickers are normalized to uppercase and deduplicated automatically.

```
# My watchlist
AAPL
MSFT
NVDA

# More picks
GOOGL
AMZN
```

---

## Running Tests

```bash
pytest
```

All tests are deterministic — no live API calls.

---

## Architecture

```
app/data/ → app/analysis/ → app/analysis/scoring.py → app/reports/
```

| Layer | Responsibility |
|-------|---------------|
| `app/data/` | Fetch and validate raw data; return typed models or DataFrames |
| `app/analysis/` | Compute independent signal lists from data |
| `app/analysis/scoring.py` | Aggregate signals into a composite Rating |
| `app/reports/` | Format a Rating into a human-readable report |
| `app/watchlist.py` | Orchestrate the pipeline across multiple tickers |
| `app/main.py` | argparse CLI entry point |

Each layer has one job. Analysis modules do not call each other. Scoring is not
done inside analysis modules. Reports do not re-run analysis.

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

---

## Project Structure

```
app/
  main.py                          # argparse CLI entry point
  config.py                        # Env-var settings via python-dotenv
  watchlist.py                     # Watchlist scanning and formatting
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
    report_generator.py            # Assembles StockReport; delegates to templates
    templates.py                   # Plain-text, Markdown, and watchlist formatters
  models/
    signal.py                      # Signal Pydantic model
    rating.py                      # Rating Pydantic model
    stock_report.py                # StockReport Pydantic model
    fundamentals.py                # CompanyFundamentals Pydantic model
    news.py                        # NewsItem Pydantic model
  utils/
    helpers.py                     # safe_float, normalize_ticker
watchlists/
  default.txt                      # Sample watchlist (AAPL, MSFT, NVDA, GOOGL, AMZN)
tests/                             # pytest suite — deterministic, no live API calls
docs/                              # Architecture, scoring rules, data sources, dev log
outputs/
  reports/                         # Saved plain-text reports (TICKER_YYYYMMDD_HHMMSS.txt)
  results/                         # Saved JSON results (TICKER_YYYYMMDD_HHMMSS.json)
```

---

## Current Status

The single-ticker and watchlist analysis pipelines are complete. The tool
produces scored reports with technical, fundamental, news, and risk signals.

## Planned Future Work

These areas are on the roadmap but not yet built:

- **Improved scoring calibration** — better-calibrated weights and thresholds (see `docs/scoring_calibration_plan.md`)
- **Better data validation** — richer error messages for missing or stale data fields
- **Backtesting** — validate signals against historical outcomes (requires careful design)
- **Paper trading simulation** — test signal-driven strategies without real capital (requires backtesting first)
- **ML/LLM sentiment** — replace keyword matching with a trained model (later phase)

Phases involving live or paper trading require additional review and explicit approval
before any implementation begins.
