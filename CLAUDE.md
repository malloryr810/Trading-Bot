# CLAUDE.md

This file is the implementation guide for Claude Code (claude.ai/code) in this
repository. Trust the code first, then this file. Older planning docs in `docs/`
are historical.

## Project purpose

A personal, full-stack stock research and decision-support platform. A Python
pipeline fetches market data, computes signals, and scores them with a
transparent rule-based engine. The results reach a CLI, a FastAPI + SQLite
backend, and a display-only React frontend.

**It is not an automated trading system.** Do not implement:
- Broker API calls or integrations (Vanguard, Schwab, Plaid, Alpaca, Robinhood, IBKR, or any other)
- Real order execution, live trading, real account linking, or position syncing
- Automatic trading, rebalancing, or position management; trade alerts or allocation advice
- Margin, options, or short selling
- ML/LLM models (`app/ml/` is Phase 8 — do not create it)
- Backtesting (unless explicitly scoped and approved)

**Paper trading is the one simulation.** The user hand-enters buys and sells
against a made-up cash balance, at prices they supply. It contacts no market and
places no real order. Everything above still applies to it.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # runtime + test deps (sections commented)

# API server (http://127.0.0.1:8000, docs at /docs)
uvicorn app.api.main:app --reload

# CLI
python -m app.main AAPL [--save-report] [--save-json] [--save-markdown]
python -m app.main --watchlist watchlists/default.txt [--save-report] [--save-json] [--save-markdown]
python -m app.main --help

# Backend tests
pytest
pytest tests/test_risk_analysis.py       # one file
python -m py_compile app/analysis/scoring.py

# Frontend (Node 22 LTS ≥ 22.13 per frontend/.nvmrc)
cd frontend
nvm use && npm install                   # first time; cp .env.example .env if needed
npm run dev                              # http://localhost:5173 (backend must be running)
npm test                                 # Vitest — pure helpers only
npm run build                            # tsc -b type-check + production build
npm run lint                             # ESLint
```

Never run `npm audit fix --force`. The known dev-only esbuild advisory is
documented in `docs/development_log.md`, and the forced fix downgrades Vitest
and breaks the test harness.

### Verification workflow

Run after any meaningful change, in this order:

```bash
python -m pytest                      # must stay fully green
python -m app.main AAPL               # CLI smoke test (hits the network)
cd frontend && npm test               # if frontend files changed
cd frontend && npm run build          # the only type-check; catches backend↔frontend contract drift
cd frontend && npm run lint
```

## Directory architecture

| Path | Responsibility |
|------|----------------|
| `app/data/` | Fetch and validate raw data. `market_data.py` (yfinance OHLCV + `latest_valid_close`, the canonical current-price reader, which never returns 0 for "unavailable"; `yf.download` is serialized behind a lock because it shares module-level state), `fundamentals.py`, `news_data.py`, `storage.py` (CLI file output to `outputs/`), `universe_loader.py` + `universes/*.csv` (static discovery universes, no network), `database.py` (SQLAlchemy Core schema, `build_engine`, `as_utc`, `begin_write_transaction`) |
| `app/analysis/` | `technicals.py`, `fundamentals_analysis.py`, `news_analysis.py`, `risk_analysis.py` each return `list[Signal]`. `scoring.py` has `score_signals()`, the only scoring entry point |
| `app/models/` | Pydantic domain models: `Signal`, `Rating`, `ConfidenceDiagnostics`, `StockReport`, `CompanyFundamentals`, `NewsItem`, `UniverseEntry/Info`, discovery models, price-history models (`market_data.py`) |
| `app/reports/` | `report_generator.build_stock_report()` (Rating → StockReport) and `templates.py` (plain text, Markdown, watchlist Markdown) |
| `app/services/` | Every use case. See the service table below |
| `app/api/` | `main.py` (app factory + CORS for the Vite origins), `routes/` (9 thin modules, 37 endpoints), `schemas/` (request/response shapes; discovery and market-data schemas re-export domain models), `errors.py` (`KNOWN_ANALYSIS_ERRORS` → 422) |
| `app/main.py` | argparse CLI. Calls `app/services/` only |
| `app/watchlist.py` | CLI watchlist *file* loader, multi-ticker scanner, and summary-table formatter. Separate from the DB-backed watchlist service, and the two must stay separate |
| `app/config.py` | `DATABASE_PATH` (default `data/investment_bot.db`). Any future secret goes here, read from `.env` |
| `frontend/src/api/` | `client.ts` (the only `fetch`; `ApiError`; `VITE_API_BASE_URL`) + one module per API group, one function per endpoint |
| `frontend/src/pages/` | Dashboard, Discover, Analyze, Watchlists, Snapshot Detail, Saved Reports, Report Detail, Paper Trading |
| `frontend/src/components/` | Presentational components (`layout/`, `charts/`, `dashboard/`, `watchlist/`, `portfolio/`, `discovery/`, `paperTrading/`). `PortfolioPanel` is the one container component |
| `frontend/src/lib/` | Pure, unit-tested display helpers (formatting, sorting, chart shaping, form pre-validation) |
| `frontend/src/types/` | TypeScript mirrors of backend schemas |
| `tests/` | pytest suite, one file per module or route group |
| `docs/` | `development_log.md` (append per change), `scoring_rules.md`, `architecture.md`, `data_sources.md`; plans and calibration docs are historical/proposals |

### Services

| Module | Role |
|--------|------|
| `stock_analysis_service` | `analyze_stock` (→ StockReport) and `analyze_stock_rating` (→ Rating with sub-scores, for discovery): the only pipeline entry points. `analyze_watchlist_file` for the CLI |
| `report_persistence_service` | Save, list, and get saved reports |
| `watchlist_service` | Watchlist + ticker CRUD (storage only) |
| `watchlist_analysis_service` | `analyze_watchlist`: runs `analyze_stock` per ticker; partial success; saves nothing |
| `watchlist_analysis_snapshot_service` | Save, list, and get snapshots of explicit analyze-and-save runs; derives `average_score` |
| `market_data_service` | Validated, JSON-safe price-history response |
| `portfolio_service` / `portfolio_summary_service` | Holdings CRUD (no market data) / priced summary (the only place portfolio prices are fetched and portfolio math runs) |
| `discovery_service` / `discovery_screening` / `discovery_ranking` | Universe → bounded pre-screen → `analyze_stock_rating` → per-mode ordering |
| `paper_trading_service` / `paper_trading_summary_service` | Accounts, trades, positions, ledger (no market data) / priced positions + valued summary |

Persistence services take an optional `engine=` keyword for tests. Production
callers omit it and get a lazily built module-level engine. Summary services
also take `price_lookup=`, and discovery takes `analyze=`/`prescreen=`.

## Dependency direction

```
app/data ─► app/analysis ─► scoring.py ─► app/reports ─► app/services ─► app/main.py (CLI)
   ▲                                                         │      └──► app/api ─► frontend (HTTP)
   └──────────────── app/models (shared by all layers) ◄─────┘
```

- Lower layers never import upward. Nothing outside `app/api/` imports
  `app.api.*`, and nothing imports `app.main`.
- Models are domain types. API schemas may re-export them; services must not
  import API schemas.
- `stock_analysis_service` may use `app/watchlist.py`'s pure scanner for the
  CLI. Nothing in the API path depends on it.

## Architectural rules

- **Data modules** fetch and clean only: no analysis or scoring. Missing or
  invalid prices are `None`, never 0.
- **Analysis modules** take a DataFrame or typed model, never call yfinance,
  and never import each other. Missing fields produce a neutral `Signal` with
  `confidence=0.30` rather than raising. Each module has its own exception class.
  News fetch failures are non-fatal in the pipeline (`analyze_news([])`).
- **Scoring** lives only in `scoring.py`. It is transparent and rule-based. Do
  not change weights, thresholds, or confidence logic without an explicitly
  scoped task.
- **Reports** consume a `Rating`; they never run analysis or scoring.
- **API route handlers are plain `def`, not `async def`.** Every service blocks
  (SQLite, yfinance), and FastAPI runs sync handlers in a threadpool; an async
  handler would stall the whole server. A test enforces this. Because requests
  now run concurrently, any service that reads a value and then writes
  something computed from it must call `begin_write_transaction(conn)` first
  inside `engine.begin()` (paper trades do). Schema creation in `build_engine`
  is serialized by a lock.
- **Routes stay thin.** Validate input, call one service, and map *domain*
  errors to status codes: `*ValidationError` → 400, `*NotFoundError` → 404,
  duplicate / insufficient funds or shares → 409, `KNOWN_ANALYSIS_ERRORS` → 422,
  anything else → 500. Do not catch bare `ValueError`/`LookupError` next to a
  domain error, which would turn bugs into 400/404s. (The one deliberate
  exception: the market-data route maps the service's documented `ValueError`
  for an unsupported period or interval to 422.) No pipeline, persistence, or
  math in a route.
- **`POST /api/analyze` never saves.** Saving is only via `POST /api/reports/analyze`.
- **Watchlist CRUD** never runs analysis. On-demand analysis and snapshots are
  separate services. Snapshots are only written by an explicit user action, and
  never by a schedule.
- **Portfolio holdings** are manual-entry tracking of real holdings: no cash,
  realized P&L, dividends, tax lots, or broker links. Keep CRUD and pricing in
  their separate modules.
- **Discovery** is a layer *around* the engine. It may only reorder existing
  `Rating`s and explain the order; it must not define scores, weights,
  thresholds, or categories. Every run is synchronous, on-demand, unsaved, and
  bounded by `max_full_analysis` (ceiling `MAX_FULL_ANALYSIS_CEILING` = 50).
  Universes are static CSVs. Per-ticker failures become `warnings`, never a
  failed request.
- **Paper trading** sits entirely outside the research spine. It is never read
  by, and never affects, ratings, reports, discovery, watchlists, or portfolio
  summaries, and it shares no tables or code with portfolio tracking (the
  duplicated price/rounding helpers in the two summary services are deliberate).
  The transaction table is an append-only ledger and the source of truth.
  Positions are a derived cache written in the same DB transaction as the cash
  movement. Two invariants must hold after every trade, and tests cover both:
  `cash_balance == starting_cash - Σ(buy gross) + Σ(sell gross)` and
  `realized_gain_loss == Σ(transaction realized)`.
- **Frontend** owns no business logic. All HTTP goes through `src/api/client.ts`
  via the per-group API modules. It formats for display and never recomputes
  scores, categories, weights, averages, totals, rankings, or accounting.
  Client-side form checks are UX only; the backend stays authoritative. Async
  loads that can be superseded (selection changes) must drop stale responses
  (see `PaperTradingPage.refreshView`, `PortfolioPanel.loadSummary`).
- **Dependencies:** add none without a clear need. No Redux/Zustand/React
  Query, no second chart library, no ORM, and no migration framework (no
  Alembic) without a scoped task.

## Data model (SQLite, `app/data/database.py`)

The schema comes from `metadata.create_all()`; there are no migrations. The one
exception is `_upgrade_legacy_watchlists_table`, which `build_engine` runs: a
one-time, idempotent in-place rebuild that gives pre-existing databases an
AUTOINCREMENT `watchlists` table. Foreign keys are declared but not enforced
(no `PRAGMA foreign_keys`), so services delete child rows explicitly.

| Table | Contents |
|-------|----------|
| `analysis_reports` | Saved `StockReport` JSON plus indexed summary columns |
| `watchlists` | Named ticker lists. **AUTOINCREMENT**: deleted ids are never reused, because snapshots outlive their watchlist and are looked up by `watchlist_id` |
| `watchlist_tickers` | Tickers per watchlist (unique per list); deleted with the list |
| `watchlist_analysis_snapshots` | One row per explicit analyze-and-save run; `watchlist_name` denormalized; **kept** when the watchlist is deleted |
| `watchlist_analysis_snapshot_results` | Per-ticker success/failure rows of a snapshot |
| `portfolios` / `portfolio_holdings` | Manual holdings; `shares`/`average_cost` stored as canonical decimal strings; one ticker per portfolio; holdings deleted with the portfolio |
| `paper_trading_accounts` | Simulated cash, starting cash, cumulative realized gain/loss (decimal strings) |
| `paper_trading_transactions` | Append-only BUY/SELL ledger |
| `paper_trading_positions` | Derived open positions (one per ticker per account; deleted when fully sold) |

SQLite returns naive datetimes. Every service normalizes them through `as_utc`.

## API status

Route groups (all under `/api`): health; analysis; reports (analyze + save,
history with `limit` 1–500, detail); watchlists (CRUD, tickers, on-demand
analyze); watchlist snapshots; market-data history; portfolios (CRUD, holdings,
priced summary); discovery (run, modes, universes); paper trading (accounts,
detail, summary, positions, transactions, buy, sell). Priced reads return 200
on partial price failure, with `warnings`.

## Feature status

| Feature | Status |
|---------|--------|
| Analysis pipeline, CLI, report formats | Complete |
| Saved reports (API + Saved Reports / Report Detail pages) | Complete |
| Watchlists: CRUD, on-demand analysis, saved snapshots + trend chart | Complete |
| Market-data price chart (Analyze page) | Complete |
| Manual portfolio tracking (Dashboard panel) | Complete (milestone 1) |
| Stock discovery (Discover page) | Complete (milestone 1); one universe |
| Paper trading (backend + page) | Complete |
| Research notes (Phase 6 remainder) | Not started |
| Scoring calibration (`docs/*calibration*` are proposals) | Not started |
| Market-data staleness detection (`TODO` in `market_data.py`) | Not started |
| Dashboard "Market Overview" | Labeled placeholder only. No live data; don't build it without a scoped task |
| ML (Phase 8), deployment/hardening (Phase 9), auth, backtesting | Not started |

## Testing guidance

- Every meaningful change ships with tests, one file per module or route
  group (`tests/test_<module>.py`; API tests in `test_<group>_api.py`).
- Tests must be deterministic: build DataFrames and models locally, patch
  yfinance (`app.data.market_data.yf.download`, etc.), and never call a live
  service. (Verified once by running the suite with sockets blocked; no
  fixture enforces it.)
- Persistence tests use `build_engine(tmp_path / "test.db")` and pass `engine=`.
  API tests either patch the service functions a route imports, or monkeypatch
  every involved service module's `_engine` to a temp engine. No test touches
  `data/investment_bot.db`.
- Assert behavior through public functions. Use `pytest.mark.parametrize` for
  boundary tables rather than copy-pasted tests. Add a regression test for
  every bug fixed (e.g. `tests/test_database.py` for watchlist id reuse).
- Frontend: Vitest covers `src/lib/` and `src/api/` only. New display logic
  belongs in a pure `lib/` helper with a test.

## Non-negotiable guardrails

- **No live trading, no broker APIs, no real order execution.** A paper trade
  is a database row at a user-supplied price; never fetch a price to "execute"
  a trade, and never route an order.
- **No real account linking or position syncing**, in either the portfolio or
  paper-trading verticals.
- **No automatic trading, rebalancing, or position management**, and no trade
  alerts or allocation advice.
- **No margin, options, or short selling.** A paper sell may never exceed the
  shares the account holds.
- **Discovery is research, not advice.** No ML/LLM picks, no scoring changes to
  make discovery "work", no scheduled scans, and never more than
  `MAX_FULL_ANALYSIS_CEILING` analyses per request.
- **No route-handler logic, no CLI regression** (`python -m app.main` must
  always work), and **no frontend business logic**.
- Secrets live only in `.env` (never committed) and are read through `app/config.py`.

## Next logical work

Only start these with an explicitly scoped task:
- Research notes on saved reports and watchlists (Phase 6 remainder).
- Market-data staleness detection (needs care with weekends and holidays).
- Component-level frontend tests for the container flows (PortfolioPanel,
  PaperTradingPage, WatchlistsPage).
- Scoring calibration, only through the documented proposal process.

Do not start the next visual feature (per-ticker sparklines, batch price
history, live market overview), widen paper trading (no "paper buy from
Discover", per-position charts, or CSV export), or extend discovery (scheduled
scans, saved runs, more universes) without a scoped task.

## Required post-implementation workflow

After every meaningful code change, use the project subagents in `.claude/agents/`:

1. **code-reviewer**: bugs, architecture issues, scope creep, security, and
   guardrail violations.
2. **test-runner**: the narrowest relevant tests, then a summary.
3. **docs-maintainer**: update docs only if the change made them stale.

Do not skip this unless the user explicitly says to skip review, tests, or docs.

For every completed task, report: files changed, tests run, subagents used,
issues found, and documentation updated (or not needed). Append an entry to
`docs/development_log.md` for each meaningful change.
