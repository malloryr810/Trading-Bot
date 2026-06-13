# Project Plan

## Goal

Build a modular, personal stock research decision-support tool that produces
structured reports for individual stocks and watchlists. The system is a
research assistant, not an automated trading system.

---

## Completed

All items below are implemented and tested.

### Foundation

- [x] Project skeleton — modular `app/` package layout, `requirements.txt`, `tests/`
- [x] Configuration — env-var settings via python-dotenv (`app/config.py`)
- [x] Shared helpers — `safe_float`, `normalize_ticker` (`app/utils/helpers.py`)
- [x] Typed models — `Signal`, `Rating`, `StockReport`, `CompanyFundamentals`, `NewsItem`

### Data Layer

- [x] Market data fetching — OHLCV price history from yfinance (`app/data/market_data.py`)
- [x] Fundamentals fetching — P/E, margins, growth, D/E, FCF, beta (`app/data/fundamentals.py`)
- [x] News fetching — recent headlines from yfinance (`app/data/news_data.py`)
- [x] Storage helpers — save plain-text reports and JSON results to disk (`app/data/storage.py`)

### Analysis Layer

- [x] Technical signal analysis — SMA 20/50/200, RSI 14, MACD, volume SMA; 7 signals
- [x] Fundamental signal analysis — valuation, profitability, growth, debt, cash flow; 5 signals
- [x] News / sentiment analysis — keyword sentiment, risk headlines, coverage density; 3 signals
- [x] Risk analysis — volatility, drawdown, recent trend, liquidity, beta; 4–5 signals
- [x] Weighted scoring engine — composite score and rating category (`app/analysis/scoring.py`)

### Reports Layer

- [x] StockReport model — structured Pydantic output (`app/models/stock_report.py`)
- [x] Report generator — assembles StockReport from Rating (`app/reports/report_generator.py`)
- [x] Plain-text report formatter — canonical terminal-readable output (`app/reports/templates.py`)

### CLI and Export

- [x] Single-stock analysis CLI — `python -m app.main AAPL`
- [x] Single-stock plain-text export — `--save-report`
- [x] Single-stock JSON export — `--save-json`
- [x] Watchlist file loading — plain-text file, one ticker per line
- [x] Watchlist scanning — runs the full pipeline across multiple tickers
- [x] Watchlist ranked summary — formatted table sorted by composite score
- [x] Watchlist plain-text export — `--watchlist FILE --save-report`
- [x] Watchlist JSON export — `--watchlist FILE --save-json`
- [x] Single-stock Markdown export — `--save-markdown` (plain Markdown report)
- [x] Watchlist Markdown export — `--watchlist FILE --save-markdown` (Markdown with pipe table)
- [x] argparse CLI — full flag support including `--help`

### Data quality and pipeline

- [x] Improved market data validation — full OHLCV column, null, and numeric checks
- [x] Company name and current price propagated through pipeline — Rating → StockReport → watchlist summary

### Application Layer (API + Persistence + Frontend)

- [x] FastAPI backend — app factory (`app/api/main.py`); thin routes delegate to services
- [x] `GET /api/health`, `POST /api/analyze` (analysis only, no save)
- [x] SQLite report persistence — `analysis_reports` table (SQLAlchemy Core); `POST /api/reports/analyze`, `GET /api/reports/history`, `GET /api/reports/{id}`
- [x] SQLite watchlist persistence — `watchlists` / `watchlist_tickers` tables; `watchlist_service` CRUD
- [x] Watchlist CRUD API — `GET/POST /api/watchlists`, `GET/PATCH/DELETE /api/watchlists/{id}`, add/remove ticker endpoints
- [x] Watchlist on-demand analysis — `watchlist_analysis_service` + `POST /api/watchlists/{id}/analyze` (partial success; results not saved)
- [x] React + Vite + TypeScript frontend — Dashboard, Analyze, Watchlists, Saved Reports, Report Detail pages
- [x] Typed API client and display-only pages — no scoring/analysis logic duplicated in the frontend

### Maintenance

- [x] Documentation cleanup — `CLAUDE.md`, `README.md`, `architecture.md`, `project_plan.md`
- [x] Code review and dead-code removal — removed unused stubs and empty modules
- [x] Legacy formatter consolidation — three canonical formatters in `templates.py`
- [x] Scoring calibration plan and worksheet — `docs/scoring_calibration_plan.md`, `docs/scoring_calibration_worksheet.md`
- [x] First calibration review notes — `docs/calibration_review_notes.md`

---

## Future Work

None of the following are implemented. These are candidate directions for
later phases, in rough priority order.

### Near-Term

- Improved scoring calibration — better-tuned weights and thresholds, validated
  against historical data (see `docs/scoring_calibration_plan.md`)
- Better data validation — richer error messages for missing or stale data fields
- Optional alternate data providers — Alpha Vantage, Polygon.io, Finnhub, or
  Financial Modeling Prep as alternatives to yfinance

### Later-Stage

These phases require additional design and explicit approval before any
implementation begins.

- **Backtesting** — validate signals against historical outcomes; requires
  careful data-handling design and is a prerequisite for any simulation work
- **Paper trading simulation** — test signal-driven strategies without real
  capital; requires backtesting first
- **ML / LLM sentiment** — replace keyword matching with a trained model;
  requires external dependency review

### Explicitly Out of Scope

The following will not be implemented in this project:

- Live trading of any kind
- Broker API integrations
- Order execution
- Automated position management
- Margin or options trading
- Portfolio automation
- Scheduled scans, alerts, or background jobs

(Note: a local web UI now exists — the React + Vite frontend listed under
"Completed." It is a research/display surface only and performs no trading,
scheduling, or order execution.)
