# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A modular Python stock research decision-support tool. It fetches market data,
computes signals, scores them, and produces structured plain-text research reports
for individual stocks and watchlists. **It is not an automated trading system.**

Do not implement any of the following:
- Broker API calls or integrations
- Order execution of any kind
- Live or paper trading
- Automatic position management
- Margin or options trading
- Portfolio automation
- ML/LLM sentiment models
- Backtesting (unless explicitly scoped and approved)

## Commands

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server (http://127.0.0.1:8000, docs at /docs)
uvicorn app.api.main:app --reload

# Single-ticker analysis (print report to terminal)
python -m app.main AAPL

# Single-ticker with save flags
python -m app.main AAPL --save-report
python -m app.main AAPL --save-json
python -m app.main AAPL --save-markdown
python -m app.main AAPL --save-report --save-json --save-markdown

# Watchlist scanning (print ranked summary table)
python -m app.main --watchlist watchlists/default.txt

# Watchlist with save flags
python -m app.main --watchlist watchlists/default.txt --save-report
python -m app.main --watchlist watchlists/default.txt --save-json
python -m app.main --watchlist watchlists/default.txt --save-markdown
python -m app.main --watchlist watchlists/default.txt --save-report --save-json --save-markdown

# Show CLI help
python -m app.main --help

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
| `app/data/news_data.py` | Fetches recent news headlines from yfinance; returns typed `NewsItem` objects |
| `app/data/storage.py` | Saves plain-text (`.txt`), Markdown (`.md`), and structured JSON (`.json`) outputs to local disk |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/models/fundamentals.py` | Typed `CompanyFundamentals` Pydantic model; output of the fundamentals data layer |
| `app/models/news.py` | Typed `NewsItem` Pydantic model; output of the news data layer |
| `app/models/stock_report.py` | Typed `StockReport` Pydantic model; top-level output of a full analysis run |
| `app/analysis/technicals.py` | Computes SMA 20/50/200, RSI 14, MACD, volume SMA; builds 7 typed Signals |
| `app/analysis/fundamentals_analysis.py` | Builds 5 typed Signals from valuation, profitability, growth, debt, and cash flow |
| `app/analysis/risk_analysis.py` | Builds 4–5 typed Signals from volatility, drawdown, recent trend, liquidity, and beta |
| `app/analysis/news_analysis.py` | Builds exactly 3 NEWS Signals (Sentiment, Risk Headlines, Coverage) via keyword matching |
| `app/analysis/scoring.py` | Composite scoring engine; `score_signals()` aggregates all signal categories into a Rating |
| `app/reports/report_generator.py` | `build_stock_report()` assembles a StockReport from a Rating; `generate_plain_text_report()` delegates to templates |
| `app/reports/templates.py` | Three public formatters: `format_plain_text_report()` (terminal), `format_report_markdown()` (single-ticker Markdown), `format_watchlist_markdown()` (watchlist Markdown) |
| `app/watchlist.py` | Loads watchlist files, scans multiple tickers, formats ranked summary tables, and serializes results |
| `app/utils/helpers.py` | Shared low-level helpers: `safe_float` and `normalize_ticker` |
| `app/services/stock_analysis_service.py` | `analyze_stock` — public entry point for all callers (CLI and API); `_analyze_ticker` is internal |
| `app/api/main.py` | FastAPI app factory; `uvicorn app.api.main:app` entry point |
| `app/api/routes/health.py` | `GET /api/health` |
| `app/api/routes/analysis.py` | `POST /api/analyze` — calls `analyze_stock`, maps known errors to 422, unexpected to 500 |
| `app/api/schemas/analysis.py` | `AnalyzeRequest` — validates and normalizes ticker at the API boundary |
| `app/main.py` | Thin argparse CLI shell — delegates entirely to `app/services/` |

## Architecture

Data flows in one direction through five layers:

```
data/ → analysis/ → scoring.py → reports/ → services/ → CLI / API
```

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Data | `app/data/` | Fetch and validate raw data; return typed models or DataFrames |
| Analysis | `app/analysis/` | Compute signals from data; modules stay independent of each other |
| Scoring | `app/analysis/scoring.py` | Aggregate signals into a composite Rating using weighted formula |
| Reports | `app/reports/` | Format a Rating and its Signals into a human-readable StockReport |
| Services | `app/services/` | Orchestrate the full pipeline; `analyze_stock` is the single public entry point |
| CLI | `app/main.py` | Thin argparse shell; calls `analyze_stock` from services |
| API | `app/api/` | Thin FastAPI layer; calls `analyze_stock` from services |

`app/watchlist.py` orchestrates the single-stock pipeline across multiple tickers.

## Layer Rules

- **Data modules** fetch and clean data only. No analysis or scoring logic.
- **Analysis modules** accept a DataFrame or typed model as input. Never call yfinance or other external APIs directly.
- **Analysis modules** are independent — `technicals.py` does not call `fundamentals_analysis.py`, etc.
- **Scoring** stays in `scoring.py`. Analysis modules produce signals; they do not score them.
- **Reports** consume scoring outputs. Report modules do not run analysis or scoring.
- **Watchlist** reuses the single-stock pipeline; it adds no analysis logic of its own.
- **API route handlers** must stay thin — call `analyze_stock`, handle errors, return the result. No pipeline logic in routes.
- **CLI** must remain functional. Adding API or frontend layers must not break `python -m app.main`.

## Scoring Weights

Base weights (re-normalised to 100% when a category is absent):

| Category | Base Weight |
|----------|-------------|
| Technical | 35% |
| Fundamental | 25% |
| News | 25% |
| Risk | 15% |

## Signal Pattern

Each analysis module follows the same pattern:
- Accepts a validated input (DataFrame, typed model, or list of NewsItem)
- Returns a `list[Signal]` using `SignalCategory.TECHNICAL`, `FUNDAMENTAL`, `NEWS`, or `RISK`
- Never raises on missing data fields — produces a neutral `Signal` with `confidence=0.30` instead
- Has its own exception class (e.g. `TechnicalAnalysisError`, `NewsAnalysisError`, `RiskAnalysisError`) that callers catch
- News fetch failures are non-fatal in `_analyze_ticker` (service layer): the pipeline continues with `analyze_news([])`

## Development Standards

- Add or update tests for every meaningful code change.
- Keep tasks narrow — prefer one clean, tested feature over a large multi-feature PR.
- Keep tests deterministic — build DataFrames and typed models locally, never call live APIs in unit tests.
- Update `docs/development_log.md` after meaningful changes.
- Do not add dependencies without a clear need.
- All API keys and secrets live in `.env` (never committed). Access them only through `app/config.py`.
- Review diffs before committing.

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Architecture and technical design doc | Done |
| 2 | FastAPI backend — `GET /api/health`, `POST /api/analyze` | Done |
| 3 | SQLite persistence — save StockReport snapshots, report history endpoints | **Next — not started** |
| 4 | Next.js frontend foundation | Not started |
| 5 | Watchlist management (frontend + backend routes) | Not started |
| 6 | Research notes and report history UI | Not started |
| 7 | Mock trading simulation (`app/simulation/`) | Not started |
| 8 | ML research layer (`app/ml/`) | Not started |
| 9 | Deployment and hardening | Not started |

See `docs/full_stack_product_architecture.md` for full scope of each phase.

## Non-Negotiable Guardrails

These apply to every phase and every task:

- **No live trading** — never connect to a broker or execute a real order
- **No broker APIs** — no Alpaca, Robinhood, IBKR, or any brokerage integration
- **No order execution** — no scheduled or triggered buy/sell of any kind
- **No options or margin** — equities only; no derivatives or leveraged positions
- **No route-handler logic** — API routes call services; they never contain pipeline logic
- **No CLI regression** — `python -m app.main` must always work after any change
- **No premature ML** — do not add `app/ml/` until Phase 8 is explicitly scoped
- **No premature simulation** — do not add `app/simulation/` until Phase 7 is explicitly scoped

## Key Docs

- `docs/project_plan.md` — version roadmap
- `docs/architecture.md` — full layer diagram
- `docs/full_stack_product_architecture.md` — full-stack product plan and phase roadmap
- `docs/scoring_rules.md` — score weights and rating thresholds
- `docs/data_sources.md` — provider options and selection criteria
- `docs/development_log.md` — append an entry for each meaningful change
