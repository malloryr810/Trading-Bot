# Phase 5 — Watchlist Management Plan

> **Status: Implemented.** This plan has since been built — watchlist CRUD
> (tables, `watchlist_service`, `/api/watchlists` routes, Watchlists frontend
> page) plus on-demand watchlist analysis (`watchlist_analysis_service`,
> `POST /api/watchlists/{id}/analyze`, results shown on the Watchlists page and
> not saved). The document below is retained as the original design plan; see
> `CLAUDE.md` and `docs/development_log.md` for the current state.
>
> Original planning note: this plan must respect every guardrail in `CLAUDE.md`:
> no broker APIs, no live trading, no order execution, no alerts, no scheduled
> scans, no mock simulation, no ML scoring, and no portfolio logic. Existing
> scoring, analysis, report generation, and CLI behavior must not change.

## 1. Purpose

Watchlist management lets a user create and maintain **named lists of tickers**
(for example "Semiconductors" or "Dividend Watch") that they intend to research
later. It gives the app a durable place to organize the tickers a user cares
about, instead of re-typing them into the Analyze page each time.

**This phase is management/storage only.** Milestone 1 delivers create / read /
update / delete (CRUD) for watchlists and their tickers, plus a simple frontend
to drive that CRUD. It does **not** run any analysis on a watchlist.

**Watchlist analysis comes later.** Once the CRUD foundation is stable and
tested, a future milestone can add an "analyze this watchlist" flow that reuses
the *existing* single-ticker pipeline (`analyze_stock`) across the saved
tickers. That work is explicitly out of scope here — the goal now is a clean,
well-tested storage layer to build on.

## 2. Scope for Phase 5 Milestone 1

In scope for this milestone:

- **Create** a saved watchlist (name + optional description).
- **List** all saved watchlists.
- **View** a single watchlist, including its tickers.
- **Rename / update** a watchlist's metadata (name, description).
- **Delete** a watchlist (and its tickers).
- **Add** one or more tickers to a watchlist.
- **Remove** a ticker from a watchlist.
- A basic **frontend page** (or small set of pages) to manage the above.

## 3. Non-goals

Explicitly **excluded** from this phase (and from this plan):

- Scheduled scans or background jobs.
- Alerts or notifications of any kind.
- Broker / trading integration.
- Auto buy / sell logic.
- Mock trading or paper trading.
- ML scoring or model-based ranking.
- Portfolio allocation, weighting, or position tracking.
- Complex analytics (correlations, aggregate scores, dashboards over time).
- Reworking the existing scoring model, signals, or report generation.

If any of these are wanted later, they require their own scoped phase and
explicit approval — consistent with the Non-Negotiable Guardrails in `CLAUDE.md`.

## 4. Proposed backend data model

Two simple SQLite tables, defined with **SQLAlchemy Core** to match the existing
`analysis_reports` table in `app/data/database.py`.

### `watchlists`

| Column        | Type      | Notes                                   |
|---------------|-----------|-----------------------------------------|
| `id`          | Integer   | Primary key, autoincrement              |
| `name`        | String    | Required, human-readable list name      |
| `description` | String    | Optional, may be null/empty             |
| `created_at`  | DateTime  | Set on creation                         |
| `updated_at`  | DateTime  | Updated on metadata or ticker changes   |

### `watchlist_tickers`

| Column         | Type     | Notes                                              |
|----------------|----------|----------------------------------------------------|
| `id`           | Integer  | Primary key, autoincrement                         |
| `watchlist_id` | Integer  | Foreign key → `watchlists.id`                      |
| `ticker`       | String   | Required, stored normalized (trimmed + uppercase)  |
| `created_at`   | DateTime | Set when the ticker is added                       |

### Validation and integrity notes

- **Normalize tickers** before storing: trim surrounding whitespace and
  uppercase. Reuse `app/utils/helpers.py::normalize_ticker` so behavior matches
  the rest of the pipeline rather than introducing a second rule.
- **Reject empty tickers** — a ticker that is empty after trimming is invalid
  input and should produce a clear validation error.
- **Duplicate tickers within the same watchlist** must be handled
  **consistently**. Recommended: treat add-of-existing as an idempotent no-op
  (return the current list, HTTP 200) rather than creating a second row or
  erroring. A composite uniqueness guard on `(watchlist_id, ticker)` enforces
  this at the data layer. Whichever rule is chosen, document it once and apply
  it everywhere.
- **Deleting a watchlist removes its ticker rows.** Because the engine is
  SQLite via SQLAlchemy Core, the service layer should delete child rows
  explicitly (or rely on a configured `ON DELETE CASCADE`) so no orphan
  `watchlist_tickers` rows remain.
- **`updated_at`** on the parent watchlist should advance when tickers are added
  or removed, so the list view can show meaningful "last changed" ordering.

## 5. Proposed backend module layout

Suggested files — **not implemented in this document**. Final layout should
follow existing project patterns (thin routes → service → data), not diverge
from them.

| File                                   | Responsibility                                                        |
|----------------------------------------|-----------------------------------------------------------------------|
| `app/data/database.py`                 | Add `watchlists` and `watchlist_tickers` `Table` definitions          |
| `app/services/watchlist_service.py`    | All watchlist business/application logic (CRUD + validation)          |
| `app/api/routes/watchlists.py`         | Thin FastAPI route module (matches `app/api/routes/reports.py` style) |
| `app/api/schemas/watchlists.py`        | Pydantic request/response schemas for the endpoints                   |
| `tests/test_watchlist_service.py`      | Service-layer unit tests (in-memory engine injection)                 |
| `tests/test_watchlist_api.py`          | API integration tests via FastAPI `TestClient`                        |

Pattern notes drawn from the current codebase:

- The route module belongs under `app/api/routes/` and is registered in
  `app/api/main.py` with `_app.include_router(watchlists.router, prefix="/api")`,
  mirroring `health`, `analysis`, and `reports`.
- The router should set `prefix="/watchlists"` and `tags=["watchlists"]`, just as
  `reports.py` uses `APIRouter(prefix="/reports", tags=["reports"])`.
- Service functions should accept an optional `engine` keyword argument for test
  injection (e.g. `build_engine(":memory:")`), exactly like
  `report_persistence_service`. Production callers omit it and share a lazily
  initialized engine.
- **No pipeline or persistence logic in route handlers** — routes call the
  service, map known errors to HTTP status codes, and return the result.

## 6. Proposed API contract

All endpoints are prefixed with `/api`. Responses follow the existing app style
(typed Pydantic models serialized to JSON). Ticker path/body values are
normalized server-side before use.

### `GET /api/watchlists`

- **Purpose:** List all saved watchlists (summary view, newest or
  recently-updated first).
- **Request:** none (optionally a `limit` query param, consistent with
  `/api/reports/history`).
- **Response:** array of watchlist summaries — `id`, `name`, `description`,
  `created_at`, `updated_at`, and a `ticker_count`.
- **Errors:** `500` on unexpected failure.

### `POST /api/watchlists`

- **Purpose:** Create a new watchlist.
- **Request:** `{ "name": string, "description"?: string, "tickers"?: string[] }`.
  `tickers` is optional convenience for seeding the list at creation.
- **Response:** the created watchlist detail (id, metadata, normalized tickers).
- **Errors:** `422` on invalid input (missing/blank name, invalid ticker);
  `500` on unexpected failure.

### `GET /api/watchlists/{watchlist_id}`

- **Purpose:** Retrieve one watchlist with its tickers.
- **Request:** none.
- **Response:** watchlist detail — metadata plus the ordered list of tickers.
- **Errors:** `404` if the id does not exist.

### `PATCH /api/watchlists/{watchlist_id}`

- **Purpose:** Update watchlist metadata (rename, edit description).
- **Request:** `{ "name"?: string, "description"?: string }` — partial update;
  only provided fields change.
- **Response:** the updated watchlist detail.
- **Errors:** `404` if not found; `422` if a provided field is invalid (e.g.
  blank name).

### `DELETE /api/watchlists/{watchlist_id}`

- **Purpose:** Delete a watchlist and all of its ticker rows.
- **Request:** none.
- **Response:** `204 No Content` (or a small confirmation body).
- **Errors:** `404` if not found.

### `POST /api/watchlists/{watchlist_id}/tickers`

- **Purpose:** Add one or more tickers to an existing watchlist.
- **Request:** `{ "tickers": string[] }` (accept a single-element array for the
  add-one case). Each ticker is trimmed and uppercased; blanks are rejected;
  duplicates are handled per the consistent rule in §4.
- **Response:** the updated watchlist detail (full current ticker list).
- **Errors:** `404` if the watchlist does not exist; `422` if any ticker is
  invalid.

### `DELETE /api/watchlists/{watchlist_id}/tickers/{ticker}`

- **Purpose:** Remove a single ticker from a watchlist.
- **Request:** `ticker` path param (normalized server-side before matching).
- **Response:** the updated watchlist detail.
- **Errors:** `404` if the watchlist does not exist (or, optionally, if the
  ticker is not present — decide one behavior and document it; an idempotent
  `200`/`204` for "already absent" is acceptable and consistent with the
  duplicate-handling stance).

> **CORS note:** `app/api/main.py` currently sets
> `allow_methods=["GET", "POST"]`. The `PATCH` and `DELETE` endpoints above will
> require adding those methods to the CORS middleware so the browser frontend can
> call them. This is a one-line config change to make during implementation, not
> a behavioral change to existing endpoints.

## 7. Frontend plan

React + Vite + TypeScript, matching the existing `frontend/src` structure
(`api/`, `pages/`, `types/`, `components/`). **Display and orchestration only —
no analysis, scoring, category derivation, or weight logic in the frontend.**

UI elements for Milestone 1:

- **Navigation:** add a "Watchlists" entry alongside the existing Dashboard /
  Analyze nav.
- **Route:** add `/watchlists` (React Router, already a dependency).
- **List view:** show all saved watchlists (name, description, ticker count).
- **Create form:** name + optional description → `POST /api/watchlists`.
- **Select / view:** selecting a watchlist shows its detail.
- **Ticker list:** show the tickers in the selected watchlist.
- **Add ticker form:** single input → `POST /api/watchlists/{id}/tickers`.
- **Remove ticker action:** per-ticker control →
  `DELETE /api/watchlists/{id}/tickers/{ticker}`.
- **Loading state:** reuse the existing `LoadingState` component.
- **Empty state:** clear "No watchlists yet — create one" / "No tickers yet"
  messaging.
- **Error state:** reuse the existing `ErrorMessage` component; surface
  `ApiError` messages from the client.

Frontend data rules:

- Add typed client functions in a new `frontend/src/api/watchlistApi.ts`, one
  function per endpoint, mirroring `analysisApi.ts` (which wraps the base
  `client.ts` fetch helper and `ApiError`).
- Add TypeScript interfaces for watchlist shapes in `frontend/src/types/`
  (e.g. `watchlist.ts`), mirroring the backend response models.
- The frontend formats dates/strings for display only; it never recalculates
  anything the backend owns.

## 8. Testing plan

### Backend (required this milestone)

Tests use pytest with an in-memory engine injected into the service
(`build_engine(":memory:")`), keeping them deterministic and isolated — no live
APIs, consistent with existing tests.

**Service tests (`tests/test_watchlist_service.py`):**

- Create a watchlist (with and without seed tickers).
- List watchlists (empty and populated).
- Read one watchlist by id; read of missing id behaves as defined.
- Update watchlist metadata (rename, description, partial update).
- Delete a watchlist; confirm its ticker rows are also gone.
- Add tickers (normalization: trimming + uppercasing verified).
- Duplicate ticker handling (idempotent per §4 — no duplicate rows).
- Remove a ticker; remove a not-present ticker behaves as defined.
- Invalid input: blank name, empty/whitespace ticker → validation error.

**API tests (`tests/test_watchlist_api.py`):** via FastAPI `TestClient`.

- Happy paths for all seven endpoints (correct status + response shape).
- Error paths: `404` for unknown `watchlist_id`, `422` for invalid input.
- Round-trip: create → add tickers → read → remove ticker → delete.

### Frontend

The frontend currently has **no test framework configured** (`frontend/package.json`
has no vitest / testing-library / jest setup). Therefore, automated frontend
tests are **not** part of this milestone. **Manual verification is acceptable**
for Milestone 1: run the dev server, exercise create / view / add / remove /
delete against the live API, and confirm loading, empty, and error states
render. A frontend test harness can be added in a later, separately scoped task.

## 9. Implementation sequence

Recommended order (each step small and reviewable):

1. Update docs with this plan (this document).
2. Implement the `watchlists` and `watchlist_tickers` table definitions in
   `app/data/database.py`.
3. Implement `app/services/watchlist_service.py` (CRUD + validation).
4. Add backend service tests (`tests/test_watchlist_service.py`).
5. Add FastAPI routes (`app/api/routes/watchlists.py` + schemas), register the
   router, and extend CORS methods to include `PATCH`/`DELETE`.
6. Add API tests (`tests/test_watchlist_api.py`).
7. Add typed frontend API client functions (`frontend/src/api/watchlistApi.ts`)
   and types.
8. Add the Watchlists page and `/watchlists` route + nav entry.
9. Manually verify backend (via `/docs`) and frontend (dev server) end to end.
10. Update `docs/development_log.md` with an entry for the change.
11. Run the full test suite (`pytest`) and the frontend build/lint.
12. Commit (and confirm `python -m app.main` still works — no CLI regression).

## 10. Future extensions

Out of scope now, but natural follow-ups once CRUD is stable:

- **Analyze all tickers** in a watchlist by reusing the existing `analyze_stock`
  pipeline across the saved tickers (no new analysis logic). ✓ Done (analyze-only).
- **Save watchlist analysis snapshots** alongside the existing report history.
  ✓ Done (Phase 6, Milestone 1) — see below.
- **Compare watchlist reports over time** (read-only historical view).

## 10a. Saved analysis snapshots (Phase 6, Milestone 1 — done)

A **snapshot** is a historical record of a single, explicitly user-triggered
on-demand analysis run. It is **storage-separate** from watchlist CRUD and from
`analysis_reports`, and is **never** written by a schedule or background job.

- Tables (`app/data/database.py`): `watchlist_analysis_snapshots` (one row per
  run: watchlist id + denormalised name, `analyzed_at`, total/success/failure
  counts, `created_at`) and `watchlist_analysis_snapshot_results` (one row per
  ticker; success rows store the full success item as `summary_json`, failure
  rows store `error_message`). `watchlist_name` is denormalised so a snapshot
  stays readable after a rename/delete.
- Service: `app/services/watchlist_analysis_snapshot_service.py`
  (`analyze_and_save_snapshot`, `save_watchlist_analysis_snapshot`,
  `list_watchlist_snapshots`, `get_watchlist_snapshot`). It reuses
  `analyze_watchlist` — no new analysis/scoring logic.
- API (`app/api/routes/watchlist_snapshots.py`):
  - `POST /api/watchlists/{id}/analysis-snapshots` — analyze once **and** save
    (explicit; distinct from the analyze-only endpoint, which still never saves).
  - `GET  /api/watchlists/{id}/analysis-snapshots` — list summaries (newest first).
  - `GET  /api/watchlist-analysis-snapshots/{snapshot_id}` — full detail.
- Frontend: an "Analyze & save snapshot" button plus a saved-snapshots list on
  the selected watchlist. A snapshot **detail page** (Milestone 2,
  `/watchlists/:watchlistId/snapshots/:snapshotId`) reuses the detail endpoint to
  review a saved run read-only. A **snapshot trend chart** (Lightweight Charts)
  now sits above the saved-snapshots list, built purely from the already-loaded
  snapshot summaries — no extra API calls. An in-card toggle switches between
  `success_count` over `analyzed_at` and a backend-derived **`average_score`**
  over `analyzed_at` (one line at a time; defaults to success count).
  `average_score` (`float | null`) is computed in the snapshot service from the
  stored scores of successful result rows only (failed rows ignored; `null` when
  none) and returned on the snapshot summary — the frontend never computes it.
- **Tag watchlists** for lightweight categorization.
- **Add notes per ticker** within a watchlist.
- **Mock simulation** only much later, and only after the core research workflow
  is stable — and only when explicitly scoped and approved, per the guardrails.
