# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A modular Python investment analysis tool. It produces structured, scored plain-text
research reports for individual stocks. **It is not an automated trading system.**

Do not implement any of the following unless explicitly instructed after backtesting is proven:
- Broker API calls or integrations
- Order execution of any kind
- Live or paper trading
- Automatic position management
- Margin or options trading
- Portfolio automation

## Commands

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the entry point
python -m app.main <TICKER>

# Run all tests
pytest

# Run a single test file
pytest tests/test_risk_analysis.py

# Compile-check a module without running it
python -m py_compile app/analysis/scoring.py
```

## Currently Implemented

| Module | Purpose |
|--------|---------|
| `app/data/market_data.py` | Fetches, validates, and normalizes OHLCV price data from yfinance |
| `app/data/fundamentals.py` | Fetches company fundamentals (P/E, margins, growth, D/E, FCF, beta) from yfinance |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/models/fundamentals.py` | Typed `CompanyFundamentals` Pydantic model; output of the fundamentals data layer |
| `app/analysis/technicals.py` | Computes SMA 20/50/200, RSI 14, MACD, volume SMA; builds 7 typed Signals |
| `app/analysis/fundamentals_analysis.py` | Builds 5 typed Signals from valuation, profitability, growth, debt, and cash flow |
| `app/analysis/risk_analysis.py` | Builds 4–5 typed Signals from volatility, drawdown, recent trend, liquidity, and beta |
| `app/analysis/scoring.py` | Composite scoring engine with `score_signals()` and `score_technical_signals()` |
| `app/reports/stock_report.py` | Generates a formatted plain-text research report from a Rating and its Signals |
| `app/main.py` | CLI entry point — orchestrates the full pipeline and prints the report |

## Architecture

Data flows in one direction through four layers:

```
data/ → analysis/ → scoring.py → reports/
```

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Data | `app/data/` | Fetch and validate raw data; return typed models or DataFrames |
| Analysis | `app/analysis/` | Compute signals from data; modules stay independent of each other |
| Scoring | `app/analysis/scoring.py` | Aggregate signals into a composite Rating using weighted formula |
| Reports | `app/reports/` | Format a Rating and its Signals into a human-readable report |

## Layer Rules

- **Data modules** fetch and clean data only. No analysis or scoring logic.
- **Analysis modules** accept a DataFrame or typed model as input. Never call yfinance or other external APIs directly.
- **Analysis modules** are independent — `technicals.py` does not call `fundamentals_analysis.py`, etc.
- **Scoring** stays in `scoring.py`. Analysis modules produce signals; they do not score them.
- **Reports** consume scoring outputs. Report modules do not run analysis or scoring.

## Scoring Weights

Base weights (re-normalised to 100% when a category is absent):

| Category | Base Weight |
|----------|-------------|
| Technical | 35% |
| Fundamental | 25% |
| Risk | 15% |
| News | Reserved — not yet active |

## Signal Pattern

Each analysis module follows the same pattern:
- Accepts a validated input (DataFrame or typed model)
- Returns a `list[Signal]` using `SignalCategory.TECHNICAL`, `FUNDAMENTAL`, or `RISK`
- Never raises on missing data fields — produces a neutral `Signal` with `confidence=0.30` instead
- Has its own exception class (e.g. `TechnicalAnalysisError`, `FundamentalAnalysisError`, `RiskAnalysisError`) that `main.py` catches

## Not Yet Implemented

These files exist as docstring-only stubs:
- `app/data/news_data.py` — news/sentiment data fetcher
- `app/data/storage.py` — data persistence layer
- `app/analysis/news_analysis.py` — news/sentiment signal builder
- `app/reports/report_generator.py` — full report orchestration
- `app/reports/templates.py` — report templates
- `app/models/stock_report.py` — top-level StockReport model

## Development Standards

- Add or update tests for every meaningful code change.
- Keep tests deterministic — build DataFrames and typed models locally, never call live APIs in unit tests.
- Update `docs/development_log.md` after meaningful changes.
- Do not add dependencies without a clear need.
- All API keys and secrets live in `.env` (never committed). Access them only through `app/config.py`.

## Key Docs

- `docs/project_plan.md` — version roadmap
- `docs/architecture.md` — full layer diagram
- `docs/scoring_rules.md` — score weights and rating thresholds
- `docs/data_sources.md` — provider options and selection criteria
- `docs/development_log.md` — append an entry for each meaningful change
