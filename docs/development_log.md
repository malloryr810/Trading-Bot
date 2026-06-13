# Development Log

## 2026-06-13 — Phase 5 Milestone 1: watchlist API routes (API + tests only)

**Goal:** expose the existing watchlist service over HTTP per
`docs/watchlist_management_plan.md`. API layer and tests only — no frontend, no
scoring/analysis/report/CLI changes.

**Schemas (`app/api/schemas/watchlists.py`, new)**

- Requests: `CreateWatchlistRequest` (name, description?), `UpdateWatchlistRequest`
  (name?, description?), `AddTickerRequest` (ticker).
- Responses: `WatchlistSummary` (list view, includes `ticker_count`),
  `WatchlistDetail` (single item, includes `tickers`), `DeleteResponse`.

**Routes (`app/api/routes/watchlists.py`, new)**

- `APIRouter(prefix="/watchlists", tags=["watchlists"])` with seven endpoints:
  `GET /api/watchlists`, `POST /api/watchlists`, `GET/PATCH/DELETE
  /api/watchlists/{id}`, `POST /api/watchlists/{id}/tickers`,
  `DELETE /api/watchlists/{id}/tickers/{ticker}`.
- Thin handlers: each calls the matching `watchlist_service` function. Mapping —
  `WatchlistValidationError`/`ValueError` → 400, `WatchlistNotFoundError`/
  `LookupError` → 404. Pydantic request validation surfaces as 422 (FastAPI
  default). `POST /api/watchlists` returns 201. No business logic in routes.

**App wiring + CORS (`app/api/main.py`)**

- Registered the watchlists router under `/api`.
- Widened CORS `allow_methods` from `["GET", "POST"]` to
  `["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` so the browser frontend can use
  the new verbs. Origins unchanged (still the two Vite localhost origins).

**Tests (`tests/test_watchlist_api.py`, new)**

- 35 integration tests via FastAPI `TestClient`, driving routes → real service →
  a temporary SQLite engine injected into the service module (no network, no real
  DB writes). Covers all seven endpoints: happy paths, 400 on blank name/ticker,
  404 on missing watchlist, ticker normalization, idempotent duplicate add and
  absent-ticker remove, and CORS preflight allowing PATCH/DELETE.

**Verification:** `pytest tests/test_watchlist_api.py` → 35 passed; full suite →
1569 passed. No frontend, scoring, analysis, report, or CLI behavior changed; the
only pre-existing endpoints touched are unaffected (CORS widening is additive).

## 2026-06-13 — Phase 5 Milestone 1: watchlist persistence + service (backend only)

**Goal:** lay the backend foundation for watchlist management per
`docs/watchlist_management_plan.md`. Storage and service layer only — no API
routes, no frontend, no scoring/analysis/report/CLI changes.

**Database (`app/data/database.py`)**

- Added two SQLAlchemy Core tables: `watchlists` (id, name, description,
  created_at, updated_at) and `watchlist_tickers` (id, watchlist_id FK →
  watchlists.id, ticker, created_at).
- `watchlist_tickers` carries a `UniqueConstraint(watchlist_id, ticker)` so a
  ticker appears at most once per list. Schema is intentionally minimal — no
  prices, scores, report ids, or analysis snapshots.

**Service (`app/services/watchlist_service.py`, new)**

- Public functions mirroring `report_persistence_service` style, each with an
  optional keyword-only `engine` for test injection:
  `create_watchlist`, `list_watchlists`, `get_watchlist`, `update_watchlist`,
  `delete_watchlist`, `add_ticker_to_watchlist`, `remove_ticker_from_watchlist`.
- Returns plain dicts with stable keys; watchlist detail includes a `tickers`
  list (insertion order). `list_watchlists` returns summaries with `ticker_count`.
- Validation: names stripped and required; blank/None descriptions collapse to
  None; tickers normalized via shared `normalize_ticker` (trim + uppercase);
  blank tickers rejected.
- Custom errors `WatchlistValidationError(ValueError)` and
  `WatchlistNotFoundError(LookupError)`. Get/update/delete on a missing id and
  add/remove ticker on a missing watchlist raise not-found (never silently
  create). Duplicate ticker adds and missing-ticker removals are idempotent.
- Watchlist deletion removes child ticker rows explicitly (does not rely on
  SQLite cascade, which is off by default here). Datetimes re-attached to UTC on
  read, matching the persistence service convention.

**Tests (`tests/test_watchlist_service.py`, new)**

- 50 service tests using a temporary SQLite engine (`tmp_path`); deterministic,
  no live APIs. Covers CRUD, validation, normalization, duplicate/idempotent
  behavior, cascade-style ticker deletion, and not-found paths.

**Verification:** `pytest tests/test_watchlist_service.py` → 50 passed; full
suite → 1534 passed. No API, frontend, scoring, analysis, report, or CLI
behavior changed.

## 2026-06-10 — Codebase review and documentation sync

**Goal:** full code-quality review (clean/useful/no redundancy) plus a docs accuracy pass. Behavior-preserving only.

- Reviewed the whole tree (`app/`, `frontend/src/`, tests, watchlists, prompts). No layer violations, dead imports, debug prints, or swallowed errors found; architecture and guardrails hold throughout.
- `app/analysis/scoring.py`: removed `_calculate_technical_score`, an exact one-line duplicate of the generic `_signals_to_score`; call site now uses `_signals_to_score` directly.
- `.env.example`: aligned with `app/config.py` — dropped `OPENAI_API_KEY` (contradicts the no-ML/LLM guardrail) and the stale `DATABASE_URL`; added `DATABASE_PATH`; documented the optional provider keys.
- `CLAUDE.md`: added the implemented `app/models/confidence_diagnostics.py` to the module table (was missing).
- Left as findings (intentional, not changed): stale placeholder prompts in `prompts/` for now-implemented modules; unused `MARKET_DATA_API_KEY`/`NEWS_API_KEY` config kept as documented provider scaffolding.
- All 1484 tests pass; `python -m app.main` unaffected.

## 2026-06-02 — Frontend Milestone 1: React + Vite shell with API connectivity

**Goal:** build the first working frontend following `docs/frontend_plan.md`.
No backend analysis, scoring, persistence, or CLI behavior changed.

**Backend change — CORS middleware (`app/api/main.py`)**

Added `CORSMiddleware` to the FastAPI app factory. Allowed origins are limited to
`http://localhost:5173` and `http://127.0.0.1:5173` (Vite dev server defaults).
Allowed methods: GET and POST. Allowed headers: Content-Type. No wildcard origins.

**New frontend app (`frontend/`)**

Scaffolded with `npm create vite@latest -- --template react-ts` (Vite 8, React 19,
TypeScript 6), then replaced all template source files with our own. Added
`react-router-dom` v7 for routing.

Key frontend files created:

- **`frontend/src/types/report.ts`** — `StockReport`, `SavedReportSummary`,
  `SavedReportDetail` TypeScript interfaces mirroring backend Pydantic schemas.
  No analysis or scoring logic.
- **`frontend/src/api/client.ts`** — base fetch wrapper; `ApiError` class with
  status code; handles network errors (backend unreachable) and non-2xx responses
  cleanly. Base URL from `VITE_API_BASE_URL` env var, defaults to `http://127.0.0.1:8000`.
- **`frontend/src/api/analysisApi.ts`** — `checkHealth`, `analyzeOnly`,
  `analyzeAndSave`; one function per backend endpoint.
- **`frontend/src/components/LoadingState.tsx`** — spinner with `role="status"`.
- **`frontend/src/components/ErrorMessage.tsx`** — error display with `role="alert"`.
- **`frontend/src/components/StockReportView.tsx`** — defensive display of all
  StockReport fields; no re-calculation of score, category, or summaries.
- **`frontend/src/pages/DashboardPage.tsx`** — health check on mount, disclaimer,
  link to Analyze page, Milestone 2 note.
- **`frontend/src/pages/AnalyzePage.tsx`** — ticker input, Analyze-only button
  (POST /api/analyze), Analyze-and-save button (POST /api/reports/analyze), loading
  state, error display, StockReportView result.
- **`frontend/src/App.tsx`** — BrowserRouter, sticky header with NavLink navigation,
  route table (`/` → Dashboard, `/analyze` → Analyze).
- **`frontend/src/styles.css`** — plain CSS with custom properties; no framework.
- **`frontend/.env.example`** — `VITE_API_BASE_URL=http://127.0.0.1:8000`.

**Backend tests — CORS (`tests/test_api.py`)**

Added `TestCors` class (3 tests): allowed origin gets the CORS header, preflight
OPTIONS request from the local frontend is accepted, unknown origin is not reflected.

**`docs/frontend_plan.md`** — updated status from "planning only" to "Milestone 1 complete".

**`README.md`** — added "Running the Frontend" section (env setup, dev server, build);
updated Current Status; updated Project Structure to include `frontend/`.

**`CLAUDE.md`** — added frontend entries to Currently Implemented and Architecture
tables; updated Phase 4 status; added frontend data ownership guardrails.

**npm run build:** passes (238 kB JS / 5 kB CSS gzipped, 0 TypeScript errors).
**npm run lint:** clean (0 ESLint warnings or errors).
**pytest:** 1484 passed (was 1481, +3 CORS tests).

---

## 2026-06-01 — Frontend planning document

**Goal:** define the frontend plan for Phase 4 before writing any frontend code, so that
when implementation begins the UI can consume the existing FastAPI backend cleanly.

**`docs/frontend_plan.md`** (new)

Twelve-section planning document covering:

- **Purpose** — why the frontend exists (display, input, navigation); backend stays the
  single source of truth for all analysis, scoring, and persistence.
- **Non-goals** — explicit list of what the frontend must never implement (trading, broker
  APIs, order execution, portfolio management, scoring logic duplication, ML).
- **Stack recommendation** — React + Vite (TypeScript) for Milestone 1; rationale vs.
  Next.js and Streamlit.
- **App structure** — proposed `frontend/src/` layout: `api/`, `components/`, `pages/`,
  `types/`, with purpose of each folder explained.
- **Initial screens** — Dashboard, Analyze Ticker, Report History, Report Detail; API
  calls, required fields, and empty/error states for each.
- **API contract** — all five endpoints documented with method, path, request body,
  response shape, and frontend behavior on success and on each error type.
- **Loading and error states** — table covering backend unavailable, invalid ticker,
  empty history, 404, slow analysis, save failure, and unexpected 500.
- **Data ownership rules** — explicit table stating that backend owns analysis, scoring,
  StockReport generation, and persistence; frontend only renders and submits.
- **Milestone 1 scope** — React + Vite scaffold, API client, Analyze page connected to
  `POST /api/analyze` and `POST /api/reports/analyze`; everything else deferred.
- **Later milestones** — outline for Milestones 2–6 (history/detail, dashboard, charts,
  watchlist UI, mock trading UI) with their backend dependencies noted.
- **Open questions** — CORS config, styling approach, repo layout, env var for API base
  URL, history pagination strategy.
- **Recommended next step** — do not implement immediately; resolve open questions, then
  open a narrow "Milestone 1" implementation task.

**`README.md`** — added React + Vite frontend to Planned Future Work with a pointer to
`docs/frontend_plan.md`.

**`CLAUDE.md`** — updated Phase 4 status row; added a Non-Negotiable Guardrail noting
that frontend code must follow `docs/frontend_plan.md`; added `docs/frontend_plan.md` to
Key Docs.

**No production code changed.** No tests added or removed.

**pytest:** 1481 passed (unchanged).

---

## 2026-06-01 — Review and cleanup pass after Phase 3 Milestone 1

**Goal:** review the SQLite persistence implementation for correctness, maintainability,
and architecture alignment; make only safe, narrow corrections — no new features.

**Issues found and fixed:**

**`app/services/report_persistence_service.py`** — added `_as_utc(value)` helper;
applied in `_summary_from_row` and the `get_saved_report` return dict. SQLite drops
timezone info on storage; without this fix, `list_saved_reports` and `get_saved_report`
returned naive datetimes while `save_stock_report` returned UTC-aware datetimes, making
`created_at` inconsistent across the three endpoints.

**`app/api/errors.py`** (new) — `KNOWN_ANALYSIS_ERRORS` tuple consolidating the seven
pipeline error types mapped to HTTP 422. Both route modules previously defined identical
copies, creating a maintenance hazard.

**`app/api/routes/analysis.py`** and **`app/api/routes/reports.py`** — replaced local
`_KNOWN_ERRORS` tuples and seven individual error imports with a single import of
`KNOWN_ANALYSIS_ERRORS` from `app.api.errors`.

**`app/api/routes/reports.py`** — wrapped `save_stock_report(report)` in its own
`try/except`. Previously a DB write failure would propagate as a raw unhandled exception;
it now returns a clean HTTP 500 with `"Failed to save report"`.

**`tests/test_persistence.py`** — removed a dead `from datetime import timezone as tz`
import inside `test_list_created_at_is_utc`; the `tz` alias was never used in the test
body and was left over from an earlier draft.

**Tests added:**
- `TestCreatedAtTimezone` (5 tests) — verify that datetimes read back from SQLite via
  `list_saved_reports` and `get_saved_report` are UTC-aware, and that `save` and `list`
  agree on the same moment.
- `test_returns_none_for_negative_id` — persistence one-liner.
- `test_save_failure_returns_500`, `test_save_failure_detail_is_clean`,
  `test_save_failure_does_not_expose_internal_error` — cover the new save error-handling path.

**Documentation:** updated `README.md` and `CLAUDE.md` to reflect the persistence layer
(Architecture table, Project Structure, Currently Implemented).

**No changes** to analysis modules, scoring engine, report formatters, CLI behavior, or
the database schema.

**pytest:** 1481 passed (was 1472 after Phase 3 Milestone 1, +9 new tests).

---

## 2026-06-01 — Phase 3 Milestone 1: SQLite persistence for StockReport snapshots

**Goal:** add a SQLite persistence layer so the API can save, list, and retrieve
full StockReport snapshots — without touching the analysis pipeline, scoring,
CLI behavior, or the existing `POST /api/analyze` endpoint (which remains
analysis-only).

**`requirements.txt`** — added `sqlalchemy`.

**`app/config.py`** — added `DATABASE_PATH` (env var override; default
`data/investment_bot.db`).

**`app/data/database.py`** (new)

SQLAlchemy Core engine factory and table definition. `build_engine(db_path)` creates
a SQLite engine, ensures the parent directory exists, and calls `metadata.create_all`
so the schema is always up to date. Accepts `":memory:"` for in-memory testing.
Table: `analysis_reports` — `id` (PK autoincrement), `ticker`, `company_name`
(nullable), `category`, `score`, `confidence`, `report_json` (full JSON text),
`created_at`.  No ORM; all queries are SQLAlchemy Core.

**`app/services/report_persistence_service.py`** (new)

Public persistence boundary with three functions:
- `save_stock_report(report, *, engine=None)` — inserts a row and returns summary + report dict.
- `list_saved_reports(limit=50, *, engine=None)` — returns summary rows ordered by `id DESC` (newest first); excludes the full JSON blob.
- `get_saved_report(report_id, *, engine=None)` — returns one full snapshot (round-tripped via `StockReport.model_validate_json`), or `None`.

Each function accepts an optional keyword-only `engine` for test injection; production
callers omit it and a shared engine is lazily initialised on first call.

**`app/api/schemas/reports.py`** (new)

`SavedReportSummary` (id, ticker, company_name, category, score, confidence, created_at)
and `SavedReportDetail` (extends summary with `report: StockReport`).

**`app/api/routes/reports.py`** (new)

Three thin route handlers; all delegate to the service layer:
- `POST /api/reports/analyze` — calls `analyze_stock`, then `save_stock_report`; returns `SavedReportDetail`.
- `GET  /api/reports/history` — calls `list_saved_reports(limit=limit)`; returns `list[SavedReportSummary]`.
- `GET  /api/reports/{report_id}` — calls `get_saved_report`; returns `SavedReportDetail` or 404.

Known analysis errors map to 422; unexpected errors to 500; save is skipped on any error.

**`app/api/main.py`** — registered the new `reports` router under `/api`.

**`.gitignore`** — added `data/*.db` so the SQLite file is never committed.

**`tests/test_persistence.py`** (new — 56 tests)

All tests use a `tmp_path` SQLite engine; no writes to the real database.
Covers: return types, sequential IDs, field values, company_name=None, created_at
presence, ordering, limit enforcement, report JSON roundtrip, independent retrieval
of two records, and None for missing IDs.

**`tests/test_api_reports.py`** (new — 63 tests)

`analyze_stock` and all three persistence functions are mocked at the route-import
level; no network calls, no real database. Covers: success path, ticker normalization,
invalid input (422), all six known service errors (422 + no-save assertion), unexpected
errors (500 + no-save assertion), history list shape, custom limit, empty history,
full-report retrieval, 404, non-integer id (422), and two assertions that confirm
`POST /api/analyze` never touches the persistence layer.

**No changes** to analysis modules, scoring, report formatters, or CLI behavior.

**pytest:** 1472 passed (was 1354, +118 new tests).

---

## 2026-05-28 — Post-FastAPI code review and documentation cleanup

**Goal:** review and clean up the repo after the FastAPI milestone; no new
product features added.

**`tests/test_api.py`** — removed `test_does_not_call_internal_analyze_ticker`:
it claimed to verify `_analyze_ticker` is not called directly but only asserted
`mock_analyze_stock.assert_called_once()`, which is strictly weaker than the
existing `test_calls_analyze_stock_with_ticker`. 26 API tests remain; all pass.

**`README.md`** — added "Running the API Server" section (uvicorn command,
endpoints table, example curl request); updated Architecture table to include
`app/services/` and `app/api/`; updated Project Structure listing; updated
Current Status paragraph.

**`CLAUDE.md`** — added `uvicorn` server command; added `app/services/` and
`app/api/` entries to "Currently Implemented"; expanded Architecture section
to show full `data → analysis → scoring → reports → services → CLI/API` flow;
added API route and CLI-preservation rules to Layer Rules; fixed stale note
attributing non-fatal news fetch to `main.py` (it is in `_analyze_ticker` in
the service layer); added Phase Status table; added Non-Negotiable Guardrails
section; added `full_stack_product_architecture.md` to Key Docs.

**No code changes to `app/`.** No new dependencies. No scoring or CLI changes.

**pytest:** 1354 passed.

---

## 2026-05-28 — FastAPI backend milestone 1

**Goal:** expose the analysis engine through a minimal FastAPI backend without
touching existing CLI behaviour, service logic, or scoring.

**`requirements.txt`** — added `fastapi`, `uvicorn`, `httpx2`.

**`app/api/__init__.py`** — new package init.

**`app/api/main.py`** — FastAPI app factory (`create_app`) plus module-level
`app` instance for uvicorn. Routers mounted under the `/api` prefix.

**`app/api/routes/health.py`** — `GET /api/health` → `{"status": "ok", "service": "investment-bot-api"}`.

**`app/api/routes/analysis.py`** — `POST /api/analyze` → calls
`analyze_stock(ticker)` from the service layer; never calls `_analyze_ticker`
directly. Known project errors map to HTTP 422; unexpected errors map to HTTP
500. Response model is `StockReport`.

**`app/api/schemas/analysis.py`** — `AnalyzeRequest` Pydantic model: strips
whitespace and uppercases the ticker at the API boundary.

**`tests/test_api.py`** — 27 tests across five groups:
- `GET /api/health` (3 tests)
- Success path: returns 200, calls `analyze_stock`, serializes `StockReport` (7 tests)
- Ticker normalization: lowercase, mixed case, whitespace (4 tests)
- Invalid input → 422: empty ticker, whitespace, missing field, non-string (4 tests)
- Known errors → 422: all six project error types (7 tests)
- Unexpected errors → 500: `RuntimeError`, `ValueError` (2 tests)

**CLI unchanged.** `python -m app.main` still works exactly as before.

Run the API server:
```
uvicorn app.api.main:app --reload
```

---

## 2026-05-28 — Full-stack product architecture plan

**Goal:** establish a clear technical direction for evolving the CLI tool into a
full-stack personal investment research platform.

**`docs/full_stack_product_architecture.md`** — new document covering:

- Product vision (decision-support tool; not a trading system)
- Current architecture baseline and service boundary
- Target stack: FastAPI backend, Next.js + React + TypeScript frontend,
  Tailwind CSS + shadcn/ui, SQLite → PostgreSQL, Recharts/lightweight-charts
- Proposed future repository structure including `app/api/`, `app/db/`,
  `app/ml/` (future), `app/simulation/` (future), and `frontend/`
- Backend API design guidelines and initial routes
- Frontend guidelines and initial screens
- Database/persistence approach (SQLite-first, JSON snapshot for StockReports)
- ML upgrade guidelines (later phase; explainable; must not silently override
  rule-based scoring)
- Mock trading simulation guidelines (later phase; paper-trading only; no broker)
- Safety guardrails (no live trading, no broker API, no route-handler logic,
  no CLI regression)
- Phased implementation roadmap (Phases 1–9)

**Direction change:** a quick single-page dashboard approach (e.g. Streamlit)
was intentionally not adopted. The project moves directly toward a proper
FastAPI + Next.js architecture with a staged rollout.

**Immediate next step:** FastAPI Backend Phase 2 — expose `analyze_stock`
through `POST /api/analyze` and a health endpoint. No frontend, database, ML,
or mock trading yet.

No code or dependencies were added in this entry.

---

## 2026-05-28 — Test boundary cleanup

**Goal:** move service-behavior tests out of `tests/test_main.py` and into
`tests/test_stock_analysis_service.py`, so each file tests only one layer.

**`app/services/stock_analysis_service.py`** (updated)

- Renamed `analyze_ticker` → `_analyze_ticker` to signal it is internal to
  the service. Public callers should use `analyze_stock` (returns `StockReport`)
  or `analyze_watchlist_file`. The function was never part of the documented
  public API for UI callers; the rename makes that explicit.

**`tests/test_stock_analysis_service.py`** (expanded)

- Updated import and all call sites: `analyze_ticker` → `_analyze_ticker`.
- Updated `test_delegates_to_analyze_ticker` patch path to
  `app.services.stock_analysis_service._analyze_ticker`.
- Added 4 tests migrated from `test_main.py:TestAnalyzeTicker`:
  - `test_calls_pipeline_in_order` — asserts full step order
  - `test_passes_none_beta_when_fundamentals_has_no_beta`
  - `test_none_company_name_from_fundamentals_stays_none`
  - `test_news_signals_included_in_score_call`

**`tests/test_main.py`** (simplified)

- Removed `TestAnalyzeTicker` (8 tests) — these were service tests, now owned
  by `test_stock_analysis_service.py` or covered by the 4 migrated tests above.
- Removed `TestNewsFetchInPipeline` (3 tests) — the news-fetch-failure behaviour
  is covered in `test_stock_analysis_service.py`; the one unique assertion was
  migrated.
- Removed all now-unused imports, helpers (`_make_signal`, `_make_rating`,
  `_make_mock_fundamentals`), and patch-target constants (`_SVC`, `_FETCH`,
  `_FETCH_FUND`, etc.).
- Simplified `_mock_pipeline` to patch `app.main.analyze_stock` directly at the
  CLI boundary; added `_make_stock_report` helper.

Net change: −11 tests removed, +4 migrated → 1327 tests total (was 1334).
No CLI behaviour, scoring logic, or report formats changed.

---

## 2026-05-28 — Service boundary cleanup / UI readiness pass

**Goal:** make `app/services/stock_analysis_service.py` the single stable entry
point for both the CLI and any future UI, with no analysis orchestration
remaining in `app/main.py`.

**`app/main.py`** (updated)

- Replaced `analyze_ticker(ticker)` + `build_stock_report(rating)` call chain
  with a single `analyze_stock(ticker)` call. `main()` no longer imports
  `analyze_ticker` or `build_stock_report` directly.
- `--save-json` now exports a `StockReport` model instead of the lower-level
  `Rating` model. `StockReport` is richer (partitioned signal lists, summaries,
  `confidence_level` field) and is the natural object for a UI to consume.
  **Breaking change:** JSON output schema has changed — any script that relied on
  `Rating`-specific fields (`explanation`, `technical_score`, `fundamental_score`,
  `news_score`, `risk_score`, `signals_used`) will need to be updated.

**`tests/test_main.py`** (updated)

- `TestMainErrors`: updated 7 patch targets from `app.main.analyze_ticker` to
  `app.main.analyze_stock` — tests now cover the actual function `main()` calls.
- `test_save_json_receives_rating_and_ticker` renamed and updated to
  `test_save_json_receives_stock_report_and_ticker` checking for `StockReport`.
- `test_save_json_rating_has_score` updated to `test_save_json_stock_report_has_score_and_category`.
- Added `StockReport` import.
- `analyze_ticker` import moved from `app.main` to `app.services.stock_analysis_service`
  (the correct home).

**`tests/test_stock_analysis_service.py`** (expanded)

Added 4 new tests covering previously untested error propagation paths:
- `test_fundamental_analysis_error_propagates` — `FundamentalAnalysisError` raised
  by `build_fundamental_signals` bubbles out of `analyze_ticker`.
- `test_risk_analysis_error_propagates` — `RiskAnalysisError` raised by
  `analyze_risk_conditions` bubbles out of `analyze_ticker`.
- `test_news_analysis_error_propagates` — `NewsAnalysisError` raised by
  `analyze_news` bubbles out of `analyze_ticker`.
- `test_stock_report_is_json_serializable` — `analyze_stock` result can be
  serialized with `model_dump_json()`; confirms the service is UI-ready.

**`docs/ui_readiness_notes.md`** (new)

Created a UI readiness reference document covering: intended CLI → service →
Streamlit → FastAPI path; public service API table; `StockReport` and
`WatchlistResult` field inventories; error handling contract; what NOT to build
yet (trading, broker APIs, ML/LLM, live polling); JSON export format change
note; known future cleanup items.

No scoring logic, weights, thresholds, analysis modules, or report formats
changed. Full suite: all tests pass.

## 2026-05-26 — Service layer added for UI readiness

Added `app/services/stock_analysis_service.py` and `app/services/__init__.py` as a
reusable service layer that sits between the CLI and the analysis pipeline. The
service exposes three public functions:

- `analyze_ticker(ticker) -> Rating` — the full pipeline (moved from `app/main.py`)
- `analyze_stock(ticker) -> StockReport` — pipeline + report assembly; intended for
  UI callers that want a ready-to-render object
- `analyze_watchlist_file(path) -> list[WatchlistResult]` — loads a watchlist file
  and runs the scan; intended for UI callers

`app/main.py` now imports `analyze_ticker` and `analyze_watchlist_file` from the
service; `_run_watchlist` delegates the scan step to `analyze_watchlist_file`. All
existing CLI behavior, output file locations, and JSON export formats are preserved.

Added `tests/test_stock_analysis_service.py` (57 new tests). Updated patch targets
in `tests/test_main.py` and `tests/test_watchlist.py` to reflect the pipeline's new
location in the service module. Full suite: 1330/1330 passing.

## 2026-05-26 — Post-confidence-recalibration validation pass completed

Reran the 14-ticker calibration watchlist and five individual ticker reports
(KO, XOM, MSFT, MCD, PFE) after the confidence threshold change. No code was
changed. All generated output files left uncommitted under `outputs/`.

**Individual ticker results — all expected labels matched:**

| Ticker | Avg Conf | Expected | Actual | Score | Category |
|--------|----------|---------|--------|-------|----------|
| KO | 0.6375 | High | High ✅ | 79.8 | Buy Candidate |
| MSFT | 0.6425 | High | High ✅ | 66.2 | Watchlist |
| XOM | 0.6250 | Medium | Medium ✅ | 59.5 | Watchlist |
| MCD | 0.6175 | Medium | Medium ✅ | 50.1 | Hold |
| PFE | 0.6100 | Medium | Medium ✅ | 65.0 | Watchlist |

**Watchlist distribution:** 6 High (KO, NVDA, MSFT, CAT, TSLA, INTC) /
8 Medium / 0 Low — 43% High, at the upper limit of the risk guardrail stated
in the proposal ("≤ 5–6 of 14"). No immediate threshold adjustment warranted,
but establishes monitoring baseline.

**Notable case:** INTC scored 54.8 (Hold) with High confidence (avg 0.635).
This is semantically correct — confidence reflects data completeness, not
score direction. Confirms the intended decoupling of confidence from category.

**Updated: `docs/calibration_review_notes.md`** — appended Post-Confidence-
Recalibration Validation Pass section.
**Updated: `docs/confidence_calibration_proposal.md`** — added validation status note.

No Python code changed. No scoring, category, signal value, or diagnostics
logic was altered. 1298 tests pass.

---

## 2026-05-26 — Confidence threshold-only recalibration implemented

**Changed: `app/analysis/scoring.py` — `_map_confidence()` only**

Updated the two threshold constants:

| Level | Old Threshold | New Threshold |
|-------|--------------|---------------|
| HIGH | avg ≥ 0.70 | avg ≥ **0.63** |
| MEDIUM | avg ≥ 0.45 | avg ≥ **0.50** |
| LOW | avg < 0.45 | avg < **0.50** |

No other code changed. Scores, categories, composite weights, signal-level
confidence values, and `ConfidenceDiagnostics` calculation are all unchanged.

**Expected label changes for five review tickers (based on measured diagnostics):**
- KO (avg 0.6375): Medium → High
- MSFT (avg 0.6425): Medium → High
- XOM (avg 0.6250): Medium → Medium (unchanged)
- MCD (avg 0.6175): Medium → Medium (unchanged)
- PFE (avg 0.6100): Medium → Medium (unchanged)

**New: 18 tests added to `tests/test_scoring.py`** (`TestConfidenceMappingBoundaries`)

Tests added:
- Exact boundaries at 0.63 (HIGH) and 0.50 (MEDIUM)
- Just-below boundary tests at 0.6299 and 0.4999
- All three labels confirmed reachable
- Representative real-ticker averages: KO/MSFT → HIGH, XOM/MCD/PFE → MEDIUM
- HIGH reachable with realistic 7-signal set (avg ≈ 0.6357)
- Regression: score unchanged, category unchanged, diagnostics unchanged

**Updated: `tests/test_confidence_diagnostics.py`** — updated stale inline comment only.

**Updated docs** (notes only, no rewrites):
- `docs/confidence_calibration_proposal.md` — implementation status note
- `docs/signal_confidence_audit.md` — implementation note
- `docs/confidence_calibration_design.md` — implementation note

1298 tests pass.

---

## 2026-05-26 — Confidence calibration proposal created; no confidence/scoring code changed

**New: `docs/confidence_calibration_proposal.md`**

Created a scoped implementation proposal for the confidence threshold calibration.
No Python code was changed. This is a planning document only.

**Recommended approach:** Option A — threshold-only recalibration.
Change only `_map_confidence()` in `app/analysis/scoring.py`.

Proposed new thresholds (current values in parentheses):
- HIGH: avg ≥ **0.63** (was ≥ 0.70 — currently unreachable)
- MEDIUM: 0.50 ≤ avg < **0.63** (was 0.45 ≤ avg < 0.70 — far too wide)
- LOW: avg < **0.50** (was < 0.45)

Expected before/after for five review tickers:
- KO (avg 0.6375): Medium → **High**
- MSFT (avg 0.6425): Medium → **High**
- XOM (avg 0.6250): Medium → Medium (unchanged — mixed signals)
- MCD (avg 0.6175): Medium → Medium (unchanged — missing D/E, weakest fund avg)
- PFE (avg 0.6100): Medium → Medium (unchanged — most neutral signals)

**Updated: `docs/confidence_calibration_design.md`** — added cross-reference to proposal.
**Updated: `docs/signal_confidence_audit.md`** — added cross-reference to proposal.
**Updated: `docs/calibration_review_notes.md`** — added one-line note that proposal exists.

1280 tests pass. No new tests required (docs-only task).

---

## 2026-05-26 — Confidence diagnostics review pass completed; docs updated

Reran KO, XOM, MSFT, MCD, and PFE with `--save-markdown --save-json` and
extracted actual `ConfidenceDiagnostics` values from JSON output. No Python
code was changed.

**Key findings:**
- All five tickers returned Medium confidence (measured avg: 0.6100–0.6425).
- Average confidence spread across a 29-point score range is only 0.0325.
- Technical avg is structurally uniform (four tickers at exactly 0.6071; PFE 0.5786).
- News avg is always 0.70 (structural cap — all tickers hit 8+ article floor).
- Fundamental avg is the only differentiator: 0.58 (MCD) to 0.67 (MSFT).
- MCD has one missing-data signal (D/E null → confidence 0.30); no other ticker did.
- MSFT measured 0.6425 — the mathematical ceiling from the audit, confirming HIGH (≥0.70) is unreachable.
- Audit's KO estimate (~0.637) matched measured value (0.6375) within 0.0005.

**Updated: `docs/calibration_review_notes.md`**

Appended `## Confidence Diagnostics Review Pass` section with run details,
full diagnostics table, pattern summary, and decision. No code change recommended.

1280 tests pass (pytest; no new tests — no code changes in this task).

---

## 2026-05-26 — Confidence diagnostics added; no confidence formula changes made

**New: `app/models/confidence_diagnostics.py`**

Added `ConfidenceDiagnostics` Pydantic model with fields: `signal_count`,
`average_signal_confidence`, `min_signal_confidence`, `max_signal_confidence`,
`bullish_count`, `bearish_count`, `neutral_count`, `missing_count`,
`technical_average_confidence`, `fundamental_average_confidence`,
`news_average_confidence`, `risk_average_confidence`.

**Updated: `app/analysis/scoring.py`**

Added private `_build_confidence_diagnostics(signals)` helper alongside
`_map_confidence()`. Called in both `score_signals()` and
`score_technical_signals()`. Result attached to `Rating` as
`confidence_diagnostics`. No scoring formula, confidence threshold, or
score_impact values were changed.

**Updated: `app/models/rating.py`**

Added optional `confidence_diagnostics: ConfidenceDiagnostics | None = None`
field. Existing fields and validators unchanged.

**Updated: `app/models/stock_report.py`**

Added optional `confidence_diagnostics: ConfidenceDiagnostics | None = None`
field. Existing fields unchanged.

**Updated: `app/reports/report_generator.py`**

`build_stock_report()` now passes `rating.confidence_diagnostics` through to
`StockReport`. No other changes.

**Updated: `app/reports/templates.py`**

Added `_md_confidence_diagnostics()` builder and included it in
`format_report_markdown()`. Renders a "## Confidence Diagnostics" table showing
signal count, avg confidence, min/max, direction counts, missing count, and
per-area sub-averages. Section is omitted when `confidence_diagnostics is None`.
Plain-text reports unchanged.

**New: `tests/test_confidence_diagnostics.py`**

70 deterministic unit and integration tests covering: empty input, signal count,
average/min/max confidence, direction counts, missing count, per-area averages,
`score_signals` integration, `build_stock_report` pass-through, JSON
serialization (including `save_json_result`), and Markdown template output.
No live API calls.

**Updated: `docs/signal_confidence_audit.md`** and
**`docs/confidence_calibration_design.md`** — short notes that the diagnostic
breakdown is now available.

1280 tests pass.

---

## 2026-05-26 — Signal confidence audit completed; docs/signal_confidence_audit.md created

**`docs/signal_confidence_audit.md`** (new file)

Audited all four analysis modules and the scoring engine to document where signal
confidence values come from and why final confidence is always Medium.

Key findings:
- Every `Signal(confidence=...)` call site was located across `technicals.py`,
  `fundamentals_analysis.py`, `news_analysis.py`, and `risk_analysis.py`.
- The HIGH threshold in `_map_confidence()` is 0.70 (average of all signals).
- The mathematical maximum average confidence for any real ticker with all data
  present and all signals bullish is approximately 0.643 — 0.057 below the HIGH
  threshold. HIGH is unreachable, not just unlikely.
- Five signals structurally depress the average in almost every real run: RSI
  Neutral (0.50), MACD Neutral (0.50), Volume Bullish (0.50), Volume Neutral
  (0.45), and Recent Trend Neutral (0.55).
- Risk signals are asymmetric: worst-case outcomes (high volatility, severe
  drawdown) receive 0.75 confidence, while best-case outcomes (mild drawdown,
  high liquidity) receive 0.60.
- Bullish and bearish versions of most signals share identical confidence values,
  so signal direction balance does not affect the confidence average.
- News confidence caps at 0.70 (8+ articles) — equal to the HIGH threshold —
  so news signals alone cannot push the overall average to HIGH.
- No measure of signal agreement or direction balance is used.

Document includes: complete signal-level inventory table, compression findings,
evidence alignment with calibration runs, specific fix targets, recommended next
step (diagnostic breakdown before formula change), and a six-gate decision gate.

**`docs/confidence_calibration_design.md`** (updated)

Added cross-reference to `docs/signal_confidence_audit.md` in See Also section.

**`docs/scoring_calibration_plan.md`** (updated)

Expanded the "Confidence calibration" bullet in Future Implementation Ideas to
reference the new audit document.

No Python code was changed. No scoring or confidence behavior was modified.
1210 tests pass.

---

## 2026-05-26 — Confidence calibration design document created; docs updated

**`docs/confidence_calibration_design.md`** (new file)

Created a design document for the confidence compression problem identified during
calibration. The document covers:

- Current behavior: `_map_confidence()` in `scoring.py` averages all signal
  confidences and maps to HIGH (≥0.70) / MEDIUM (≥0.45) / LOW (<0.45).
- Evidence: all 19 tickers across three calibration runs returned MEDIUM; zero
  returned HIGH or LOW. KO with 14 bullish / 0 bearish signals estimated at
  avg ~0.57 — still below the 0.70 HIGH threshold.
- Problem statement: MEDIUM band is structurally inevitable because neutral
  signals (news, volume, RSI neutral) pull the average below 0.70 for every
  real ticker. Confidence adds no information to the output.
- Four options: A (lower HIGH threshold), B (raise signal-level confidence
  values), C (distribution-aware formula), D (add explanation text, no code
  change).
- Recommended next step: audit all four analysis modules to inventory current
  per-signal confidence values before choosing an option.
- Decision gate: five conditions that must be met before any code change.

No Python code was changed. No scoring behavior was modified.

**`docs/scoring_calibration_plan.md`** (updated)

Added a note under "Confidence calculation" in "What Can Be Tuned Later" pointing
to the new design document. Added a "Confidence calibration" bullet in "Future
Implementation Ideas" summarizing the gap and referencing the decision gate.

**`docs/calibration_review_notes.md`** (updated)

Added a short cross-reference at the end of the Individual Ticker Review Pass
Decision section linking to `docs/confidence_calibration_design.md`.

---

## 2026-05-26 — Individual ticker calibration review; calibration_review_notes.md updated

**`docs/calibration_review_notes.md`** (extended)

Ran individual ticker reports for the five priority tickers identified in the
second calibration pass: KO, XOM, MSFT, MCD, and PFE. All five commands
succeeded. Commands:

```
python -m app.main KO   --save-markdown --save-json
python -m app.main XOM  --save-markdown --save-json
python -m app.main MSFT --save-markdown --save-json
python -m app.main MCD  --save-markdown --save-json
python -m app.main PFE  --save-markdown --save-json
```

Output files reviewed (not committed):
- `outputs/reports/KO_20260526_195905.md` / `.json`
- `outputs/reports/XOM_20260526_200010.md` / `.json`
- `outputs/reports/MSFT_20260526_200040.md` / `.json`
- `outputs/reports/MCD_20260526_200052.md` / `.json`
- `outputs/reports/PFE_20260526_200113.md` / `.json`

Key findings:
- Company name and current price present in all five reports.
- All five returned Medium confidence — confidence compression persists and
  is now identified as the strongest calibration candidate.
- KO's high score (79.8) is internally consistent: near-perfect technicals
  (97.5) and strong fundamentals (87.5). Not a weighting artifact.
- MCD's Hold (50.8) is entirely driven by its full technical downtrend
  (all three SMAs bearish, technical score 22.5). Fundamentals are solid (82.5).
- MSFT's Watchlist (66.2) despite exceptional fundamentals (95.0) is explained
  by price being below SMA 200 (bearish strong) and MACD bearish.
- XOM's Watchlist (59.5) is driven by weak technicals (47.5). The -43.4%
  EPS decline scoring as neutral (not bearish) is flagged as a weak-evidence
  calibration observation.
- PFE's Watchlist (65.0) is plausible; very low fwd PE (9.1) correctly reads
  as attractive; investigation risk term correctly flagged.
- No scoring code changes were made.

Appended "Individual Ticker Review Pass" section to calibration_review_notes.md
covering: run details, sub-scores table, per-ticker individual review table,
cross-ticker pattern table, confidence pattern analysis, and decision.

---

## 2026-05-26 — Second calibration pass; calibration_review_notes.md updated

**`docs/calibration_review_notes.md`** (extended)

Ran the calibration sample watchlist a second time after the company name and
current price pipeline fix. Command:
`python -m app.main --watchlist watchlists/calibration_sample.txt --save-markdown --save-json`

Output files reviewed:
- `outputs/reports/WATCHLIST_20260526_195322.md`
- `outputs/results/WATCHLIST_20260526_195322.json`

Neither file was committed.

Key findings from the second pass:
- Company names and current prices are now fully populated in both the Markdown
  report and JSON export — the data gap from the first pass is resolved.
- All 14 tickers succeeded with no errors.
- Score range: 50.8–79.8. Category shifts were observed between the first and
  second pass (JNJ, XOM, NVDA dropped from Buy Candidate to Watchlist; WMT rose
  from Hold to Watchlist) — consistent with live intraday data changes, not a bug.
- All-medium confidence across the full set persists and remains a noted pattern.
- Score compression at the upper and lower ends persists.
- No scoring code changes were made.

Appended a "Second Calibration Pass" section to `docs/calibration_review_notes.md`
covering: run details, data completeness check, scoring pattern comparison across
both passes, updated follow-up priorities, and a decision statement.

---

## 2026-05-26 — Code review and cleanup pass; README and CLAUDE.md updates

**`app/analysis/risk_analysis.py`** (minor cleanup)

Removed the redundant `from math import sqrt` import. `math` was already
imported; replaced the single call-site `sqrt(252)` with `math.sqrt(252)`.
No behavior change.

**`app/reports/report_generator.py`** (minor cleanup)

Restored the blank line between `from __future__ import annotations` and the
first import, consistent with all other modules in the codebase.

**`README.md`**, **`CLAUDE.md`**, **`docs/architecture.md`**, **`docs/project_plan.md`**
(documentation updates)

Updated all four documents to reflect the current feature set:
- Added `--save-markdown` to CLI examples and flag tables everywhere it was missing.
- Updated `templates.py` descriptions to reflect its three public formatters
  (`format_plain_text_report`, `format_report_markdown`, `format_watchlist_markdown`).
- Updated `storage.py` descriptions to include `.md` as an output format.
- Removed stale hardcoded test counts (1029, 1103) where they appeared.
- Moved "Richer report formats (Markdown)" from Near-Term future work to
  Completed in `docs/project_plan.md`, where it belongs.
- Added recently completed items to `docs/project_plan.md`: Markdown export flags,
  market data validation improvement, company name/price pipeline flow,
  calibration plan and worksheet, and first calibration review notes.
- Removed Markdown from README Planned Future Work (it is now done).
- Added calibration plan reference to README Planned Future Work.

All 1210 tests pass.

---

## 2026-05-26 — Fix watchlist data completeness gap

**`app/models/rating.py`**, **`app/main.py`**, **`app/reports/report_generator.py`**, **`app/watchlist.py`**

Added `company_name` and `current_price` fields to the `Rating` model (provenance
section). Updated `analyze_ticker` to attach those values to the rating via
`model_copy` after scoring, sourcing `company_name` from `CompanyFundamentals`
and `current_price` from the last close in the OHLCV DataFrame (via `safe_float`).
Updated `build_stock_report` to fall back to `rating.company_name` and
`rating.current_price` when the explicit keyword args are `None`, so both the
watchlist and single-ticker paths receive the values automatically. Extended
`format_watchlist_summary` with COMPANY and PRICE columns so the plain-text
terminal table shows these fields when present and `—` when absent. The Markdown
formatter and JSON serializer already referenced `WatchlistResult.company_name`
and `WatchlistResult.current_price`, so no changes were needed there. No scoring
logic, weights, thresholds, or confidence logic changed. Added 13 deterministic
unit tests covering the new fallback behavior, the column display, and
`analyze_ticker` attachment. All 1210 tests pass.

---

## 2026-05-26 — First calibration review notes

**`docs/calibration_review_notes.md`** (new)

Ran the calibration sample watchlist (`watchlists/calibration_sample.txt`) and
recorded a first manual review snapshot. All 14 tickers succeeded with no
failures. Key observations: company names and current prices are not populated
in watchlist-level output (data gap in the pipeline, no code change made); all
14 tickers received `confidence_level: medium` despite a 27-point score spread
(flagged as a calibration candidate); score range was 50.8–77.5 with no tickers
reaching Strong Buy Candidate or below Hold. Identified five priority tickers for
individual follow-up review (KO, MSFT, PFE, MCD, NVDA). Decision: no scoring code
changes to be made yet.

Generated output files (`outputs/reports/WATCHLIST_20260526_053942.md` and
`outputs/results/WATCHLIST_20260526_053942.json`) were inspected but not committed.

---

## 2026-05-26 — Add sample calibration watchlist

**`watchlists/calibration_sample.txt`** (new)

Added a 14-ticker calibration sample watchlist for use with the scoring
calibration worksheet. Tickers were chosen to cover a range of scoring
conditions: large-cap tech (MSFT, NVDA), high-growth/volatile (AMZN, TSLA),
financial (JPM), healthcare — one stronger, one challenged (JNJ, PFE), consumer
staples/dividend (KO, MCD), retail (WMT), industrial/cyclical (CAT), energy
(XOM), a challenged tech example for lower-score categories (INTC), and a
broad-market ETF reference (SPY). The file contains comment headers explaining
it is a calibration aid only, not a recommendation list.

**`docs/scoring_calibration_worksheet.md`** (minor update)

Added a "Calibration Sample Watchlist" section near the top with the ready-to-run
command and a pointer to the generated output directories.

**`docs/scoring_calibration_plan.md`** (minor update)

Updated step 1 of the Manual Review Workflow to include the sample watchlist
command alongside the single-ticker command.

---

## 2026-05-26 — Add scoring calibration worksheet template

**`docs/scoring_calibration_worksheet.md`** (new)

Added a reusable worksheet template for manually recording observations from
generated stock reports before making any scoring changes. The document includes:
a purpose statement clarifying it is not financial advice, not a backtest, and
does not change scoring behavior; a step-by-step usage workflow with example CLI
commands; a ticker review table with columns for all report fields plus manual
judgment; a pattern-tracking table for finding repeated issues across multiple
tickers with an evidence-strength guide; and decision rules for when and how to
act on findings.

**`docs/scoring_calibration_plan.md`** (minor update)

Updated the "Calibration Worksheet Fields" section to reference the new
worksheet file, and updated the "Future Implementation Ideas" bullet to mark the
worksheet template as complete.

---

## 2026-05-26 — Add scoring calibration plan document

**`docs/scoring_calibration_plan.md`** (new)

Added a planning document that defines how the rule-based scoring system will
be evaluated and tuned over time. No scoring code, weights, or thresholds were
changed. The document covers: current model reference (weights, thresholds,
categories), calibration principles, a candidate evaluation set structure, the
manual review workflow, calibration worksheet fields, a list of tunable and
off-limits levers, future implementation ideas, and a decision gate that must
be cleared before any scoring code changes.

**`docs/project_plan.md`** (minor update)

Added a reference link from the existing "Improved scoring calibration" future
work item to the new `docs/scoring_calibration_plan.md`.

---

## 2026-05-26 — Add real Markdown formatter for watchlist reports

**`app/reports/templates.py`** (extended)

Added `format_watchlist_markdown(results)` — a proper Markdown formatter for
watchlist scan results. Watchlist `--save-markdown` now produces a real Markdown
document instead of saving the plain-text terminal summary with a `.md` extension.

New public function:

- **`format_watchlist_markdown(results)`** — renders a `list[WatchlistResult]` as a
  Markdown document with an H1 title, a generated-at date, a pipe table of successful
  results (Ticker, Company, Category, Score, Confidence, Price), a Failures table when
  errors exist, and the standard disclaimer footer.

New private helpers:

- **`_wl_md_header`** — H1 title, date, and scanned/success/failed counts.
- **`_wl_md_results_table`** — pipe table for successful results; falls back to a
  "*(no results)*" message when the list is empty or all-failures.
- **`_wl_md_failures_table`** — pipe table for failed tickers; omitted when absent.
- **`_md_cell`** — escapes `|` characters that would break table cells.

**`app/main.py`** (updated)

`_run_watchlist` now calls `format_watchlist_markdown(results)` for `--save-markdown`
instead of reusing the plain-text summary string. `--save-report` behavior is unchanged.

**`tests/test_report_templates.py`** (expanded)

Added 40 new deterministic tests covering `format_watchlist_markdown`: return type,
H1 heading, table structure, per-column values, empty-list handling, mixed
success/failure rows, failures-section presence, and the disclaimer footer.

**`tests/test_main.py`** (expanded)

Added 3 new tests to `TestWatchlistSaveMarkdown` verifying that `--save-markdown`
calls the new formatter (not `format_watchlist_summary`), that the saved content
starts with a Markdown heading, and that `--save-report` still receives the plain-text
summary.

---

## 2026-05-26 — Improve market data validation and DataFetchError messages

**`app/data/market_data.py`** (refactored)

Expanded the validation pipeline so invalid, empty, stale, malformed, or
incomplete yfinance responses produce specific `DataFetchError` messages.
No changes to scoring, analysis logic, or report formatting.

New private helpers added:

- **`_validate_price_history(df, symbol)`** — orchestrates all post-fetch checks.
- **`_validate_required_columns(df, symbol)`** — raises if any OHLCV column is
  absent; error message now also lists which columns *were* present to aid diagnosis.
- **`_validate_column_nullability(df, symbol)`** — raises if any individual required
  column is entirely null, naming the specific column. Previously only caught the
  case where *all* columns were null and the row-drop step removed everything.
- **`_validate_numeric_columns(df, symbol)`** — raises if any required column has a
  non-numeric dtype (e.g. strings returned for a price column), naming the column
  and its dtype.

Other improvements:

- Added `isinstance(raw, pd.DataFrame)` guard before `.empty` — catches unexpected
  return types (dicts, `None`, etc.) with a clear message naming the actual type.
- yfinance exception message now includes `period` and `interval` in addition to
  the ticker, making it easier to reproduce a failed fetch.
- Empty-DataFrame error message also now includes `period` and `interval`.
- `REQUIRED_COLUMNS` promoted to `frozenset` (immutable constant).
- Added `# TODO` comment for staleness detection (deferred — requires careful
  handling of weekends/holidays and test fixture dates without an exchange-calendar
  dependency).

**`tests/test_market_data.py`** (expanded)

- Added `_make_normalized_ohlcv()` fixture for unit-testing private helpers directly.
- Added `TestNormalizeColumns`, `TestValidateRequiredColumns`,
  `TestValidateColumnNullability`, `TestValidateNumericColumns`,
  `TestValidatePriceHistory` — 29 new tests covering helpers in isolation.
- Extended `TestDataValidation` and `TestYfinanceErrors` — 16 new integration tests
  covering non-DataFrame returns, per-column nullability, non-numeric columns,
  period/interval in error messages, and exception chaining.
- Updated one existing assertion: `test_all_nan_rows_dropped_and_raises_if_empty`
  match string updated to reflect that all-null columns are now caught earlier
  (at `_validate_column_nullability`) with a more specific message.
- Total: 64 tests in the market data file (was 10).

No scoring weights, thresholds, or report formats changed. No new dependencies added.
Full suite 1155/1155 passing.

## 2026-05-26 — Add Markdown report export (`--save-markdown`)

**`app/reports/templates.py`** (updated)

- Added `format_report_markdown(report: StockReport) -> str` — produces a clean
  Markdown document from an existing `StockReport` with H1 title, summary metadata,
  Recommendation table, per-category analysis sections, Key Strengths/Risks bullet
  lists, Triggers, Metadata, and a disclaimer footer.
- No new analysis or scoring logic; formatter consumes already-computed `StockReport`.

**`app/data/storage.py`** (updated)

- Added `"md"` to `_SUPPORTED_EXTENSIONS` so `build_report_filename` accepts `.md`.
- Added `save_markdown_report(report_text, ticker, output_dir, timestamp) -> Path`
  following the same pattern as `save_text_report`. Saves to `outputs/reports/` with
  a `.md` extension.

**`app/main.py`** (updated)

- Added `--save-markdown` argparse flag.
- Single-ticker mode: calls `format_report_markdown(stock_report)` and
  `save_markdown_report(md_text, ticker)` when the flag is set.
- Watchlist mode: saves the plain-text watchlist summary as a `.md` file via
  `save_markdown_report(summary, "WATCHLIST")` when the flag is set.
- StorageError is non-fatal in both modes (warns to stderr, returns 0).

**`tests/test_report_templates.py`** (updated)

- Added `TestMarkdownReturnType`, `TestMarkdownHeader`, `TestMarkdownRecommendation`,
  `TestMarkdownAnalysisSummaries`, `TestMarkdownKeyStrengths`, `TestMarkdownKeyRisks`,
  `TestMarkdownTriggers`, `TestMarkdownMetadata`, `TestMarkdownDisclaimer` — 44 new tests.

**`tests/test_main.py`** (updated)

- Added `TestSaveMarkdownFlag` (13 tests), `TestArgParserMarkdown` (5 tests),
  `TestWatchlistSaveMarkdown` (5 tests) — 23 new tests.

No scoring weights or thresholds changed. No new dependencies added. No existing
entries modified. Full suite passing.

## 2026-05-25 — Update architecture.md and project_plan.md to match current codebase

**`docs/architecture.md`** (rewritten)

- Replaced stale layer map (most modules marked ○/planned) with accurate map showing all implemented modules
- Added `app/models/fundamentals.py`, `app/models/news.py`, `app/watchlist.py` which were missing
- Corrected storage description: outputs go to `outputs/reports/` and `outputs/results/`, not `data/raw/`
- Corrected report generator description: it builds a StockReport from a Rating (does not receive one)
- Removed the "Future Trading Layer" section — no trading layer is planned for this project
- Added data flow diagram, watchlist flow, CLI flag table, and testing approach section
- Removed all ○ stub markers; every listed module is implemented

**`docs/project_plan.md`** (rewritten)

- Replaced the original Version 1 plan (partially done) with a clean completed/future split
- Marked as completed: all foundation, data, analysis, reports, CLI/export, and maintenance work
- Removed v1.1/v1.2/v2.0/v2.1/v3.0/v3.1/v4.0 version table — all phases through v2.x are done
- Removed v4.0 "Live trading" row; replaced with explicit "Out of Scope" section
- Updated CLI example from `python app/main.py --ticker AAPL` to `python -m app.main AAPL`
- Future work section now covers only genuinely unimplemented items

No application logic changed. No trading functionality added. Full suite 1029/1029 passing.

## 2026-05-25 — Consolidate report formatters; remove legacy stock_report.py

**`app/reports/stock_report.py`** (removed)

- Deleted the older `generate_stock_report(ticker, rating, signals, ...)` formatter
- It had no production callers — `app/main.py` already used `build_stock_report` + `generate_plain_text_report` exclusively
- `app/reports/templates.py` is now the single canonical plain-text report implementation

**`tests/test_stock_report.py`** (removed)

- Deleted the 74-test suite that tested the legacy formatter only
- All meaningful coverage already existed in `test_report_templates.py` (header, recommendation, analysis summaries, signals ordering, key strengths/risks, triggers, disclaimer)
- Ticker validation is covered by `test_stock_report_model.py` at the Pydantic model level
- Tests for `_score_breakdown` and `rating.explanation` were specific to the legacy formatter's output; neither feature exists in `templates.py`

**`CLAUDE.md`** (updated)

- Removed `app/reports/stock_report.py` row from the "Currently Implemented" table

**`README.md`** (updated)

- Removed `stock_report.py` from the project structure block
- Updated test count from 1103 to 1029

No trading functionality added. Full suite 1029/1029 passing.

## 2026-05-25 — Code review, cleanup, and documentation update

**`app/utils/logging.py`** (removed)

- Removed empty docstring-only stub; nothing imported it and it contained no implementation

**`app/config.py`** (updated)

- Removed `OPENAI_API_KEY` and `DATABASE_URL` entries; both are aspirational for features that don't exist (no LLM, no database) and nothing imported config at all
- Retained `MARKET_DATA_API_KEY`, `NEWS_API_KEY`, `ENVIRONMENT`, and `DEBUG` as legitimate placeholders

**`CLAUDE.md`** (rewritten)

- Updated "Currently Implemented" table to include all implemented modules: `app/models/stock_report.py`, `app/reports/report_generator.py`, `app/reports/templates.py`, `app/reports/stock_report.py`, `app/watchlist.py`
- Removed "Not Yet Implemented" section (all three listed stubs are now implemented)
- Added all watchlist CLI commands and `--help`
- Added argparse note to `app/main.py` entry
- Added watchlist and argparse to development standards
- Added ML/LLM to the "Do not implement" list

**`README.md`** (rewritten)

- Added full feature list (all four signal categories, StockReport model, JSON export, watchlist scanning, watchlist export, argparse CLI)
- Added complete watchlist CLI usage section
- Added watchlist file format documentation
- Updated "What Is Not Included" section — removed "Watchlist scanning (planned, not yet built)" since it is now built; kept backtesting as future
- Updated test count from 812 to 1103
- Updated project structure to show all implemented files (no more stub labels)
- Added `outputs/` directory to structure
- Updated "Planned Future Work" section to accurately describe remaining roadmap items

No trading functionality added. Full suite 1103/1103 passing.

## 2026-05-25 — Refactor CLI to use argparse

**`app/main.py`** (updated)

- Replaced manual argument parsing with `argparse`; no product behavior changed
- Added `build_parser() -> argparse.ArgumentParser` — single source of truth for all flags and help text
- Added `parse_args(argv) -> argparse.Namespace` — thin public wrapper around `build_parser().parse_args(argv)`
- `main()` now calls `parser.parse_args(argv)` inside a `try/except SystemExit` so parse errors return 1 and `--help` returns 0 without propagating `SystemExit` to callers
- Mutual exclusion (ticker + `--watchlist` together) is validated after parsing; same "not both" error message preserved
- "No args" case validated after parsing; prints argparse-style usage to stderr and returns 1
- Removed manual `_USAGE` string constant
- All single-ticker and watchlist flags (`--save-report`, `--save-json`, `--watchlist`) preserved with identical behavior

**Tests updated**

- `tests/test_main.py`: Updated `test_no_ticker_prints_usage` to match argparse's lowercase `"usage:"` output (previously checked `"Usage"`)
- `tests/test_watchlist.py`: Updated `test_watchlist_flag_missing_path_returns_1` to check for `"--watchlist"` in stderr (argparse says `"argument --watchlist: expected one argument"`; previously checked `"requires a file path"`); updated `test_no_args_still_prints_usage` to lowercase `"usage"`

**Tests added**

- `tests/test_main.py` — `TestArgParser` (15 tests): unit tests for `parse_args()` covering single ticker, save flags, watchlist path, combined flags, no-args defaults, unknown flag raises SystemExit, `--help` raises SystemExit 0, flag order independence, and `build_parser()` return type
- `tests/test_main.py` — `TestMainBehaviorValidation` (11 tests): behavior tests for unknown flag returns 1 with "unrecognized" in stderr, `--help` returns 0 with expected text, ticker + watchlist mutual exclusion, no-args returns 1 with usage in stderr

**Intentional CLI behavior change**

Usage/error lines now use argparse's lowercase `"usage:"` prefix instead of the previous custom `"Usage:"`. All exit codes and error semantics are identical.

No trading functionality added. Full suite 1103/1103 passing (previously 1077, +26 tests).

## 2026-05-25 — Add watchlist save/export support

**`app/watchlist.py`** (updated)

- Added `serialize_watchlist_results(results) -> list[dict]` — converts `WatchlistResult` entries to JSON-serializable plain dicts; enum fields (`final_category`, `confidence_level`) serialized to their string values; `None` preserved as `null`; list order preserved for deterministic JSON output

**`app/main.py`** (updated)

- `_run_watchlist` accepts `do_save_report: bool` and `do_save_json: bool` parameters
- `--save-report`: saves the plain-text watchlist summary via `save_text_report(summary, "WATCHLIST")`; prints confirmation path; non-fatal on `StorageError`
- `--save-json`: saves `{"results": [...]}` dict via `save_json_result(data, "WATCHLIST")`; prints confirmation path; non-fatal on `StorageError`
- Both flags extracted before watchlist dispatch so they apply to both watchlist and single-ticker modes
- `_USAGE` updated to document all four flag combinations
- Single-ticker `--save-report`/`--save-json` behavior unchanged

**Tests added**

- `tests/test_watchlist.py` — 47 new tests across 5 new test classes: `TestWatchlistSaveReport` (8), `TestWatchlistSaveJson` (9), `TestWatchlistBothSaveFlags` (4), `TestSerializeWatchlistResults` (20), `TestSingleTickerSaveUnchanged` (3); also updated 4 existing flag-passing assertions to match new `_run_watchlist` signature (3 bool params)

No trading functionality added. Full suite 1077/1077 passing (previously 1030, +47 tests).

## 2026-05-25 — Add basic watchlist scanning

**`app/watchlist.py`** (new)

- `WatchlistLoadError` — raised for missing or empty watchlist files
- `WatchlistResult` dataclass — ticker, company_name, final_category, score, confidence_level, current_price, error_message; `succeeded` property distinguishes success from failure
- `load_watchlist(path)` — reads a plain-text file; strips whitespace; ignores blank lines and lines starting with `#`; normalizes tickers to uppercase; removes duplicates preserving first-seen order; raises `WatchlistLoadError` for missing files or no valid tickers
- `scan_watchlist(tickers, analyze_func)` — calls `analyze_func` for each ticker; captures failures as `WatchlistResult` entries with `error_message` set so one bad ticker never aborts the scan; returns successful results sorted by score descending followed by failures in encounter order; `analyze_func` is injectable so tests can avoid live API calls
- `format_watchlist_summary(results)` — renders an aligned plain-text table with TICKER / CATEGORY / SCORE / CONFIDENCE columns, error rows for failed tickers, and a footer with scanned/success/failed counts

**`watchlists/default.txt`** (new)

- Sample watchlist: AAPL, MSFT, NVDA, GOOGL, AMZN

**`app/main.py`** (updated)

- Added `--watchlist <file>` CLI flag; dispatches to `_run_watchlist` helper which loads the file, runs `scan_watchlist` via the existing `analyze_ticker` → `build_stock_report` pipeline, and prints the summary
- Single-ticker path and `--save-report`/`--save-json` flags unchanged
- Providing both a ticker and `--watchlist` prints an error and returns 1

**Tests added**

- `tests/test_watchlist.py` — 62 tests covering: file loading (normal, blank lines, comments, lowercase, dedup, whitespace, missing file, empty file); scan success, partial failure, all-failure, and ordering; format output (headers, counts, columns, error rows, order preservation); CLI integration (watchlist flag dispatch, missing path, ticker+watchlist conflict, partial failure returns 0, existing single-ticker path unaffected)

No trading functionality added. Full suite 1030/1030 passing (previously 968, +62 tests).

## 2026-05-25 — Implement structured report layer (StockReport model, templates, report generator)

**`app/models/stock_report.py`**

- Implemented `StockReport` Pydantic model: the top-level structured output of a full analysis run
- Fields: ticker (normalized, non-empty), company_name, current_price, final_category, score (0–100), confidence_level, per-category summaries, key_positive_factors, key_risks, buy_trigger, sell_or_avoid_trigger, data_timestamp, data_sources_used, and four per-category signal lists (technical_signals, fundamental_signals, news_signals, risk_signals)
- Reuses `RatingCategory`, `ConfidenceLevel`, and `Signal` from existing models; no concepts duplicated

**`app/reports/templates.py`**

- Implemented `format_plain_text_report(report: StockReport) -> str` — terminal-readable plain-text formatter
- Section structure matches existing CLI output style: header, recommendation, analysis summaries, signals (sorted Technical → Fundamental → News → Risk), key strengths, key risks, triggers, disclaimer
- Header now includes an "As of:" line from data_timestamp when present

**`app/reports/report_generator.py`**

- Implemented `build_stock_report(rating, company_name, current_price) -> StockReport` — assembles StockReport from a completed Rating; partitions `signals_used` into per-category lists; does not fetch data or perform analysis
- Implemented `generate_plain_text_report(report: StockReport) -> str` — delegates to `format_plain_text_report`

**`app/main.py`**

- Replaced `generate_stock_report` import and call with `build_stock_report` + `generate_plain_text_report`; no other changes; CLI flags and error handling unchanged

**Tests added**

- `tests/test_stock_report_model.py` — 42 tests: creation, ticker normalization, score/field validation, defaults, optional fields, immutability
- `tests/test_report_templates.py` — 52 tests: all report sections, signal ordering, count labels, trigger/risk/strength display, empty-state fallbacks
- `tests/test_report_generator.py` — 31 tests: field mapping from Rating, signal partitioning, optional parameters, generate_plain_text_report delegation

No trading functionality added. Full suite 968/968 passing (previously 842, +126 tests).

## 2026-05-24 — Remove dead format_rating_output() helper

- Confirmed via full-repo search: `format_rating_output()` was defined in `app/main.py` and tested in `tests/test_main.py` but never called by the production pipeline (which uses `generate_stock_report()`)
- Deleted `format_rating_output()` and its `# Formatting` section from `app/main.py`
- Removed `TestFormatRatingOutput` class (14 tests) from `tests/test_main.py`; removed `format_rating_output` from the import line
- No production behavior changed; `Rating` import retained (still used by `analyze_ticker` return annotation)
- Full suite 828/828 passing (−14 dead-code tests)

## 2026-05-24 — Consolidate shared helpers into app/utils/helpers.py

- Implemented `safe_float(value) -> float | None` and `normalize_ticker(ticker) -> str` in `app/utils/helpers.py`
- Removed `_safe_float` from `app/analysis/technicals.py`, `app/analysis/risk_analysis.py`, and `app/data/fundamentals.py`; all three copies were identical in behavior
- Removed `_validate_ticker` from `app/data/market_data.py`, `app/data/fundamentals.py`, `app/data/news_data.py`, and `app/data/storage.py`; all four copies were identical in behavior (storage.py used lowercase "ticker" in messages but module-boundary error types are unchanged)
- Each module now imports from `app.utils.helpers`; module-specific exception types (`DataFetchError`, `FundamentalDataFetchError`, `NewsFetchError`, `StorageError`) are preserved at public module boundaries via `try: normalize_ticker(ticker); except ValueError: raise ModuleError(...) from exc`
- Removed `import math` from `app/analysis/technicals.py` and `app/data/fundamentals.py` (only used by the removed helpers); kept in `app/analysis/risk_analysis.py` (`_validate_beta` uses `math.isfinite`)
- Added 29 tests in `tests/test_helpers.py` covering both helpers
- Full suite 842/842 passing

## 2026-05-24 — Codebase audit and cleanup

**`app/main.py`**

- Added `NewsAnalysisError` import and catch clause in `main()` — the error was reachable via `analyze_news()` but silently missing from the handler chain; now exits with `return 1` and a message to stderr like all other analysis errors

**`README.md`**

- Corrected test count (512 → 812), scoring table (News was listed as "reserved", now shown as 25% active), module table (added `news_data.py`, `news_analysis.py`, `models/news.py`, `storage.py`), CLI examples (`--save-report`, `--save-json`), project structure section; removed stale "Future Versions" mention of news analysis; added "What Is Not Included" section

**`tests/test_main.py`**

- Added `test_news_analysis_error_returns_1` to `TestMainErrors` — verifies `NewsAnalysisError` from `analyze_news` surfaces as exit code 1 with "news analysis" in stderr

**Refactor candidates (not changed — beyond audit scope)**

- `_safe_float` duplicated verbatim in `technicals.py`, `fundamentals_analysis.py`, `risk_analysis.py`, and `market_data.py` — move to `app/utils/helpers.py`
- `_validate_ticker` duplicated in `market_data.py`, `fundamentals.py`, `news_data.py`, `storage.py` — move to `app/utils/helpers.py`
- `format_rating_output()` in `main.py` — dead code; never called in the production pipeline (pipeline uses `generate_stock_report()`); 6 tests cover it, so it remains until those tests are removed
- `app/config.py` — defines `MARKET_DATA_API_KEY`, `NEWS_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`; no module imports it; fields are unused placeholders
- `app/utils/helpers.py`, `app/utils/logging.py`, `app/models/stock_report.py`, `app/reports/report_generator.py`, `app/reports/templates.py` — docstring-only stubs; no production code depends on them

**Full suite 813/813 passing**

## 2026-05-24 — Report quality polish

**`app/analysis/scoring.py`**

- `_build_buy_trigger` and `_build_sell_avoid_trigger` now accept sub-scores and the active-category set; language no longer hardcodes "technical score" — triggers describe the weakest active category by name and reference the composite score
- `_build_positive_factors` now sorts by signal strength (STRONG → MODERATE → WEAK) so the highest-conviction factors appear first in the report
- `_build_risk_factors` now also includes cautionary neutral signals — those with `direction=NEUTRAL` and a description matching any keyword in `_CAUTION_KEYWORDS` (e.g. "elevated", "overbought", "warning"); capped at 10 items; bearish signals (score_impact < 0) are not double-counted
- `news_summary` now characterises sentiment qualitatively: "positive" (≥65), "moderately positive" (≥55), "mixed or neutral" (≥45), "cautionary" (≥35), "negative" (<35)
- Fixed stale docstring on `score_signals()` (previously said "NEWS signals are silently ignored")
- Added `_STRENGTH_ORDER`, `_CATEGORY_LABELS`, `_CAUTION_KEYWORDS`, `_weak_category_labels` helpers

**`app/reports/stock_report.py`**

- `_signals_section` now sorts signals by category before rendering: Technical → Fundamental → News → Risk; stable sort preserves within-category order; original list is not mutated

**Tests**

- `test_composite_scoring.py`: added `TestTriggers` (7 tests), `TestPositiveFactorsOrdering` (3 tests), `TestCautionaryNeutralRisks` (5 tests), `TestNewsSummaryQuality` (6 tests); added `RatingCategory` to imports
- `test_stock_report.py`: added `TestSignalsOrdering` (7 tests); added `_CATEGORY_ORDER` to imports
- Full suite 812/812 passing

## 2026-05-24 — CLI save flags

- Added `--save-report` and `--save-json` optional flags to `app/main.py`
- Default behavior unchanged: `python -m app.main AAPL` prints to terminal only, no files written
- `--save-report`: calls `save_text_report(report, ticker)` after printing; prints confirmation with saved path; `StorageError` handled gracefully (warning to stderr, exit 0)
- `--save-json`: calls `save_json_result(rating, ticker)` after printing; passes the `Rating` Pydantic model directly so all fields (ticker, score, category, confidence, sub-scores, signals) are serialised; prints confirmation with saved path; same graceful error handling
- Both flags can be combined: `python -m app.main AAPL --save-report --save-json`
- Updated module docstring with new usage examples
- Added 20 tests in `TestSaveFlags` class within `tests/test_main.py`; all mock storage functions — no real file writes
- Full suite 784/784 passing

## 2026-05-24 — Local storage layer

- Replaced docstring-only stub with full implementation of `app/data/storage.py`
- `StorageError` — single exception class for all storage failures
- `build_report_filename(ticker, timestamp=None, extension="txt") -> str` — deterministic `TICKER_YYYYMMDD_HHMMSS.ext` filenames; validates ticker and extension; supports `"txt"`, `".txt"`, `"json"`, `".json"`
- `ensure_output_dir(output_dir) -> Path` — creates directory tree with `parents=True, exist_ok=True`; wraps `OSError` in `StorageError`
- `save_text_report(report_text, ticker, output_dir="outputs/reports", timestamp=None) -> Path` — validates non-blank text, calls `ensure_output_dir`, writes UTF-8
- `save_json_result(result, ticker, output_dir="outputs/results", timestamp=None) -> Path` — accepts plain `Mapping` or Pydantic `BaseModel`; uses `model_dump(mode="json")` for models; `json.dumps` with `indent=2, sort_keys=True`; `_json_default` fallback handles `datetime` objects
- Added 77 tests in `tests/test_storage.py`; all use `tmp_path` — no writes to real project directories
- Not wired into CLI yet; that is the recommended next step

## 2026-05-24 — Wire news analysis into pipeline

- Updated `_WEIGHTS` in `scoring.py`: Technical 35%, Fundamental 25%, **News 25%**, Risk 15% (sum 1.00; re-normalised when a category is absent)
- `score_signals()` now handles `SignalCategory.NEWS`: computes `news_score`, populates `news_summary`, includes news signal count in `explanation`, passes `news_score` and `news_summary` to `Rating`
- Error message updated: "Expected at least one TECHNICAL, FUNDAMENTAL, NEWS, or RISK signal."
- `main.py`: added `get_recent_news` and `analyze_news` imports; `analyze_ticker()` now fetches news (non-fatal — falls back to `analyze_news([])` on any exception), calls `analyze_news(news_items)`, and includes `news_signals` in the `score_signals()` call
- `tests/test_composite_scoring.py`: renamed `test_only_news_signals_raises` → `test_only_news_signals_does_not_raise`; replaced `TestUnsupportedCategoriesIgnored` with `TestNewsSignals` (10 tests); added `test_news_only_weight_is_100pct` to `TestRenormalisation`; added `TestFourWayWeighting` (4 tests)
- `tests/test_main.py`: added `_FETCH_NEWS` and `_ANALYZE_NEWS` patch targets; updated `_mock_pipeline`; updated `test_calls_pipeline_in_order` with new step order; added news patches to two individual beta tests; added `TestNewsFetchInPipeline` (3 tests)
- No changes to `app/models/rating.py` or `app/reports/stock_report.py` — both already handled `news_score` and `news_summary`
- Full suite 687/687 passing

## 2026-05-24 — News analysis and data layers

- Implemented `app/models/news.py` with `NewsItem` Pydantic model; required `title` (validated non-blank), optional `publisher`, `link`, `published_at`, `summary`, `related_tickers: list[str]`
- Implemented `app/data/news_data.py` with `get_recent_news(ticker, limit=10) -> list[NewsItem]` and `NewsFetchError`; handles both flat and nested-content yfinance response shapes; converts Unix timestamps to timezone-aware UTC datetimes; limit validated to reject bool, float, and zero/negative integers
- Implemented `app/analysis/news_analysis.py` with `analyze_news(news_items) -> list[Signal]` and `NewsAnalysisError`; always returns exactly 3 `SignalCategory.NEWS` signals (Sentiment, Risk Headlines, Coverage); rule-based keyword matching using frozensets; empty input produces 3 neutral no-data signals (confidence=0.30); score impacts capped at ±0.20; coverage signal always score_impact=0.0
- Added 63 tests in `tests/test_news_data.py` and 95 tests in `tests/test_news_analysis.py`; all mocked — no live API calls

## 2026-05-23 — Architecture review and cleanup

Code-quality review after integrating three analysis branches. No behavior changes.

- **`app/analysis/technicals.py`**: renamed private `_maybe_float` → `_safe_float` for
  consistency with `risk_analysis.py` and `fundamentals.py`; replaced `f != f` NaN-only
  check with `math.isfinite()` which also filters Inf; added `import math`
- **`app/analysis/scoring.py`**: updated `score_signals` docstring (weight values were
  still 60/40 from before risk was wired in); updated `score_technical_signals` docstring
  and `explanation` string (both said "not implemented yet" when they are now implemented)
- **`app/reports/stock_report.py`**: removed spurious double blank line left by linter
- No structural changes, no new abstractions, no new dependencies

Issues noted but intentionally left alone:
- `_validate_ticker` is duplicated between `market_data.py` and `fundamentals.py` — they
  raise different exceptions by design; extracting to shared utils would create
  cross-layer coupling for trivial gain
- `_safe_float` is duplicated between `risk_analysis.py` and `fundamentals.py` — same
  reason; private helpers in independent modules
- `_score_breakdown` shows "(not scored)" for any sub-score of 0.0 — borderline issue
  only for the rare case where a scored category lands exactly at 0.0; acceptable now
- `format_rating_output` in `main.py` is not on the live code path but is intentionally
  retained and tested as an alternate/simpler formatter

## 2026-05-23 — Wire risk analysis into pipeline

- Updated `_WEIGHTS` in `scoring.py`: Technical 35%, Fundamental 25%, Risk 15% (total 0.75, re-normalised when a category is absent)
- `score_signals()` now handles `SignalCategory.RISK`: computes `risk_score`, populates `risk_summary`, includes risk signal count in `explanation`, passes `risk_score` and `risk_summary` to `Rating`
- Error message updated: "Expected at least one TECHNICAL, FUNDAMENTAL, or RISK signal."
- `stock_report.py`: RISK CONDITIONS section always rendered; fallback text "Risk conditions were not assessed for this report." shown when `risk_summary` is None
- `main.py`: full pipeline wired — fetches fundamentals, builds all three signal sets, scores with `score_signals()`; handles `FundamentalDataFetchError`, `FundamentalAnalysisError`, and `RiskAnalysisError` in `main()`
- Updated `tests/test_composite_scoring.py`: fixed 7 tests that assumed old 60/40 weights; added `TestRiskSignals` (7 tests) and `TestThreeWayWeighting` (4 tests); renamed two `TestNoSupportedCategories` tests that no longer raise
- Updated `tests/test_main.py`: rewrote mock targets for new pipeline; added tests for `FundamentalDataFetchError`, `FundamentalAnalysisError`, `RiskAnalysisError`; added `test_passes_beta_from_fundamentals_to_risk` and `test_passes_none_beta_when_fundamentals_has_no_beta`
- Added 3 tests to `tests/test_stock_report.py` for the RISK CONDITIONS section
- Full suite 515/515 passing

## 2026-05-23 — Risk analysis module

- Implemented `app/analysis/risk_analysis.py` with `analyze_risk_conditions()` and `RiskAnalysisError`
- Produces 4 signals (or 5 when `beta` is provided), all using `SignalCategory.RISK`
- **Volatility Risk**: annualized std of daily returns; bearish >= 45%, bullish < 25%
- **Maximum Drawdown Risk**: peak-to-trough decline; bearish <= -35%, neutral -35% to -15%, bullish > -15%
- **Recent Trend Risk**: 30-trading-day price return; bearish <= -10%, bullish >= 5%; neutral signal with low confidence when fewer than 31 rows are available
- **Liquidity Risk**: average daily volume; bearish < 500k, neutral 500k–1M, bullish >= 1M; graceful neutral when volume is all NaN
- **Beta Risk** (optional): bearish >= 1.5, neutral 0.8–1.5, bullish < 0.8; raises `RiskAnalysisError` for NaN/Inf beta
- Input validation follows the same pattern as `technicals.py` and `fundamentals_analysis.py`
- `_insufficient_data_signal()` helper consolidates the neutral/low-confidence pattern for missing data
- `_safe_float()` converts NaN/Inf safely to None for all calculations
- Input DataFrame is never mutated (`.dropna()` returns a new Series)
- Added 72 unit tests in `tests/test_risk_analysis.py`; full suite 496/496 passing
- Not yet wired into `scoring.py`, `main.py`, or `stock_report.py`

## 2026-05-23 — Plain-text stock report generator

- Added `app/reports/stock_report.py` with `generate_stock_report()` and `StockReportError`
- Report is a single formatted string with eight sections: header, recommendation, score
  breakdown, analysis summaries (technical/fundamental/news/risk when present), signals
  table, key strengths, key risks, triggers, and disclaimer
- Each signal rendered with a direction indicator (`[+]`/`[-]`/`[ ]`), direction, strength, name, and description
- Optional params: `company_name`, `current_price`, `data_sources` (falls back to `rating.data_sources_used`)
- Input validated with `StockReportError` for bad ticker, non-Rating, or non-Signal items
- `app/main.py` updated to call `generate_stock_report` instead of the old `format_rating_output`
- `format_rating_output` retained in `main.py` (tested independently in `test_main.py`)
- Added 67 unit tests in `tests/test_stock_report.py`; full suite 427/427 passing

## 2026-05-19 — Composite scoring

- Added `score_signals()` to `app/analysis/scoring.py` alongside existing `score_technical_signals()`
- Weights: Technical 60%, Fundamental 40%; re-normalised to 100% when a category is absent
- Unsupported categories (NEWS, RISK) are silently ignored; raises `ScoringError` only if no supported categories are present at all
- Added `_WEIGHTS` constant, `_signals_to_score()` shared formula helper, and `_validate_composite_inputs()`
- `score_technical_signals()` unchanged; its internal validator refactored to be standalone
- `fundamental_summary` populated when fundamental signals are present; `technical_summary` likewise
- Added 58 unit tests in `tests/test_composite_scoring.py`; full suite 360/360 passing

## 2026-05-17 — Fundamentals analysis layer

- Implemented `app/analysis/fundamentals_analysis.py` with `build_fundamental_signals()` and `FundamentalAnalysisError`
- Produces 5 typed FUNDAMENTAL Signals: Valuation, Profitability, Growth, Debt Levels, Free Cash Flow
- Valuation: uses forward P/E (preferred) or trailing P/E; thresholds at 0/5/25/40; BEARISH for negative or >40 PE
- Profitability: profit_margin thresholds at 0/5%/15%; BULLISH STRONG at >=15%, BEARISH below 0
- Growth: both revenue_growth and earnings_growth assessed together; 4 outcomes (strong/positive/mixed/declining) plus partial and missing
- Debt: debt_to_equity thresholds at 50/150; negative D/E treated as unusual with lower confidence
- Cash flow: positive FCF is BULLISH, negative is BEARISH, zero is NEUTRAL
- Missing fields always produce a neutral Signal with confidence=0.30 rather than raising exceptions
- Also removed unused `Field` import from `app/models/fundamentals.py` (Pylance diagnostic)
- Added 65 unit tests in `tests/test_fundamentals_analysis.py`; full suite 302/302 passing
- Scoring and CLI untouched; fundamental signals not yet wired into scoring

## 2026-05-17 — Fundamental data layer

- Added `app/models/fundamentals.py` with `CompanyFundamentals` Pydantic model
- Added `app/data/fundamentals.py` with `get_company_fundamentals()` and `FundamentalDataFetchError`
- Fetches 15 fields from `yfinance.Ticker.info`: identity (name, sector, industry) and key metrics (market cap, P/E ratios, P/B, margins, growth rates, D/E, FCF, dividend yield, beta)
- `_safe_float` converts yfinance values safely: rejects None, NaN, Inf, and non-numeric strings → None
- `_extract_company_name` prefers `longName` over `shortName`; raises if neither is present
- Added 43 unit tests in `tests/test_fundamentals_data.py`; full suite 237/237 passing
- Scoring and technical analysis untouched; scoring weights unchanged

## 2026-05-14 — v0.1 milestone quality review

- Reviewed all 7 source modules, 7 test files, README, CLAUDE.md, and 4 docs files
- No architectural violations, no import boundary issues, no stale or live-API tests found
- Removed `# type: ignore[union-attr]` in `_validate_summary_input` — converted to `set(summary)` for clean narrowing
- Fixed `rating.py` module docstring: "future scoring engine" → "scoring engine"
- Updated README: corrected stale test count (41→194), placeholder labels on `main.py` and `models/`
- Updated CLAUDE.md: added all 6 currently-implemented modules to the table; added `<TICKER>` to CLI example
- Updated `docs/architecture.md`: marked each file as ✓ implemented or ○ planned
- Updated `docs/scoring_rules.md`: replaced placeholder thresholds with the actual implemented values; moved risk_block note to "planned" section
- 194/194 tests passing; `python -m app.main AAPL` produces correct technical-only output

## 2026-05-14 — CLI pipeline wired in app/main.py

- Implemented `analyze_ticker(ticker)` — orchestrates the full technical analysis pipeline
- Implemented `format_rating_output(rating)` — renders a human-readable terminal summary
- Implemented `main(argv)` — CLI entry point; handles missing ticker (exit 1 + usage), `DataFetchError`, `TechnicalAnalysisError`, and `ScoringError` gracefully (stderr + exit 1)
- Added 24 unit tests in `tests/test_main.py`; entire pipeline mocked — no live API calls
- Full suite 194/194 passing; smoke test `python -m app.main AAPL` produces structured output

## 2026-05-14 — Technical-only scoring module

- Added `app/analysis/scoring.py` with `ScoringError` and `score_technical_signals()`
- Scoring: sums `score_impact` across signals, clamps to [-1, 1], scales to 0–100 via `50 + impact * 50`
- Maps composite score to `RatingCategory`; maps average signal confidence to `ConfidenceLevel`
- Populates `key_positive_factors` from bullish signals and `key_risks` from bearish signals
- Non-implemented sub-scores (`fundamental_score`, `news_score`, `risk_score`) explicitly set to 0.0
- Added 36 unit tests in `tests/test_scoring.py`; full suite 170/170 passing

## 2026-05-14 — Typed Rating model foundation

- Added `app/models/rating.py` with `RatingCategory` and `ConfidenceLevel` enums and `Rating` Pydantic model
- `RatingCategory` uses project-specific labels: Strong Buy Candidate, Buy Candidate, Watchlist, Hold, Avoid, Sell / Exit Warning
- Score fields (composite + 4 sub-scores) constrained to 0–100 via `Field(ge=0.0, le=100.0)`
- Ticker stripped and uppercased via `@field_validator`; explanation validated non-blank
- `signals_used: list[Signal]` embeds provenance directly in the output model
- Added `is_positive_rating`, `is_negative_rating`, `is_neutral_rating` convenience properties
- Added 37 unit tests in `tests/test_rating.py` including JSON round-trip; full suite 134/134 passing

## 2026-05-14 — Technical signal builder

- Added `build_technical_signals(indicator_summary)` to `app/analysis/technicals.py`
- Converts the dict from `summarize_technical_signals()` into 7 typed `Signal` objects (trend, RSI, MACD, price vs SMA 20/50/200, volume)
- Added `REQUIRED_SUMMARY_KEYS` constant and `_validate_summary_input` helper
- Added 34 unit tests in `tests/test_build_technical_signals.py`; full suite 97/97 passing

## 2026-05-14 — Typed signal model foundation

- Added `app/models/signal.py` with `Signal` Pydantic model and `SignalCategory`, `SignalDirection`, `SignalStrength` enums
- Validated: name/description non-blank, `score_impact` ∈ [-1.0, 1.0], `confidence` ∈ [0.0, 1.0]
- Optional fields: `value`, `source`, `timestamp`, `metadata` (safe default factory)
- Added `is_bullish`, `is_bearish`, `is_neutral` convenience properties
- Added 22 unit tests in `tests/test_signal.py`; full suite 63/63 passing

## 2026-05-14 — Documentation update and foundation review

- README rewritten to accurately reflect implemented state; removed references to unbuilt features
- CLAUDE.md updated with explicit guardrails, implemented module list, layer rules, and development standards
- `app/analysis/technicals.py`: removed redundant `isinstance` check in `_validate_ohlcv_input` and dropped unnecessary `# type: ignore` comment
- `app/analysis/technicals.py`: fixed `_calculate_rsi` to use `.where()` instead of `.fillna(100)` so pre-window rows correctly stay NaN rather than being incorrectly filled with 100
- All 41 tests pass; no behavior changes

## 2026-05-14 — Technical analysis module implemented

- Added `app/analysis/technicals.py` with `TechnicalAnalysisError`, `calculate_technical_indicators()`, and `summarize_technical_signals()`
- Indicators: SMA 20/50/200, RSI 14, MACD/signal/histogram, volume SMA 20, daily return
- Summary helper classifies trend (bullish/bearish/mixed), RSI condition, and MACD condition from the latest row
- All calculations use pandas only; no external indicator libraries
- Added 26 unit tests in `tests/test_technicals.py` (no network calls); full suite 41/41 passing

## 2026-05-12 — Market data module implemented

- Added `app/data/market_data.py` with `get_price_history()` and `DataFetchError`
- Fetches historical OHLCV data via yfinance; normalizes column names; validates inputs and output shape
- Added 15 unit tests in `tests/test_market_data.py` (all passing, no live API calls)

## 2026-05-12 — Project skeleton created

- Initialized repository with full modular project structure
- Created `app/` package with `data/`, `analysis/`, `reports/`, `models/`, and `utils/` sub-packages
- Added placeholder docstrings to all Python modules
- Created `requirements.txt`, `.env.example`, and `.gitignore`
- Added `docs/` with project plan, architecture overview, scoring rules, and data sources
- Added `prompts/` to track Claude prompts used during development
- Confirmed: no trading execution, no broker integration, no ML, no web dashboard in v1
