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
scored research report. Run a single ticker, scan an entire watchlist, track
holdings you entered by hand, or surface candidates from a controlled stock
universe.

There are three ways in, all backed by the same analysis pipeline:

- a **CLI** (`python -m app.main`) that prints or saves reports,
- a **FastAPI backend** that exposes the pipeline over HTTP and persists results to SQLite,
- a **React + Vite frontend** that reads that API.

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

### Web application (FastAPI backend + React/Vite frontend)

- **FastAPI backend** — exposes the same analysis pipeline used by the CLI; interactive docs at `/docs`
- **Saved reports** — analyze-and-save a `StockReport` to SQLite, then browse history and a full report-detail view
- **Watchlists** — create/rename/delete named ticker lists, add/remove tickers (storage-only CRUD)
- **On-demand watchlist analysis** — run the pipeline over a saved watchlist; per-ticker partial success, results not saved
- **Saved watchlist analysis snapshots** — explicitly save a watchlist analysis run as a historical record, with a snapshot-detail view
- **Snapshot trend charts** — Lightweight Charts line of successful-ticker count or backend-derived average score across saved snapshots (toggle; historical data only)
- **Daily price chart** — read-only market-data history endpoint rendered as a daily closing-price chart on the Analyze page
- **Personal portfolios** — create named portfolios and manually enter the holdings you own (ticker, shares, average cost, optional purchase date/notes); a priced summary values each holding at the current end-of-day price and computes cost basis, market value, unrealized gain/loss, return %, and portfolio weight. Manual entry only — no brokerage connection and no trading
- **Stock discovery** — a Discover page that ranks research candidates from a controlled, static stock universe instead of only tickers you type in. Six deterministic modes (`overall`, `momentum`, `quality`, `value`, `defensive`, `avoid`), each result showing the score, category, confidence, sub-scores, key positives, key risks, and a plain-text reason it surfaced. Rule-based and bounded — no ML, no LLM picks, nothing scheduled or saved
- **Paper trading (backend only)** — open a **simulated** trading account with a made-up starting cash balance, record paper buys and sells at prices you supply, and read back positions, cash, realized and unrealized gain/loss, total value, and a full transaction ledger. Entirely simulated: there is no broker integration, no real account link, and no real order anywhere in this project. **No frontend UI yet** — this milestone is API + services + tests only
- **Dark dashboard** — app shell with sidebar; dashboard summary cards over real saved reports and watchlists, plus the portfolio panel

## What Is Not Included (By Design)

This project intentionally does not implement:

- Live trading
- Broker API integrations — no Vanguard, Schwab, Plaid, Alpaca, Robinhood, or Interactive Brokers
- Real order execution of any kind
- Real account linking or position syncing
- Automatic trading, automatic rebalancing, or automated position management
- Trade alerts or allocation advice
- Margin, options, or short selling
- ML/LLM sentiment models
- Backtesting (planned for a future phase)

Paper trading **is** implemented (see above), and it is a simulation: hand-entered
trades against a made-up cash balance, at prices the user supplies. Nothing about
it reaches a market.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No API keys are required. The only data provider is yfinance, which needs none.
A `.env` file is optional — copy `.env.example` if you want to override
`DATABASE_PATH` or `ENVIRONMENT`; every setting has a working default.

Dependencies (`requirements.txt`): pandas, numpy, requests, yfinance, pydantic,
python-dotenv, pytest, fastapi, uvicorn, httpx, sqlalchemy.

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
| `POST` | `/api/watchlists/{id}/analyze` | Analyze every ticker in a watchlist; returns per-ticker results + errors (partial success, nothing saved) |
| `POST` | `/api/watchlists/{id}/analysis-snapshots` | Analyze the watchlist **and save** the run as a historical snapshot (explicit) |
| `GET` | `/api/watchlists/{id}/analysis-snapshots` | List saved snapshot summaries for a watchlist (newest first; includes `average_score`) |
| `GET` | `/api/watchlist-analysis-snapshots/{id}` | Return one saved snapshot's full detail (results + errors) |
| `GET` | `/api/market-data/{ticker}/history` | Read-only daily historical OHLCV price series (for the price chart) |
| `GET` | `/api/portfolios` | List portfolios (id, name, description, timestamps, holdings_count) |
| `POST` | `/api/portfolios` | Create a portfolio (`{name, description?}`) |
| `GET` | `/api/portfolios/{id}` | Return one portfolio with its holdings |
| `PATCH` | `/api/portfolios/{id}` | Update a portfolio's name and/or description |
| `DELETE` | `/api/portfolios/{id}` | Delete a portfolio and all its holdings |
| `POST` | `/api/portfolios/{id}/holdings` | Add a holding (`{ticker, shares, average_cost, purchase_date?, notes?}`); duplicate ticker → 409 |
| `PATCH` | `/api/portfolios/{id}/holdings/{holding_id}` | Update a holding (partial; duplicate-ticker validation preserved) |
| `DELETE` | `/api/portfolios/{id}/holdings/{holding_id}` | Remove one holding |
| `GET` | `/api/portfolios/{id}/summary` | Priced summary — holding + portfolio valuations at current prices (200 even on partial price failure; unavailable prices listed in `warnings`) |
| `GET` | `/api/discovery` | Ranked discovery candidates. Query: `mode` (default `overall`), `universe` (default `starter_large_cap`), `limit` (default 10, max 50), `max_full_analysis` (default 25, max 50) |
| `GET` | `/api/discovery/modes` | List supported discovery modes with their descriptions and ranking rules |
| `GET` | `/api/discovery/universes` | List registered stock universes with their sizes |
| `POST` | `/api/paper-trading/accounts` | Open a simulated trading account (`{name, starting_cash}`) |
| `GET` | `/api/paper-trading/accounts` | List simulated accounts (newest first; includes `positions_count`) |
| `GET` | `/api/paper-trading/accounts/{id}` | Return one account with its open positions (no market data) |
| `GET` | `/api/paper-trading/accounts/{id}/summary` | Valued summary — cash, realized + unrealized gain/loss, open-position value, total value and return |
| `GET` | `/api/paper-trading/accounts/{id}/positions` | Open positions priced at the latest valid close |
| `GET` | `/api/paper-trading/accounts/{id}/transactions` | Full transaction ledger, newest first |
| `POST` | `/api/paper-trading/accounts/{id}/buy` | Record a simulated buy (`{ticker, quantity, price, executed_at?}`); insufficient cash → 409 |
| `POST` | `/api/paper-trading/accounts/{id}/sell` | Record a simulated sell; insufficient/unowned shares → 409 |

> **Watchlist CRUD is storage only.** The list/ticker endpoints persist named
> ticker lists; they do not run analysis. `POST /api/watchlists/{id}/analyze`
> runs the existing analysis pipeline over the saved tickers on demand and
> returns the results — it does **not** save them, schedule scans, or trade. The
> Watchlists page has an "Analyze watchlist" button that calls this endpoint and
> displays the results on demand (results are not persisted).

> **Portfolios are manual, read-only holdings.** Portfolio and holding CRUD is
> storage only and never touches market data. Current prices are fetched (via the
> existing yfinance market-data layer) **only** when `GET /api/portfolios/{id}/summary`
> is requested. "Current price" everywhere in this project means the latest
> *valid* close from historical daily data — not necessarily the provider's final
> raw row, which during an open session can carry a volume with null OHLC values. `shares` and `average_cost` are validated decimal-safe
> (`shares > 0`, `average_cost ≥ 0`) and a portfolio holds each ticker at most
> once. If a ticker's price cannot be fetched, that holding is marked
> `price_available: false` (its market value is `null`, never `0`), it is listed
> in `warnings`, and market-value-dependent totals exclude it — `total_cost_basis`
> still reflects every holding. There is no brokerage connection, order execution,
> cash, realized gain, dividend, or tax-lot logic anywhere in this feature.

> **Discovery is bounded, on-demand research.** A discovery run pre-screens the
> selected universe for usable price data, runs the **existing** analysis
> pipeline on a shortlist of at most `max_full_analysis` tickers, and ranks the
> results with a deterministic per-mode sort. It introduces no scoring of its
> own: every score, sub-score, category, confidence level, factor, and trigger
> shown is the scoring engine's own output. Universes are static CSV files
> committed to the repository (`app/data/universes/`) — nothing is scraped at
> runtime. Tickers that fail the pre-screen or the analysis are returned in
> `warnings`; the request still succeeds with `200`. Invalid parameters return
> `400`. Nothing is saved, scheduled, alerted on, or traded, and results are
> research candidates — **not** financial advice.

> **Paper trading is a simulation, and it is separate from your portfolio.**
> A paper trading account has a made-up starting cash balance. Every buy and
> sell is a row the user submitted, at a price the user supplied — the backend
> never fetches a price in order to "execute" a trade, and it never contacts a
> market. There is **no broker integration** (no Vanguard, Schwab, Plaid,
> Alpaca, Robinhood, or Interactive Brokers), no real account link, no order
> routing, no automatic trading or rebalancing, no alerts, no allocation advice,
> and no margin, options, or short selling. A sell may never exceed the shares
> the account holds.
>
> It shares **no tables and no code** with manual portfolio tracking:
> `/api/portfolios` records real holdings you own and carries no cash or
> ledger, while `/api/paper-trading` is a self-contained simulation. It also
> sits entirely outside the research pipeline — it cannot affect a rating,
> score, report, discovery ranking, watchlist analysis, or portfolio summary.
>
> Accounting is decimal-exact: `paper_trading_transactions` is an append-only
> ledger, `paper_trading_positions` is the derived current-state cache updated
> atomically with the cash movement, and two invariants hold after every trade —
> `cash_balance == starting_cash - Σ(buy gross) + Σ(sell gross)` and
> `realized_gain_loss == Σ(transaction realized)`. Current prices are fetched
> only when a summary or positions read is requested (via the same
> `latest_valid_close` reader the rest of the project uses); a per-ticker price
> failure returns 200 with the position marked `price_available: false` and
> listed in `warnings`.
>
> **Backend only in this milestone** — there is no Paper Trading page in the
> frontend yet.

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

- The backend must be running before the frontend will work (the health check calls `/api/health` on load).
- **Node 22 LTS** (≥ 22.13). The frontend toolchain (Vite 8, Vitest 3) targets the
  active LTS line; `frontend/.nvmrc` pins it. With nvm: `cd frontend && nvm use`.
  Newer odd-numbered Node releases (e.g. 23.x) work but emit an engine warning.

### First-time setup

```bash
cd frontend
nvm use                     # selects Node 22 from .nvmrc (optional but recommended)
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
- Dark app shell with a left sidebar; routing via React Router
- Discover page (`/discover`) — pick a mode, universe, result count, and analysis budget, then run a bounded discovery pass and read the ranked candidates with their match reasons; skipped tickers are listed as warnings rather than failing the run
- Dashboard page — a personal **Portfolio panel** (create/select/edit/delete portfolios; add/edit/remove holdings; summary cards for market value, cost basis, unrealized gain/loss, return, and holdings count; a holdings table valued at current prices with per-row Analyze/Edit/Remove; explicit loading, empty, partial-price-failure, and error states) plus backend health/source status, disclaimer, and summary cards over real saved reports and watchlists (rating breakdown, top candidates, recent reports). The Market Overview strip remains a clearly labeled "coming soon" placeholder
- Analyze page — enter a ticker, choose "Analyze only" (POST /api/analyze) or "Analyze and save" (POST /api/reports/analyze), view the StockReport result and a daily closing-price chart
- Watchlists page — create, rename, and delete named watchlists; add and remove tickers (CRUD over the watchlist API). "Analyze watchlist" runs the pipeline on demand and shows per-ticker results/failures (not saved); "Analyze & save snapshot" records a historical snapshot. Saved snapshots list with a snapshot-trend chart (success count / average score toggle)
- Snapshot Detail page (`/watchlists/:watchlistId/snapshots/:snapshotId`) — full read-only view of one saved watchlist analysis snapshot
- Saved Reports page (`/reports`) — list of previously saved analysis snapshots; each links to a Report Detail page (`/reports/:id`) that renders the full saved report. Display-only — no analysis is run here.

> The frontend is display-only: it formats values the backend produced and never recomputes scores, categories, weights, or averages.

### Build, lint, and test

```bash
cd frontend
npm run build        # type-check (tsc -b) + production build to frontend/dist/
npm run lint         # ESLint
npm test             # Vitest unit tests (pure utilities — no browser/DOM)
```

---

## Running Backend Tests

```bash
pytest                                   # full suite
pytest tests/test_risk_analysis.py       # one file
pytest tests/test_watchlist_service.py tests/test_watchlist_api.py
```

All tests are deterministic — they build DataFrames and typed models locally and
never call a live API. There is no linter or formatter configured for the Python
side; `python -m py_compile <module>` is a quick syntax check.

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
| `app/services/` | Public service boundary — `analyze_stock` (analysis), `report_persistence_service` (saved-report I/O), `watchlist_service` (watchlist CRUD), `watchlist_analysis_service` (on-demand scan), `watchlist_analysis_snapshot_service` (saved snapshots + `average_score`), `market_data_service` (price-history responses), `portfolio_service` / `portfolio_summary_service` (manual holdings + priced summary), `discovery_service` / `discovery_screening` / `discovery_ranking` (bounded candidate discovery), `paper_trading_service` / `paper_trading_summary_service` (simulated accounting + valued summary) |
| `app/data/database.py` | SQLAlchemy Core schema, engine factory, and the shared `as_utc` datetime reader (`analysis_reports`, `watchlists`, `watchlist_tickers`, `watchlist_analysis_snapshots`, `watchlist_analysis_snapshot_results`, `portfolios`, `portfolio_holdings`, `paper_trading_accounts`, `paper_trading_transactions`, `paper_trading_positions`); no business logic |
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
      watchlists.py                # GET/POST/PATCH/DELETE /api/watchlists, /tickers, /analyze
      watchlist_snapshots.py       # POST/GET /api/watchlists/{id}/analysis-snapshots, GET /api/watchlist-analysis-snapshots/{id}
      market_data.py               # GET /api/market-data/{ticker}/history
      portfolios.py                # GET/POST/PATCH/DELETE /api/portfolios, /holdings, /summary
      discovery.py                 # GET /api/discovery, /api/discovery/modes, /api/discovery/universes
      paper_trading.py             # POST/GET /api/paper-trading/accounts, /buy, /sell, /positions, /transactions, /summary
    schemas/
      analysis.py                  # AnalyzeRequest Pydantic schema
      reports.py                   # SavedReportSummary, SavedReportDetail schemas
      watchlists.py                # Watchlist + analyze request/response schemas
      watchlist_snapshots.py       # WatchlistSnapshotSummary/Detail (incl. average_score)
      market_data.py               # PricePoint, PriceHistoryResponse schemas
      portfolios.py                # Portfolio/holding CRUD + priced-summary schemas
      discovery.py                 # Names the discovery domain models for the HTTP layer
      paper_trading.py             # Paper trading account/trade request + response schemas
  services/
    stock_analysis_service.py      # analyze_stock — public entry point for CLI and API
    report_persistence_service.py  # save_stock_report, list_saved_reports, get_saved_report
    watchlist_service.py           # watchlist + ticker CRUD (storage only)
    watchlist_analysis_service.py  # analyze_watchlist — run analyze_stock over a saved watchlist
    watchlist_analysis_snapshot_service.py  # save/list/get snapshots; derives average_score
    market_data_service.py         # build read-only price-history responses
    portfolio_service.py           # portfolio + holding CRUD (storage only; decimal-safe)
    portfolio_summary_service.py   # priced portfolio summary; current prices + Decimal math
    discovery_service.py           # run_discovery — universe → pre-screen → bounded analysis → ranking
    discovery_screening.py         # stage-1 lightweight price-data validity check
    discovery_ranking.py           # deterministic per-mode ordering + match reasons (no scoring)
    paper_trading_service.py       # simulated accounts, buys/sells, positions, ledger (no market data)
    paper_trading_summary_service.py  # valued paper account summary; current prices + Decimal math
  data/
    market_data.py                 # OHLCV price history + latest_valid_close (current-price reader)
    fundamentals.py                # Company fundamentals
    news_data.py                   # Recent news headlines
    storage.py                     # Saves reports and JSON results to disk
    database.py                    # SQLAlchemy Core engine + as_utc; analysis_reports, watchlists, watchlist_tickers, watchlist_analysis_snapshots(+_results), portfolios, portfolio_holdings, paper_trading_accounts, paper_trading_transactions, paper_trading_positions
    universe_loader.py             # Loads/validates the static stock universes
    universes/
      starter_large_cap.csv        # Starter universe (liquid large-cap U.S. equities)
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
    universe.py                    # UniverseEntry, UniverseInfo Pydantic models
    discovery.py                   # DiscoveryMode, DiscoveryCandidate, DiscoveryWarning, DiscoveryRun
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
frontend/                          # React + Vite + TypeScript frontend
  src/
    api/
      client.ts                    # Base fetch wrapper (get/post/patch/del); base URL, ApiError class
      analysisApi.ts               # checkHealth, analyzeOnly, analyzeAndSave
      watchlistApi.ts              # Watchlist CRUD + analyze + snapshot client functions
      reportsApi.ts                # listSavedReports, getSavedReport (read-only history)
      marketDataApi.ts             # getPriceHistory (read-only)
      portfolioApi.ts              # Portfolio + holding CRUD + getPortfolioSummary
      discoveryApi.ts              # listDiscoveryModes, listDiscoveryUniverses, runDiscovery
    components/
      LoadingState.tsx             # Spinner with accessible role/aria attributes
      ErrorMessage.tsx             # Accessible error display
      StockReportView.tsx          # Full StockReport result display
      layout/                      # AppShell, Sidebar, PageHeader
      charts/                      # StockPriceChart, WatchlistSnapshotTrendChart (Lightweight Charts)
      dashboard/                   # ComingSoonCard
      watchlist/                   # WatchlistCard, AnalysisResultCard
      portfolio/                   # PortfolioPanel, PortfolioSelector, PortfolioSummaryCards, HoldingsTable, HoldingForm
      discovery/                   # DiscoveryControls, DiscoveryCandidateCard, DiscoveryWarnings
    lib/                           # Pure, tested helpers: format, errors, sort, dashboard, watchlist, chartData, snapshotTrend, portfolio, discovery
    pages/
      DashboardPage.tsx            # Portfolio panel + summary cards over saved reports/watchlists; health/source status
      DiscoverPage.tsx             # Discovery controls + ranked candidate list (/discover)
      AnalyzePage.tsx              # Ticker input, analyze/save actions, report result + price chart
      WatchlistsPage.tsx           # Watchlist CRUD, on-demand analyze, save snapshot, snapshot list + trend chart
      WatchlistSnapshotDetailPage.tsx  # One saved snapshot rendered in full
      SavedReportsPage.tsx         # List of saved report snapshots (/reports)
      ReportDetailPage.tsx         # One saved report rendered in full (/reports/:id)
    types/                         # report.ts, watchlist.ts, marketData.ts, portfolio.ts, discovery.ts (mirror backend schemas)
    App.tsx                        # BrowserRouter + AppShell (sidebar) + route table
    main.tsx                       # Vite entry point
    styles.css                     # Plain CSS — no framework
  .env.example                     # Copy to .env before running dev server
```

---

## Current Status

Everything listed under **Features** above is built, tested, and working end to
end. The sections below summarise where each area stands.

### Built

| Area | State |
|------|-------|
| Analysis pipeline | Complete — technical, fundamental, news, and risk signals scored into a composite `Rating` and rendered as a `StockReport` |
| CLI (`python -m app.main`) | Complete — single ticker and watchlist file modes, with `--save-report` / `--save-markdown` / `--save-json` |
| FastAPI backend (`app/api/`) | Complete for the features above — 8 route modules, all thin, all delegating to `app/services/` |
| SQLite persistence | Saved reports, watchlists + tickers, watchlist analysis snapshots, portfolios + holdings. Schema created via `metadata.create_all()`; no migration tool |
| Watchlists | CRUD, on-demand analysis (not saved), and explicitly saved historical snapshots with trend charts |
| Market-data chart | Read-only daily OHLCV history endpoint + Analyze-page price chart |
| Personal portfolios | Manual holdings CRUD (storage-only) plus a separate priced-summary service; partial price failures degrade gracefully |
| Stock discovery | Static universe → bounded pre-screen → existing analysis pipeline → deterministic per-mode ranking, surfaced on the Discover page. Nothing saved or scheduled |
| Paper trading | **Backend only.** Simulated accounts, hand-entered buys/sells at caller-supplied prices, stored positions over an append-only ledger, cash, realized + unrealized gain/loss, and a valued summary. 8 endpoints under `/api/paper-trading`. **No frontend UI yet.** Simulation only — no broker, no real order, no real account |
| React + Vite frontend | Dashboard, Discover, Analyze, Watchlists, Snapshot Detail, Saved Reports, and Report Detail pages, all wired to the API. Display-only |

### Known gaps and rough edges

- **Research notes** — planned for the report-history area; not started.
- **Scoring calibration** — weights and thresholds are still the original hand-picked values (see `docs/scoring_calibration_plan.md`).
- **Staleness detection** — the market-data layer does not yet reject unreasonably old price history (a documented `TODO` in `app/data/market_data.py`).
- **Discovery universe** — one static universe (`starter_large_cap`); adding more means dropping a CSV in `app/data/universes/` and registering it.
- **Paper trading UI** — the backend is complete, but there is no Paper Trading page in the frontend and no `frontend/src/api/paperTradingApi.ts` yet. The feature is API-only today.
- **Frontend tests** — Vitest covers the pure helpers in `src/lib/` and `src/api/client.ts` only. There are no component or end-to-end tests.
- **Dashboard "Market Overview"** — still a clearly labelled "coming soon" placeholder.

## Planned Future Work

These areas are on the roadmap but not yet built:

- **Research notes** — free-text notes attached to saved reports and watchlists
- **Improved scoring calibration** — better-calibrated weights and thresholds (see `docs/scoring_calibration_plan.md`)
- **Better data validation** — richer error messages for missing or stale data fields
- **Paper trading frontend UI** — a Paper Trading page over the existing `/api/paper-trading` endpoints: account picker, cash and value cards, positions table, buy/sell forms, and the transaction ledger. Backend-complete already; this is display + forms only
- **Backtesting** — validate signals against historical outcomes (requires careful design)
- **ML/LLM sentiment** — replace keyword matching with a trained model (later phase)

Paper trading is built and is a **simulation** (see above). Anything involving real
money — live trading, broker integrations, real account linking, and order
execution — remains permanently out of scope; see **What Is Not Included** above.
