# Investment Bot

A full-stack, personal stock research and decision-support platform: a Python
analysis engine with a FastAPI + SQLite backend, a React + TypeScript frontend,
and a CLI.

> **Disclaimer:** This project is for personal research and education only.
> It does not provide financial advice and is **not** an automated trading system.
> Treat every output as a starting point for your own due diligence, not as a
> recommendation to buy, sell, or hold any security.

## What it does

For any U.S. ticker, the engine fetches price history, company fundamentals, and
recent headlines from yfinance. It computes technical, fundamental, news, and
risk signals and combines them into a transparent, rule-based composite score
and rating. Around that engine sit:

- **Reports**: plain-text, Markdown, and JSON output, plus saved report history.
- **Watchlists**: named ticker lists, on-demand analysis, and saved historical
  snapshots with trend charts.
- **Discovery**: bounded, explainable candidate ranking over a static stock universe.
- **Portfolio tracking**: hand-entered real holdings, valued at current prices.
- **Paper trading**: a self-contained simulation with a made-up cash balance and
  hand-entered trades.

It never places a trade, connects to a broker, or touches a real account.

## Tech stack

| Area | Technology |
|------|------------|
| Analysis | Python 3, pandas, Pydantic v2 |
| Market data | yfinance (no API key needed) |
| Backend | FastAPI, Uvicorn |
| Persistence | SQLite via SQLAlchemy Core (no ORM, no migration tool) |
| Frontend | React 19, TypeScript, Vite, React Router, Lightweight Charts, plain CSS |
| Tests | pytest (backend), Vitest (frontend helpers) |

## Features

**Full stack (API + UI):**

| Feature | What you get |
|---------|--------------|
| Stock analysis | 7 technical, 5 fundamental, 3 news, and 4–5 risk signals; weighted composite score, rating category, confidence level, key positives/risks, and trigger notes. Optional save to history. Daily price chart |
| Saved reports | Browse saved analyses and open any one in full |
| Watchlists | CRUD for named ticker lists; on-demand analysis (partial success, not saved); explicit "analyze & save snapshot" with a snapshot detail view and success-count / average-score trend chart |
| Discovery | Six deterministic ranking modes (`overall`, `momentum`, `quality`, `value`, `defensive`, `avoid`) over the `starter_large_cap` universe. Each run is bounded (≤ 50 full analyses), unsaved, and explains why each candidate surfaced |
| Portfolio | Manually entered holdings with cost basis, current market value, unrealized gain/loss, return, and weight. Unavailable prices show as unavailable, never as zero |
| Paper trading | Simulated accounts with a made-up starting cash balance; buys/sells at prices you type; decimal-exact cash, positions, realized/unrealized gain/loss, and an append-only transaction ledger |

**CLI only:** analyzing a plain-text watchlist file, and saving `.txt`, `.md`, or
`.json` output to `outputs/`.

**API only:** a few read endpoints the UI doesn't use (e.g.
`GET /api/portfolios/{id}`, `GET /api/paper-trading/accounts/{id}/positions`).

## Architecture

```
app/data/ ──► app/analysis/ ──► scoring.py ──► app/reports/ ──► app/services/ ──► CLI (app/main.py)
 yfinance      signals          Rating        StockReport      business logic  └► API (app/api/) ──► frontend/
 + SQLite
```

- **`app/data/`**: fetches and validates raw data (yfinance, static universe
  CSVs) and owns the SQLite schema. No analysis.
- **`app/analysis/`**: independent signal builders plus the single scoring
  engine (`scoring.py`).
- **`app/reports/`**: turns a `Rating` into a `StockReport` and text/Markdown.
- **`app/services/`**: every use case (analysis, persistence, watchlists,
  snapshots, portfolio, discovery, paper trading). The only layer the CLI and
  API call.
- **`app/api/`**: thin FastAPI routes that validate input, call one service, and
  map domain errors to HTTP status codes.
- **`frontend/`**: display-only React app. It calls the API through one typed
  client and never recomputes scores, totals, or rankings.

Paper trading is a separate vertical. It shares no tables or code with portfolio
tracking and never reads or influences analysis output.

## Getting started

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No API keys are required. `.env` is optional; copy `.env.example` only to
change `DATABASE_PATH` (default `data/investment_bot.db`, created on first use).

```bash
uvicorn app.api.main:app --reload  # http://127.0.0.1:8000, interactive docs at /docs
```

### Frontend

Requires Node 22 LTS (≥ 22.13, pinned in `frontend/.nvmrc`) and the backend running.

```bash
cd frontend
nvm use                            # optional
cp .env.example .env               # points the app at http://127.0.0.1:8000
npm install
npm run dev                        # http://localhost:5173
```

### CLI

```bash
python -m app.main AAPL                                   # print a report
python -m app.main AAPL --save-report --save-markdown --save-json
python -m app.main --watchlist watchlists/default.txt     # ranked summary table
python -m app.main --help
```

Watchlist files are plain text, one ticker per line. Blank lines and `#`
comments are ignored, and tickers are normalized and deduplicated.

## API

All routes live under `/api`. Domain validation errors return 400. Malformed
request bodies or query parameters, and data or analysis failures on `analyze`
and market-data calls, return 422. Missing resources return 404, and state
conflicts (duplicate holding, insufficient cash or shares) return 409.

| Group | Endpoints |
|-------|-----------|
| Health | `GET /health` |
| Analysis | `POST /analyze` (analysis only, never saves) |
| Reports | `POST /reports/analyze` (analyze + save), `GET /reports/history?limit=` (1–500), `GET /reports/{id}` |
| Watchlists | `GET/POST /watchlists`, `GET/PATCH/DELETE /watchlists/{id}`, `POST /watchlists/{id}/tickers`, `DELETE /watchlists/{id}/tickers/{ticker}`, `POST /watchlists/{id}/analyze` |
| Snapshots | `POST/GET /watchlists/{id}/analysis-snapshots`, `GET /watchlist-analysis-snapshots/{id}` |
| Market data | `GET /market-data/{ticker}/history?period=&interval=` |
| Portfolios | `GET/POST /portfolios`, `GET/PATCH/DELETE /portfolios/{id}`, `POST /portfolios/{id}/holdings`, `PATCH/DELETE /portfolios/{id}/holdings/{holding_id}`, `GET /portfolios/{id}/summary` |
| Discovery | `GET /discovery?mode=&universe=&limit=&max_full_analysis=`, `GET /discovery/modes`, `GET /discovery/universes` |
| Paper trading | `GET/POST /paper-trading/accounts`, `GET /paper-trading/accounts/{id}` plus `/summary`, `/positions`, `/transactions`, `POST .../buy`, `POST .../sell` |

Priced reads (portfolio summary, paper-trading summary and positions, discovery)
return 200 even when some prices are unavailable. Affected rows are flagged and
listed in `warnings`.

## Scoring

Each signal carries a `score_impact` in `[-1, 1]`. Within a category, impacts are
summed, clamped to `[-1, 1]`, and scaled to `[0, 100]`. Category scores are then
weighted: Technical 35%, Fundamental 25%, News 25%, Risk 15%. Weights are
re-normalized when a category is missing.

| Score | Category |
|-------|----------|
| ≥ 85 | Strong Buy Candidate |
| ≥ 70 | Buy Candidate |
| ≥ 55 | Watchlist |
| ≥ 45 | Hold |
| ≥ 30 | Avoid |
| < 30 | Sell / Exit Warning |

The weights and thresholds are the original hand-picked values. The
calibration documents in `docs/` are proposals, not shipped behavior.

## Testing

```bash
pytest                               # backend
cd frontend && npm test              # frontend helpers (Vitest)
cd frontend && npm run build         # type-check (tsc -b) + production build
cd frontend && npm run lint          # ESLint
```

Results as of the 2026-10-12 code review:

| Check | Result |
|-------|--------|
| `pytest` | 2066 passed, 0 failed, 0 skipped |
| `npm test` | 128 passed across 11 files |
| `npm run build` | succeeds |
| `npm run lint` | clean |

Backend tests are deterministic. They build DataFrames and models locally, mock
yfinance, and use temporary or in-memory SQLite databases. During the
2026-10-12 review the full suite also passed with network sockets blocked (a
one-off check, not an enforced fixture).
Frontend tests cover the pure helpers in `src/lib/` and the API modules in `src/api/` only;
there are no component or end-to-end tests. No Python linter or formatter is
configured.

## Project status

**Implemented:** the analysis pipeline and CLI, saved reports, watchlists with
on-demand analysis and saved snapshots, the market-data chart, manual portfolio
tracking, bounded discovery, paper trading, and the 8-page frontend.

**Partially implemented:**
- Phase 6 delivered report history, but research notes (free-text notes on
  reports and watchlists) are not started.
- Discovery has a single universe (`starter_large_cap`).
- Frontend test coverage is limited to pure helpers.
- The dashboard's "Market Overview" card is a labeled placeholder; no live index
  data is connected.

**Not implemented (intentionally or not yet scoped):** authentication,
deployment, ML/LLM models, backtesting, scoring calibration changes,
market-data caching, and price-staleness detection.

## Guardrails

These are out of scope permanently, not just unbuilt:

- Live trading and real order execution of any kind
- Broker integrations (Vanguard, Schwab, Plaid, Alpaca, Robinhood, Interactive
  Brokers, or any other), real account linking, or position syncing
- Automatic trading, rebalancing, position management, trade alerts, or
  allocation advice
- Margin, options, or short selling. A paper sell can never exceed the shares held

Paper trading is the one simulation. Every paper trade is a database row the
user entered, at a price the user supplied.

## Repository layout

```
app/
  main.py            CLI (argparse)
  config.py          DATABASE_PATH from the environment
  watchlist.py       CLI watchlist-file loader, scanner, and table formatter
  api/               FastAPI app, routes/, schemas/, shared error tuple
  services/          use-case layer (13 modules)
  data/              yfinance fetchers, SQLite schema, file storage, universe loader + universes/*.csv
  analysis/          technicals, fundamentals, news, risk signal builders; scoring.py
  reports/           StockReport assembly and text/Markdown templates
  models/            Pydantic domain models
  utils/helpers.py   safe_float, normalize_ticker
frontend/src/
  api/               typed fetch client + one module per API group
  pages/             8 routed pages
  components/        presentational components (layout, charts, portfolio, discovery, paper trading, …)
  lib/               pure, unit-tested display helpers
  types/             TypeScript mirrors of the backend schemas
tests/               pytest suite (42 files)
docs/                development log, scoring rules, architecture notes, historical plans
watchlists/          sample watchlist files for the CLI
outputs/             CLI-saved reports; tracked samples are cited by the calibration notes
```

See `CLAUDE.md` for the detailed implementation guide and
`docs/development_log.md` for the change history.
