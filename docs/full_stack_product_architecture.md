# Full-Stack Product Architecture Plan

## 1. Product Vision

This project is a **personal investment research and decision-support platform**. Its purpose is to help an individual investor research stocks systematically — fetching data, computing signals, scoring them, and surfacing structured reports — so that investment decisions are more informed and consistent.

**This is not a live trading system.** It does not execute orders, connect to broker APIs, manage real money, or automate any buy/sell decision. That boundary is permanent at the core design level, not a temporary limitation.

The current CLI analysis engine is the foundation. Going forward it becomes the **core backend research engine**: a stable, well-tested library of data fetching, signal computation, scoring, and report assembly that a FastAPI backend exposes to a Next.js frontend. The CLI remains functional and is not replaced.

---

## 2. Current Architecture Baseline

The current system is a pure Python CLI tool organized into four logical layers:

```
app/data/           — fetch and validate raw data (yfinance)
app/analysis/       — compute signals from data; modules are independent
app/analysis/scoring.py — aggregate signals into a composite Rating
app/reports/        — format a Rating into a human-readable StockReport
app/services/       — orchestrate the pipeline; public entry points for callers
app/main.py         — thin argparse CLI shell; delegates to services
```

**Service boundary:**
`app/services/stock_analysis_service.py` is the stable public contract between the analysis engine and any caller (CLI today, API tomorrow):

| Function | Returns | Notes |
|---|---|---|
| `analyze_stock(ticker)` | `StockReport` | Primary entry point; use this in all new callers |
| `analyze_watchlist_file(path)` | `list[WatchlistResult]` | Scan a watchlist file |
| `_analyze_ticker(ticker)` | `Rating` | **Internal only.** Not a public API. |

Any future API layer, frontend backend, or tool must call `analyze_stock` — never `_analyze_ticker` directly.

---

## 3. Target Full-Stack Architecture

### Technology Choices

| Layer | Choice | Rationale |
|---|---|---|
| Backend API | **FastAPI** | Async-capable, typed, auto-generates OpenAPI docs, Python-native — no context switch from the existing engine |
| Frontend framework | **Next.js + React + TypeScript** | File-based routing, SSR/SSG options, strong ecosystem, typed |
| Styling | **Tailwind CSS + shadcn/ui** | Utility-first CSS with a composable component library; avoids opinionated design lock-in |
| Database (initial) | **SQLite** | Zero infrastructure for local development; fine for a single-user personal tool |
| Database (later) | **PostgreSQL** | Migrate when multi-user support or deployment requires it |
| Charts | **Recharts or lightweight-charts** | Add in a later phase once the data pipeline to the frontend is stable |

### Data Flow

```
User (browser)
    │
    ▼
Next.js frontend
    │  HTTP JSON
    ▼
FastAPI backend (app/api/)
    │  Python function call
    ▼
app/services/stock_analysis_service.analyze_stock()
    │
    ▼
app/data/ → app/analysis/ → app/analysis/scoring.py → app/reports/
    │
    ▼
StockReport
    │
    ├──► JSON API response → frontend
    └──► app/db/  (persist snapshot for history)
```

### Why wrap instead of duplicate

The API layer's only job is to receive a request, call the service, and return the result. It must not contain scoring logic, signal computation, or data fetching. That logic already exists in the engine and is tested there. Duplicating it in route handlers creates two sources of truth that will drift apart.

---

## 4. Proposed Future Repository Structure

```
app/
├── api/                  # FastAPI routers and request/response schemas
│   ├── __init__.py
│   ├── main.py           # FastAPI app factory
│   └── routes/
│       ├── health.py
│       ├── analyze.py
│       ├── watchlists.py
│       ├── reports.py
│       └── notes.py
├── db/                   # Database models, migrations, session management
│   ├── __init__.py
│   ├── models.py
│   └── session.py
├── services/             # Existing — orchestration, public entry points
├── data/                 # Existing — data fetching
├── analysis/             # Existing — signal computation and scoring
├── reports/              # Existing — report formatting
├── models/               # Existing — Pydantic models (Signal, Rating, StockReport, etc.)
├── ml/                   # FUTURE PHASE — ML feature engineering, training, inference
│   └── (not yet)
├── simulation/           # FUTURE PHASE — mock trade tracking and portfolio simulation
│   └── (not yet)
├── utils/                # Existing — shared helpers
├── config.py             # Existing
└── main.py               # Existing CLI entry point

frontend/
├── src/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # React components
│   ├── lib/              # API client, utilities
│   └── types/            # TypeScript types mirroring API schemas
├── public/
├── package.json
└── tsconfig.json

docs/
tests/
requirements.txt
```

`app/ml/` and `app/simulation/` are placeholders for future phases. Do not create or populate them until those phases are explicitly scoped.

---

## 5. Backend API Guidelines

### Initial routes (Phase 2)

```
GET  /api/health         — liveness check; returns {"status": "ok"}
POST /api/analyze        — run analyze_stock for a ticker; return StockReport as JSON
```

`POST /api/analyze` request body:
```json
{ "ticker": "AAPL" }
```

Response: the `StockReport` serialized via `model.model_dump(mode="json")`.

### Later routes (Phases 3–6)

```
GET  /api/reports/history          — paginated list of saved StockReport snapshots
GET  /api/reports/{id}             — retrieve a specific saved report
GET  /api/watchlists               — list watchlists
POST /api/watchlists               — create a watchlist
GET  /api/watchlists/{id}/scan     — run analyze_stock for every ticker in a watchlist
POST /api/notes                    — save a research note linked to a ticker/report
GET  /api/notes                    — list notes with optional ticker filter
POST /api/mock-trades              — record a simulated trade decision
GET  /api/mock-portfolio           — current simulated positions and performance
```

### Route handler rules

- Route handlers must be thin. Validate the request, call the service, return the result.
- No signal computation, scoring logic, or data fetching in route handlers.
- No database query logic directly in route handlers — delegate to a repository or service function.
- Input validation should use Pydantic request schemas, not ad hoc `if` checks.

---

## 6. Frontend Guidelines

The frontend is a **real application**, not a throwaway dashboard. It should be structured as a maintainable Next.js project with typed components, clear page boundaries, and proper API integration.

### Frontend rules

- The frontend calls the FastAPI backend only. It has no knowledge of yfinance, scoring weights, signal categories, or any internal analysis code.
- All data comes through the API. No direct database access from the frontend.
- API types should be mirrored in `frontend/src/types/` as TypeScript interfaces generated from or manually synchronized with the FastAPI OpenAPI schema.

### Initial screens

| Screen | Purpose |
|---|---|
| Dashboard | Entry point; recent reports, watchlist summary, quick analyze input |
| Stock Analysis | Input ticker, trigger analysis, display full StockReport |
| Watchlist | Manage watchlists; run a scan; view ranked summary |
| Report History | Browse and search saved StockReport snapshots |
| Research Notes | View, add, and filter personal notes linked to tickers |
| Mock Portfolio | Later phase — simulated positions, trade log, performance summary |

### UI requirements

Loading, error, and empty states are **first-class requirements** for every page, not afterthoughts:

- **Loading:** show a skeleton or spinner while the API request is in-flight.
- **Error:** show a clear, actionable error message when the API returns an error or the network fails. Do not silently fail.
- **Empty:** show meaningful empty states when there are no reports, no watchlist items, or no notes yet.

---

## 7. Database / Persistence Guidelines

### Technology progression

Start with **SQLite** using a file-local database (`data/trading_bot.db` or similar). No server to run, no Docker required, no environment configuration. SQLite is appropriate for a single-user personal tool indefinitely.

Migrate to **PostgreSQL** only when one of these conditions is true:
- The tool is deployed to a server that needs to be accessible from multiple devices.
- Concurrent writes become a bottleneck.
- A managed cloud database makes backup/recovery easier.

### Likely tables

| Table | Purpose |
|---|---|
| `analysis_reports` | Saved StockReport snapshots (JSON blob + key fields indexed) |
| `watchlists` | Named lists of tickers |
| `watchlist_items` | Tickers belonging to a watchlist |
| `research_notes` | Free-text notes linked to a ticker and optionally a report |
| `mock_trades` | Simulated trade decisions (ticker, direction, price, date, linked report) |
| `mock_positions` | Current simulated positions derived from mock trades |

### Persistence approach

Initial persistence should focus on a single thing: **saving `StockReport` snapshots**. Store the full JSON blob plus a handful of indexed scalar fields (`ticker`, `score`, `final_category`, `data_timestamp`) to support history queries and filtering.

Do not redesign the `StockReport` model to fit a normalized database schema prematurely. The JSON snapshot approach keeps persistence decoupled from the analysis engine's internal model evolution.

---

## 8. Machine Learning Upgrade Guidelines

ML is a **later phase**. The current rule-based scoring system is transparent, debuggable, and already well-calibrated. Do not introduce ML until the full-stack product is stable and there is a clear, scoped reason to do so.

### Principles

- Keep the current rule-based scoring system intact. It is the baseline and the fallback.
- ML outputs must be **explainable**. An ML model that silently overrides a rule-based score is not acceptable. The system must show both the rule-based score and any ML-assisted adjustment, with reasoning.
- ML should augment the scoring system, not replace it without justification.

### Proposed `app/ml/` structure (future)

```
app/ml/
├── features/       — feature engineering from StockReport / Signal data
├── datasets/       — dataset assembly and versioning
├── training/       — model training pipelines
├── inference/      — inference wrappers called by the service layer
└── evaluation/     — backtesting, metric tracking, model comparison
```

### Initial ML goal

The first ML goal should be **signal evaluation**: given historical StockReport snapshots and subsequent price outcomes, train a model to assess which signals are most predictive. This is research tooling, not automated trading.

---

## 9. Mock Trading / Simulation Guidelines

Mock trading is a **later phase** under `app/simulation/`. It will never connect to a real broker or execute real orders.

### What mock trading is

- A paper-trading journal: the user records a simulated trade decision (e.g., "I would have bought 10 shares of AAPL at $185 on 2026-01-15") linked to the `StockReport` rating available at that time.
- The system tracks hypothetical cash, simulated positions, simulated returns, and performance metrics (win rate, average gain/loss, drawdown).
- The simulation helps the user evaluate whether their research process leads to good decisions over time.

### What mock trading is not

- Not connected to any broker API.
- Not executing real trades.
- Not managing real money.
- Not simulating margin, leverage, options, or short selling.
- Not an automated strategy runner or backtesting engine.

### Linkage to research

Every mock trade should reference the `analysis_report` row that supported the decision. This creates an auditable record: "I made this simulated trade because of this rating at this time."

---

## 10. Safety and Scope Guardrails

These constraints apply to all phases and all contributors:

| Guardrail | Rule |
|---|---|
| No live trading | The system never connects to a broker or executes a real order — ever |
| No broker integration | No Alpaca, Robinhood, IBKR, or any brokerage API |
| No automatic execution | No scheduled job, trigger, or agent that places a buy/sell order |
| No options / margin | Scope is equities only; no derivatives, no leveraged positions |
| No frontend analysis logic | The frontend calls the API; it never runs scoring or signal code |
| No route handler logic | API route handlers call services; they never contain business logic |
| No CLI regression | Adding API and frontend layers must not change or break existing CLI behavior |
| No premature ML | Do not add `app/ml/` code until the full-stack baseline is stable |
| No premature simulation | Do not add `app/simulation/` code until persistence and history are working |

---

## 11. Recommended Implementation Sequence

| Phase | Milestone | Scope |
|---|---|---|
| **1** | Architecture alignment | This document. No code changes. ✓ Done |
| **2** | FastAPI backend — core | `app/api/`, `GET /api/health`, `POST /api/analyze`; wraps `analyze_stock`; no database yet. ✓ Done |
| **3** | Database persistence | `app/db/`, SQLite, save `StockReport` snapshots, `GET /api/reports/history` |
| **4** | Next.js frontend foundation | Project scaffold, API client, Dashboard page, Stock Analysis page |
| **5** | Watchlist management | Backend routes + frontend Watchlist page; scan and display ranked results |
| **6** | Research notes and report history | Notes CRUD, report history page, ticker-linked browsing |
| **7** | Mock trading simulation | `app/simulation/`, mock trade recording, portfolio summary, performance metrics |
| **8** | ML research layer | `app/ml/`, feature engineering from historical snapshots, signal evaluation models |
| **9** | Deployment and hardening | Environment config, containerization, auth if needed, PostgreSQL migration if needed |

Each phase must be completable independently. A phase is not started until the previous phase's core functionality is tested and stable.

---

## 12. Immediate Next Step

~~FastAPI Backend — Phase 2 is complete.~~ The next code milestone is **Database Persistence — Phase 3**.

Scope:
- Create `app/db/` package with SQLite session management and ORM models.
- Save `StockReport` snapshots to an `analysis_reports` table on every `POST /api/analyze` call.
- Implement `GET /api/reports/history` returning a paginated list of saved reports.
- Implement `GET /api/reports/{id}` returning a single saved report.
- Use SQLite for local development. No migration to PostgreSQL yet.

**Do not add** in Phase 3: frontend, ML, simulation, authentication, watchlist endpoints, or mock trading.
