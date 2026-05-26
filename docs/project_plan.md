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
- [x] argparse CLI — full flag support including `--help`

### Maintenance

- [x] Documentation cleanup — `CLAUDE.md`, `README.md`, `architecture.md`, `project_plan.md`
- [x] Code review and dead-code removal — removed unused stubs and empty modules
- [x] Legacy formatter consolidation — single canonical report path in `templates.py`

---

## Future Work

None of the following are implemented. These are candidate directions for
later phases, in rough priority order.

### Near-Term

- Improved scoring calibration — better-tuned weights and thresholds, validated
  against historical data (see `docs/scoring_calibration_plan.md`)
- Better data validation — richer error messages for missing or stale data fields
- Richer report formats — Markdown or HTML output options alongside plain text
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
- Dashboards or web UIs
