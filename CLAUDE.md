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

# Run the watchlist suites specifically
pytest tests/test_watchlist_service.py tests/test_watchlist_api.py

# Compile-check a module without running it
python -m py_compile app/analysis/scoring.py
```

### Frontend commands

```bash
cd frontend
nvm use              # Node 22 LTS from frontend/.nvmrc (engines: node >=22.13.0)
npm install          # first-time setup (cp .env.example .env if needed)
npm run dev          # Vite dev server at http://localhost:5173 (backend must be running)
npm run build        # type-check (tsc -b) + production build to frontend/dist/
npm run lint         # ESLint
npm test             # Vitest unit tests (pure logic only — src/**/*.test.ts)
```

Frontend Node version: use the active LTS line (Node 22, ≥ 22.13) per
`frontend/.nvmrc`. A known dev-only npm-audit advisory (esbuild via Vite/Vitest)
is documented in `docs/development_log.md`; do not run `npm audit fix --force`
(it would downgrade Vitest and break the test harness).

## Currently Implemented

| Module | Purpose |
|--------|---------|
| `app/data/market_data.py` | Fetches, validates, and normalizes OHLCV price data from yfinance. Also owns `latest_valid_close(df)` — the canonical current-price reader: newest-first scan for the first finite close, so an in-progress session row (volume present, OHLC still null) never reads as "no price". Returns `None` when nothing is usable, never `0` |
| `app/data/fundamentals.py` | Fetches company fundamentals (P/E, margins, growth, D/E, FCF, beta) from yfinance |
| `app/data/news_data.py` | Fetches recent news headlines from yfinance; returns typed `NewsItem` objects |
| `app/data/storage.py` | Saves plain-text (`.txt`), Markdown (`.md`), and structured JSON (`.json`) outputs to local disk |
| `app/models/signal.py` | Typed `Signal` Pydantic model; shared contract across the analysis layer |
| `app/models/rating.py` | Typed `Rating` Pydantic model; output of the scoring engine |
| `app/models/fundamentals.py` | Typed `CompanyFundamentals` Pydantic model; output of the fundamentals data layer |
| `app/models/news.py` | Typed `NewsItem` Pydantic model; output of the news data layer |
| `app/models/stock_report.py` | Typed `StockReport` Pydantic model; top-level output of a full analysis run |
| `app/models/confidence_diagnostics.py` | Typed `ConfidenceDiagnostics` Pydantic model; read-only breakdown of confidence inputs (diagnostic only — never affects score or label) |
| `app/analysis/technicals.py` | Computes SMA 20/50/200, RSI 14, MACD, volume SMA; builds 7 typed Signals |
| `app/analysis/fundamentals_analysis.py` | Builds 5 typed Signals from valuation, profitability, growth, debt, and cash flow |
| `app/analysis/risk_analysis.py` | Builds 4–5 typed Signals from volatility, drawdown, recent trend, liquidity, and beta |
| `app/analysis/news_analysis.py` | Builds exactly 3 NEWS Signals (Sentiment, Risk Headlines, Coverage) via keyword matching |
| `app/analysis/scoring.py` | Composite scoring engine; `score_signals()` aggregates all signal categories into a Rating |
| `app/reports/report_generator.py` | `build_stock_report()` assembles a StockReport from a Rating; `generate_plain_text_report()` delegates to templates |
| `app/reports/templates.py` | Three public formatters: `format_plain_text_report()` (terminal), `format_report_markdown()` (single-ticker Markdown), `format_watchlist_markdown()` (watchlist Markdown) |
| `app/watchlist.py` | Loads watchlist files, scans multiple tickers, formats ranked summary tables, and serializes results |
| `app/utils/helpers.py` | Shared low-level helpers: `safe_float` and `normalize_ticker` |
| `app/models/universe.py` | Typed `UniverseEntry` / `UniverseInfo` Pydantic models; one row of a stock-universe file and universe metadata |
| `app/models/discovery.py` | Typed discovery models: `DiscoveryMode` enum, `DiscoveryModeInfo`, `DiscoveryCandidate`, `DiscoveryStage`, `DiscoveryWarning`, `DiscoveryRun`. Every scored field is copied from `Rating`; discovery owns only `rank` + `match_reason` |
| `app/services/stock_analysis_service.py` | `analyze_stock` — public entry point for all callers (CLI and API); attaches `current_price` via `latest_valid_close`; `analyze_stock_rating` — same pipeline returning the raw `Rating` (sub-scores) for discovery ranking; `_analyze_ticker` is internal |
| `app/services/report_persistence_service.py` | `save_stock_report`, `list_saved_reports`, `get_saved_report` — SQLite persistence boundary |
| `app/services/watchlist_service.py` | Watchlist + ticker CRUD over SQLite (storage only); `WatchlistValidationError`/`WatchlistNotFoundError`; optional `engine` kwarg for tests |
| `app/services/watchlist_analysis_service.py` | `analyze_watchlist` — reuses `get_watchlist` + `analyze_stock` to analyze every ticker in a saved watchlist; partial success (per-ticker errors captured); analysis-only, nothing saved. Surfaced in the UI via the Watchlists page "Analyze watchlist" button |
| `app/services/watchlist_analysis_snapshot_service.py` | `analyze_and_save_snapshot`, `save_watchlist_analysis_snapshot`, `list_watchlist_snapshots`, `get_watchlist_snapshot` — saves/reads historical snapshots of explicit analyze-and-save runs; derives `average_score` from stored success-row scores (`_mean_score`). Not a scheduled scan |
| `app/services/market_data_service.py` | `get_price_history_response` — builds the read-only price-history response (JSON-safe nullable OHLCV) from `market_data`; no analysis/scoring |
| `app/services/portfolio_service.py` | Portfolio + holding CRUD over SQLite (storage only; no market data). Decimal-safe `shares`/`average_cost` validation; `PortfolioValidationError`/`PortfolioNotFoundError`/`HoldingNotFoundError`/`DuplicateHoldingError`; one ticker per portfolio; cascade-deletes holdings; optional `engine` kwarg for tests |
| `app/services/portfolio_summary_service.py` | `get_portfolio_summary` — enriches a portfolio with current prices (reuses `market_data` + `latest_valid_close`) and computes holding + portfolio values with `Decimal` math. Prices fetched only here, never during CRUD. Partial/complete price failure is non-fatal (per-holding `price_available` + `warnings`); market-value-dependent totals exclude unpriced holdings and are `None` (never zero) when nothing is priced. Optional `price_lookup`/`engine` kwargs for tests |
| `app/services/discovery_screening.py` | `prescreen_ticker` — stage-1 lightweight validity check (fetchable history, ≥60 settled closes, positive latest *valid* close via `latest_valid_close`, usable average volume). Returns a `PrescreenResult`; never raises, never scores |
| `app/services/discovery_ranking.py` | Pure per-mode ranking strategies over existing `Rating` objects (`rank_ratings`, `match_reason`, `valuation_lean`, `list_mode_info`). Ordering only — no scoring, ties broken by ticker |
| `app/services/discovery_service.py` | `run_discovery`, `list_discovery_modes`, `list_discovery_universes` — universe → bounded pre-screen → `analyze_stock_rating` → mode ranking → `DiscoveryRun`. Bounded by `max_full_analysis`; per-ticker failures become warnings; `DiscoveryValidationError` → 400. Optional `analyze`/`prescreen` kwargs for tests. Nothing saved, nothing scheduled |
| `app/data/universe_loader.py` | Loads the static, versioned universe CSVs in `app/data/universes/` (`load_universe`, `load_universe_file`, `list_universes`); validates ticker uniqueness/normalization; caches per key. No network access |
| `app/data/universes/starter_large_cap.csv` | The only universe today: a hand-maintained set of liquid large-cap U.S. equities (`ticker,company_name,sector,industry`) |
| `app/data/database.py` | SQLAlchemy Core engine factory (`build_engine`) and table definitions: `analysis_reports`, `watchlists`, `watchlist_tickers`, `watchlist_analysis_snapshots`, `watchlist_analysis_snapshot_results`, `portfolios`, `portfolio_holdings` |
| `app/api/main.py` | FastAPI app factory; `uvicorn app.api.main:app` entry point |
| `app/api/routes/health.py` | `GET /api/health` |
| `app/api/routes/analysis.py` | `POST /api/analyze` — analysis only; calls `analyze_stock`, does not save |
| `app/api/routes/reports.py` | `POST /api/reports/analyze`, `GET /api/reports/history`, `GET /api/reports/{id}` |
| `app/api/routes/watchlists.py` | Watchlist CRUD routes — `GET/POST /api/watchlists`, `GET/PATCH/DELETE /api/watchlists/{id}`, `POST` / `DELETE` `/api/watchlists/{id}/tickers[/{ticker}]`, `POST /api/watchlists/{id}/analyze` (analyze-watchlist, partial success); thin, delegate to services |
| `app/api/routes/watchlist_snapshots.py` | `POST`/`GET /api/watchlists/{id}/analysis-snapshots`, `GET /api/watchlist-analysis-snapshots/{id}` — saved snapshot save/list/detail; thin, delegate to snapshot service |
| `app/api/routes/market_data.py` | `GET /api/market-data/{ticker}/history` — read-only daily OHLCV history |
| `app/api/routes/portfolios.py` | Portfolio + holding CRUD — `GET/POST /api/portfolios`, `GET/PATCH/DELETE /api/portfolios/{id}`, `POST /api/portfolios/{id}/holdings`, `PATCH`/`DELETE` `/api/portfolios/{id}/holdings/{holding_id}`, `GET /api/portfolios/{id}/summary` (priced). Thin; validation→400, duplicate ticker→409, missing→404; summary stays 200 on price failure |
| `app/api/routes/discovery.py` | `GET /api/discovery` (ranked candidates; `mode`, `universe`, `limit`, `max_full_analysis`), `GET /api/discovery/modes`, `GET /api/discovery/universes`. Thin; invalid params → 400, partial ticker failures stay 200 with `warnings` |
| `app/api/schemas/analysis.py` | `AnalyzeRequest` — validates and normalizes ticker at the API boundary |
| `app/api/schemas/discovery.py` | Names the discovery domain models for the HTTP layer (`DiscoveryResponse`, `DiscoveryModeResponse`, `DiscoveryUniverseResponse`); no duplicate field definitions |
| `app/api/schemas/reports.py` | `SavedReportSummary`, `SavedReportDetail` — response schemas for persistence endpoints |
| `app/api/schemas/watchlists.py` | Watchlist request/response schemas (`CreateWatchlistRequest`, `UpdateWatchlistRequest`, `AddTickerRequest`, `WatchlistSummary`, `WatchlistDetail`, `DeleteResponse`, plus analyze-watchlist: `WatchlistAnalysisResponse`/`Result`/`Error`) |
| `app/api/schemas/watchlist_snapshots.py` | `WatchlistSnapshotSummary` (incl. `average_score: float \| null`), `WatchlistSnapshotDetail` |
| `app/api/schemas/market_data.py` | `PricePoint`, `PriceHistoryResponse` — nullable OHLCV transport shapes |
| `app/api/schemas/portfolios.py` | Portfolio/holding request+response schemas (`CreatePortfolioRequest`, `UpdatePortfolioRequest`, `AddHoldingRequest`, `UpdateHoldingRequest`, `PortfolioSummary`, `PortfolioDetail`, `HoldingResponse`, `DeleteResponse`) plus priced summary (`PortfolioSummaryResponse`, `HoldingValuation`, `PortfolioSummaryWarning`). Shares/avg-cost accepted as `Decimal` |
| `app/api/errors.py` | `KNOWN_ANALYSIS_ERRORS` — shared tuple of pipeline error types used by both API routes for 422 mapping |
| `app/main.py` | Thin argparse CLI shell — delegates entirely to `app/services/` |
| `frontend/` | React + Vite + TypeScript browser frontend; dark app shell with sidebar |
| `frontend/src/api/client.ts` | Base fetch wrapper (`get`/`post`/`patch`/`del` over one shared `request` helper); `ApiError` class; `VITE_API_BASE_URL` env var |
| `frontend/src/api/analysisApi.ts` | `checkHealth`, `analyzeOnly`, `analyzeAndSave` |
| `frontend/src/api/watchlistApi.ts` | Watchlist CRUD + `analyzeWatchlist`, `analyzeAndSaveSnapshot`, `listWatchlistSnapshots`, `getWatchlistSnapshot` — one per `/api/watchlists*` endpoint |
| `frontend/src/api/reportsApi.ts` | `listSavedReports`, `getSavedReport` — read-only saved-report history |
| `frontend/src/api/marketDataApi.ts` | `getPriceHistory` — read-only daily price history |
| `frontend/src/api/portfolioApi.ts` | Portfolio + holding CRUD and `getPortfolioSummary` — one per `/api/portfolios*` endpoint |
| `frontend/src/api/discoveryApi.ts` | `listDiscoveryModes`, `listDiscoveryUniverses`, `runDiscovery` — one per `/api/discovery*` endpoint |
| `frontend/src/components/` | Presentational only: `LoadingState`, `ErrorMessage`, `StockReportView`; `layout/` (`AppShell`, `Sidebar`, `PageHeader`); `charts/` (`StockPriceChart`, `WatchlistSnapshotTrendChart`); `dashboard/` (`ComingSoonCard`); `watchlist/` (`WatchlistCard`, `AnalysisResultCard`); `portfolio/` (`PortfolioPanel` container + `PortfolioSelector`, `PortfolioSummaryCards`, `HoldingsTable`, `HoldingForm`); `discovery/` (`DiscoveryControls`, `DiscoveryCandidateCard`, `DiscoveryWarnings`) |
| `frontend/src/lib/` | Pure, tested helpers: `format`, `errors`, `sort`, `dashboard`, `watchlist`, `chartData`, `snapshotTrend`, `portfolio` (money/percent/share formatting + holding-form validation), `discovery` (query building, mode labels, score/price formatting, run + warning summaries). Display-only — never recompute scores/categories/averages/portfolio totals/discovery ranking |
| `frontend/src/pages/` | `DashboardPage` (portfolio panel, summary cards, health/source status), `DiscoverPage` (`/discover` — mode/universe/limit controls + ranked candidates), `AnalyzePage` (analyze + report + price chart), `WatchlistsPage` (CRUD + on-demand analyze + save snapshot + snapshot list/trend chart), `WatchlistSnapshotDetailPage` (`/watchlists/:watchlistId/snapshots/:snapshotId`), `SavedReportsPage` (`/reports`), `ReportDetailPage` (`/reports/:id`) |
| `frontend/src/types/` | `report.ts`, `watchlist.ts` (incl. snapshot summary/detail + `average_score`), `marketData.ts`, `portfolio.ts`, `discovery.ts` — mirror backend schemas |

## Architecture

Data flows in one direction through five layers:

```
data/ → analysis/ → scoring.py → reports/ → services/ → CLI / API
```

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Data | `app/data/` | Fetch and validate raw data; return typed models or DataFrames |
| Database | `app/data/database.py` | SQLAlchemy Core engine and schema; no business logic |
| Analysis | `app/analysis/` | Compute signals from data; modules stay independent of each other |
| Scoring | `app/analysis/scoring.py` | Aggregate signals into a composite Rating using weighted formula |
| Reports | `app/reports/` | Format a Rating and its Signals into a human-readable StockReport |
| Services | `app/services/` | `analyze_stock` — analysis pipeline entry point; `report_persistence_service` — DB boundary |
| CLI | `app/main.py` | Thin argparse shell; calls `analyze_stock` from services |
| API | `app/api/` | Thin FastAPI layer; routes call service functions; no pipeline or DB logic in route handlers |
| Frontend | `frontend/` | React + Vite display layer; calls API endpoints; never duplicates analysis or scoring logic |

`app/watchlist.py` orchestrates the single-stock pipeline across multiple tickers.

Stock discovery wraps the same pipeline in one extra flow:

```
universes/*.csv → universe_loader → discovery pre-screen → bounded shortlist
    → analyze_stock_rating (existing pipeline) → discovery_ranking → /api/discovery → Discover page
```

## Layer Rules

- **Data modules** fetch and clean data only. No analysis or scoring logic.
- **Analysis modules** accept a DataFrame or typed model as input. Never call yfinance or other external APIs directly.
- **Analysis modules** are independent — `technicals.py` does not call `fundamentals_analysis.py`, etc.
- **Scoring** stays in `scoring.py`. Analysis modules produce signals; they do not score them.
- **Reports** consume scoring outputs. Report modules do not run analysis or scoring.
- **Watchlist** reuses the single-stock pipeline; it adds no analysis logic of its own.
- **API route handlers** must stay thin — call service functions, handle errors, return the result. No pipeline or persistence logic in route handlers.
- **API persistence routes** (`/api/reports/*`) call `analyze_stock` from `stock_analysis_service` and the persistence functions from `report_persistence_service`. They never duplicate pipeline logic.
- **`POST /api/analyze`** is analysis-only and must never save to the database. Saving is exclusively done via `POST /api/reports/analyze`.
- **CLI** must remain functional. Adding API or frontend layers must not break `python -m app.main`.
- **Database** uses SQLAlchemy Core (not ORM). The `analysis_reports` table stores full `StockReport` JSON snapshots alongside indexed summary columns. The `watchlists` and `watchlist_tickers` tables store named ticker lists. The `portfolios` and `portfolio_holdings` tables store manually entered holdings (`shares`/`average_cost` persisted as canonical decimal strings for exact precision; one ticker per portfolio via a unique constraint). The database file lives at `data/investment_bot.db` (configurable via `DATABASE_PATH` env var). Schema is created directly via `metadata.create_all()`; there are no migrations (do not add Alembic without a scoped task).
- **Persistence service functions** accept an optional `engine` keyword argument for test injection. Production callers omit it; a shared engine is lazily initialised on first call.
- **Watchlist management** (`watchlist_service` + `/api/watchlists`) is storage/CRUD only — it never runs analysis, scans, alerts, or trades. It is separate from `app/watchlist.py`, which is the CLI multi-ticker analysis scanner. Do not merge the two; do not add analysis to the watchlist CRUD layer without an explicitly scoped task.
- **Portfolio holdings** (`portfolio_service` + `/api/portfolios`) are manually entered, real holdings for tracking only. `portfolio_service` is storage/CRUD and fetches no market data; `portfolio_summary_service` is the only place current prices are fetched (reusing `app/data/market_data`) and the only place portfolio math runs. Keep these two separate — do not fetch prices during CRUD, and do not put calculations in routes. This is decision-support only: never add broker links, order execution, cash balances, realized gains, dividends, tax lots, or automatic trading.
- **Stock discovery** (`discovery_service` + `/api/discovery`) is a layer *around* the existing analysis engine, never a second one. It must not define scores, weights, thresholds, categories, or confidence logic — `discovery_ranking` may only reorder existing `Rating` objects and explain the ordering. Every run stays bounded by `max_full_analysis` (ceiling 50) and is synchronous, on-demand, and unsaved: no scheduled scans, no background jobs, no persistence. Universes are static CSVs in `app/data/universes/` — never scraped or fetched at runtime. Per-ticker failures become `warnings`, never a failed request.
- **Frontend** owns no business logic: it calls the typed API client and formats results for display. It must not recalculate scores, categories, weights, portfolio totals, discovery ranking, or re-validate domain rules the backend already enforces (the holding-form check in `lib/portfolio` is pre-submit UX only; the backend stays authoritative).

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
| 3 | SQLite persistence — save StockReport snapshots, report history endpoints | **Milestone 1 complete** — `POST /api/reports/analyze`, `GET /api/reports/history`, `GET /api/reports/{id}` |
| 4 | React + Vite frontend — Milestone 1: shell with API connectivity | **Complete** — Dashboard + Analyze pages, health check, analyze-only and analyze-and-save flows |
| 5 | Watchlist management (frontend + backend routes) | **Complete (CRUD + analyze + snapshots)** — `watchlists`/`watchlist_tickers` tables, `watchlist_service`, `/api/watchlists` CRUD, Watchlists page. Analyze-watchlist (`watchlist_analysis_service` + `POST /api/watchlists/{id}/analyze`, partial success, not saved). Saved snapshots (`watchlist_analysis_snapshots(+_results)` tables, `watchlist_analysis_snapshot_service`, snapshot save/list/detail endpoints) with snapshot-detail page and success/average-score trend charts (`average_score` derived in the service) |
| 6 | Research notes and report history UI | **Report history UI done** — Saved Reports list (`/reports`) and Report Detail (`/reports/:id`) over the existing read endpoints. Research notes not started |
| — | Market-data chart (read-only) | **Done** — `market_data_service` + `GET /api/market-data/{ticker}/history`; daily price chart on the Analyze page (Lightweight Charts) |
| — | Personal portfolio holdings (manual) | **Milestone 1 complete** — `portfolios`/`portfolio_holdings` tables, `portfolio_service` (CRUD) + `portfolio_summary_service` (priced summary), `/api/portfolios` CRUD + `GET /{id}/summary`, Dashboard `PortfolioPanel`. Manual entry only; current-price valuation via existing market-data layer; partial-price-failure tolerant. No broker links, cash, realized gains, dividends, tax lots, or trading |
| — | Stock discovery engine | **Milestone 1 complete** — static `starter_large_cap` universe + `universe_loader`, stage-1 pre-screen, bounded full analysis (`max_full_analysis`, default 25/ceiling 50), six deterministic ranking modes (`overall`, `momentum`, `quality`, `value`, `defensive`, `avoid`), `GET /api/discovery(+/modes,/universes)`, Discover page. Rule-based and explainable; no ML, no LLM picks, no scoring changes, nothing saved or scheduled |
| 7 | Mock trading simulation (`app/simulation/`) | Not started |
| 8 | ML research layer (`app/ml/`) | Not started |
| 9 | Deployment and hardening | Not started |

See `docs/full_stack_product_architecture.md` for full scope of each phase.

**Current priority: code quality and research quality, not more dashboard polish.**
Do not start the next visual feature (e.g. per-ticker sparklines, batch
price-history endpoint) without an explicitly scoped task.
Snapshot/report/watchlist/portfolio/discovery concerns are separate and must stay separate.
Discovery is a bounded, on-demand research surface — do not extend it toward
scheduled scans, alerts, saved discovery runs, larger universes, ML, or
LLM-generated picks without an explicitly scoped task.
Portfolio holdings are manual-entry tracking only — do not extend them toward
paper trading, cash, realized P&L, dividends, tax lots, or broker links without
an explicitly scoped task.

## Non-Negotiable Guardrails

These apply to every phase and every task:

- **No live trading** — never connect to a broker or execute a real order
- **No broker APIs** — no Alpaca, Robinhood, IBKR, or any brokerage integration
- **No order execution** — no scheduled or triggered buy/sell of any kind
- **No options or margin** — equities only; no derivatives or leveraged positions
- **Portfolio is manual + read-only** — holdings are hand-entered for tracking; never connect a brokerage account, sync positions, or trade. No cash balances, realized gains, dividends, or tax lots
- **Discovery is research, not advice** — discovery output is a rule-based, explainable candidate list. Never generate picks with an LLM or ML model, never change scoring rules to make discovery "work", and never let a discovery run trigger an order, an alert, or a scheduled scan
- **No unbounded scans** — a single discovery request may never analyze more than `MAX_FULL_ANALYSIS_CEILING` tickers
- **No route-handler logic** — API routes call services; they never contain pipeline logic
- **No CLI regression** — `python -m app.main` must always work after any change
- **No premature ML** — do not add `app/ml/` until Phase 8 is explicitly scoped
- **No premature simulation** — do not add `app/simulation/` until Phase 7 is explicitly scoped
- **Frontend must not duplicate backend logic** — no scoring, signal calculation, category derivation, or persistence in frontend code; display only
- **Frontend data ownership** — frontend formats dates/numbers for display; it must never recalculate ratings, categories, or weights; all analysis stays in the backend
- **Frontend stack** — React + Vite + TypeScript; plain CSS; native fetch; React Router; see `docs/frontend_plan.md` for the full plan

## Key Docs

- `docs/project_plan.md` — version roadmap
- `docs/architecture.md` — full layer diagram
- `docs/full_stack_product_architecture.md` — full-stack product plan and phase roadmap
- `docs/frontend_plan.md` — frontend design and milestone plan (React + Vite; implementation not yet started)
- `docs/scoring_rules.md` — score weights and rating thresholds
- `docs/data_sources.md` — provider options and selection criteria
- `docs/development_log.md` — append an entry for each meaningful change
