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

## Running the API Server

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload
```

The server starts at `http://127.0.0.1:8000`. Interactive API docs are available at `http://127.0.0.1:8000/docs`.

CORS is configured to allow `http://localhost:5173` and `http://127.0.0.1:5173`
(the Vite dev server defaults) so the frontend can call the backend during development.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/analyze` | Analyze a ticker; returns a `StockReport` — **analysis only, nothing is saved** |
| `POST` | `/api/reports/analyze` | Analyze a ticker and **save** the snapshot; returns saved metadata + report |
| `GET` | `/api/reports/history` | List saved report summaries (id, ticker, category, score, confidence, created_at) |
| `GET` | `/api/reports/{id}` | Return one full saved `StockReport` snapshot by id |
| `GET` | `/api/watchlists` | List saved watchlists (id, name, description, timestamps, ticker_count) |
| `POST` | `/api/watchlists` | Create a watchlist (`{name, description?}`) |
| `GET` | `/api/watchlists/{id}` | Return one watchlist with its tickers |
| `PATCH` | `/api/watchlists/{id}` | Update a watchlist's name and/or description |
| `DELETE` | `/api/watchlists/{id}` | Delete a watchlist and its tickers |
| `POST` | `/api/watchlists/{id}/tickers` | Add a ticker to a watchlist (`{ticker}`) |
| `DELETE` | `/api/watchlists/{id}/tickers/{ticker}` | Remove a ticker from a watchlist |

> **Watchlist management is storage only.** These endpoints persist named ticker
> lists for later research — they do **not** run analysis, scans, or trades.

**Analysis only (no persistence):**

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

**Analyze and save:**

```bash
curl -X POST http://127.0.0.1:8000/api/reports/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

**Report history:**

```bash
curl http://127.0.0.1:8000/api/reports/history
curl "http://127.0.0.1:8000/api/reports/history?limit=10"
curl http://127.0.0.1:8000/api/reports/1
```

All routes delegate to the same `analyze_stock` service function used by the CLI.
The database file is stored at `data/investment_bot.db` (configurable via the
`DATABASE_PATH` environment variable). No trades are executed.

---

## Running the Frontend

### Prerequisites

The backend must be running before the frontend will work (the health check calls `/api/health` on load).

### First-time setup

```bash
cd frontend
cp .env.example .env        # copy the env template (edit if backend runs on a different port)
npm install
```

### Start the dev server

```bash
cd frontend
npm run dev
```

The app opens at `http://localhost:5173`.

**Current frontend scope:**
- Dashboard page — backend health status, disclaimer, link to Analyze
- Analyze page — enter a ticker, choose "Analyze only" (POST /api/analyze) or "Analyze and save" (POST /api/reports/analyze), view the StockReport result
- Watchlists page — create, rename, and delete named watchlists; add and remove tickers; basic CRUD over the watchlist API (storage only, no analysis run from here)
- Saved Reports page (`/reports`) — list of previously saved analysis snapshots; each links to a Report Detail page (`/reports/:id`) that renders the full saved report. Display-only — no analysis is run here.

### Build and lint

```bash
cd frontend
npm run build        # type-check + production build to frontend/dist/
npm run lint         # ESLint
```

---

## Running Backend Tests

```bash
pytest
```

All tests are deterministic — no live API calls.

---

## Architecture

```
app/data/ → app/analysis/ → app/analysis/scoring.py → app/reports/ → app/services/ → CLI / API
```

| Layer | Responsibility |
|-------|---------------|
| `app/data/` | Fetch and validate raw data; return typed models or DataFrames |
| `app/analysis/` | Compute independent signal lists from data |
| `app/analysis/scoring.py` | Aggregate signals into a composite Rating |
| `app/reports/` | Format a Rating into a human-readable StockReport |
| `app/services/` | Public service boundary — `analyze_stock` for analysis, `report_persistence_service` for saved snapshot I/O, `watchlist_service` for watchlist CRUD |
| `app/data/database.py` | SQLAlchemy Core schema and engine factory (`analysis_reports`, `watchlists`, `watchlist_tickers`); no business logic |
| `app/watchlist.py` | Orchestrate the pipeline across multiple tickers |
| `app/main.py` | Thin argparse CLI shell; delegates to `app/services/` |
| `app/api/` | Thin FastAPI layer; delegates to `app/services/` |

Each layer has one job. Analysis modules do not call each other. Scoring is not
done inside analysis modules. Reports do not re-run analysis. API routes and CLI
both call the service layer — neither duplicates pipeline logic.

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
  main.py                          # Thin argparse CLI shell
  config.py                        # Env-var settings via python-dotenv
  watchlist.py                     # Watchlist scanning and formatting
  api/
    main.py                        # FastAPI app factory (uvicorn entry point)
    errors.py                      # Shared KNOWN_ANALYSIS_ERRORS tuple used by both API routes
    routes/
      health.py                    # GET /api/health
      analysis.py                  # POST /api/analyze (analysis only, no save)
      reports.py                   # POST /api/reports/analyze, GET /api/reports/history, GET /api/reports/{id}
      watchlists.py                # GET/POST/PATCH/DELETE /api/watchlists and /tickers
    schemas/
      analysis.py                  # AnalyzeRequest Pydantic schema
      reports.py                   # SavedReportSummary, SavedReportDetail schemas
      watchlists.py                # Watchlist request/response schemas
  services/
    stock_analysis_service.py      # analyze_stock — public entry point for CLI and API
    report_persistence_service.py  # save_stock_report, list_saved_reports, get_saved_report
    watchlist_service.py           # watchlist + ticker CRUD (storage only)
  data/
    market_data.py                 # OHLCV price history
    fundamentals.py                # Company fundamentals
    news_data.py                   # Recent news headlines
    storage.py                     # Saves reports and JSON results to disk
    database.py                    # SQLAlchemy Core engine; analysis_reports + watchlists + watchlist_tickers tables
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
frontend/                          # React + Vite + TypeScript frontend (Dashboard, Analyze, Watchlists, Saved Reports)
  src/
    api/
      client.ts                    # Base fetch wrapper (get/post/patch/del); base URL, ApiError class
      analysisApi.ts               # checkHealth, analyzeOnly, analyzeAndSave
      watchlistApi.ts              # Watchlist CRUD client functions
      reportsApi.ts                # listSavedReports, getSavedReport (read-only history)
    components/
      LoadingState.tsx             # Spinner with accessible role/aria attributes
      ErrorMessage.tsx             # Accessible error display
      StockReportView.tsx          # Full StockReport result display
    pages/
      DashboardPage.tsx            # Health status, disclaimer, nav to Analyze / Saved Reports
      AnalyzePage.tsx              # Ticker input, analyze/save actions, report result
      WatchlistsPage.tsx           # Watchlist CRUD UI (create/rename/delete, add/remove tickers)
      SavedReportsPage.tsx         # List of saved report snapshots (/reports)
      ReportDetailPage.tsx         # One saved report rendered in full (/reports/:id)
    types/
      report.ts                    # TypeScript interfaces mirroring backend report schemas
      watchlist.ts                 # TypeScript interfaces mirroring backend watchlist schemas
    App.tsx                        # BrowserRouter, NavLink header, route table
    main.tsx                       # Vite entry point
    styles.css                     # Plain CSS — no framework
  .env.example                     # Copy to .env before running dev server
```

---

## Current Status

The single-ticker and watchlist analysis pipelines are complete. The tool
produces scored reports with technical, fundamental, news, and risk signals.
A FastAPI backend (`app/api/`) exposes the analysis through `POST /api/analyze`
(analysis only) and `POST /api/reports/analyze` (analyze and persist). A SQLite
persistence layer stores StockReport JSON snapshots with a history and detail
endpoint for retrieval. All routes are backed by the same service layer used by
the CLI.

Watchlist management is implemented at a basic CRUD level across all layers:
SQLite tables (`watchlists`, `watchlist_tickers`), a `watchlist_service`, the
`/api/watchlists` endpoints, and a Watchlists page in the frontend. Users can
create, rename, and delete named watchlists and add or remove tickers. This is
storage only — no analysis, scans, alerts, or trades run from a watchlist.

A React + Vite frontend (`frontend/`) is in active development. The Dashboard,
Analyze, Watchlists, and Saved Reports pages are built and connected to the
backend. The Analyze page supports both analyze-only and analyze-and-save flows;
the Saved Reports page lists persisted snapshots and links to a read-only Report
Detail page.

## Planned Future Work

These areas are on the roadmap but not yet built:

- **Watchlist analysis** — analyze every ticker in a saved watchlist by reusing the existing pipeline (CRUD foundation is in place; see `docs/watchlist_management_plan.md`)
- **Improved scoring calibration** — better-calibrated weights and thresholds (see `docs/scoring_calibration_plan.md`)
- **Better data validation** — richer error messages for missing or stale data fields
- **Backtesting** — validate signals against historical outcomes (requires careful design)
- **Paper trading simulation** — test signal-driven strategies without real capital (requires backtesting first)
- **ML/LLM sentiment** — replace keyword matching with a trained model (later phase)

Phases involving live or paper trading require additional review and explicit approval
before any implementation begins.
