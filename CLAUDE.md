# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A modular Python investment analysis tool. It produces structured, scored research
reports for individual stocks. **It is not an automated trading system.**

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
pytest tests/test_market_data.py

# Compile-check a module without running it
python -m py_compile app/analysis/technicals.py
```

## Currently Implemented

| Module | Purpose |
|--------|---------|
| `app/data/market_data.py` | Fetches, validates, and normalizes OHLCV data from yfinance |
| `app/analysis/technicals.py` | Computes SMA, RSI, MACD, volume SMA, daily return; builds 7 typed Signals |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/analysis/scoring.py` | Technical-only scoring from Signal objects into a Rating |
| `app/main.py` | CLI entry point — orchestrates the pipeline and prints a terminal summary |

## Architecture

Data flows in one direction through four layers:

```
data/ → analysis/ → scoring.py → reports/
```

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Data | `app/data/` | Fetch and validate raw data; return DataFrames |
| Analysis | `app/analysis/` | Compute signals from data; modules stay independent of each other |
| Scoring | `app/analysis/scoring.py` | Aggregate signals using weighted formula (see `docs/scoring_rules.md`) |
| Reports | `app/reports/` | Render `StockReport` to disk |

## Layer Rules

- **Data modules** fetch and clean data only. No analysis or scoring logic.
- **Analysis modules** accept a DataFrame as input. Never call yfinance or other external APIs directly.
- **Analysis modules** are independent — `technicals.py` does not call `fundamentals_analysis.py`.
- **Scoring** stays in `scoring.py`. Analysis modules produce signals; they do not score them.
- **Reports** consume scoring outputs. Report modules do not run analysis.

## Development Standards

- Add or update tests for every meaningful code change.
- Keep tests deterministic — build DataFrames locally, never call live APIs in unit tests.
- Update `docs/development_log.md` after meaningful changes.
- Do not add dependencies without a clear need.
- All API keys and secrets live in `.env` (never committed). Access them only through `app/config.py`.

## Key Docs

- `docs/project_plan.md` — version roadmap
- `docs/architecture.md` — full layer diagram
- `docs/scoring_rules.md` — score weights and rating thresholds
- `docs/data_sources.md` — provider options and selection criteria
- `docs/development_log.md` — append an entry for each meaningful change
