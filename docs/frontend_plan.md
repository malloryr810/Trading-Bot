# Frontend Plan — Investment Bot

> **Status:** Milestone 1 complete — React + Vite shell with API connectivity is built and tested.
> Dashboard page (health check, disclaimer) and Analyze page (analyze-only + analyze-and-save) are live.
> Milestone 2 (report history + detail pages) is next.

---

## 1. Purpose

The Investment Bot backend is fully functional: it analyzes tickers, scores signals,
generates structured StockReport outputs, and persists snapshots to SQLite. The
terminal CLI works today. The FastAPI backend is ready to be consumed.

The frontend exists to make all of that usable without terminal commands:

- Let the user enter a ticker and request analysis from a browser.
- Display StockReport output in a readable, structured layout.
- Let the user browse and review saved report history.
- Let the user drill into one saved report for the full analysis detail.

The backend remains the single source of truth for all analysis, scoring, report
generation, and persistence. The frontend is a display and input layer only.

---

## 2. Non-Goals

The frontend must not implement or expose any of the following, in any milestone:

- Live or paper trading of any kind
- Broker API integration
- Order placement or order management
- Real-money portfolio management
- Margin or options features
- Frontend-side scoring or signal calculation
- Frontend-side duplication of category, threshold, or weight logic
- ML inference or model calls
- Mock trading simulation (not until the backend phase for that is scoped and built)
- Authentication or user accounts (not until intentionally added as a separate milestone)

If a feature requires the frontend to recalculate a rating, rebuild a signal, or
replicate analysis logic, that feature belongs in the backend first.

---

## 3. Recommended Frontend Stack

### Options considered

| Option | Pros | Cons |
|--------|------|------|
| **React + Vite** | Lightweight, clean FastAPI pairing, standard full-stack pattern, good component ecosystem, easy to extend | Requires wiring routing and API client manually |
| **Next.js** | Full-featured, SSR/SSG, file-based routing | More complex than needed now; SSR adds overhead for a personal tool with no SEO requirement |
| **Streamlit** | Near-zero setup, good for data exploration | Python-only, not a real frontend, poor production story, hard to extend into a polished product |

### Recommendation: React + Vite

React + Vite is the right choice for the first real frontend milestone:

- Lightweight and fast to scaffold.
- Works cleanly with a FastAPI backend over HTTP — no framework coupling.
- Avoids Next.js complexity (SSR, file-based routing conventions, deployment constraints)
  that add no value for a personal single-user tool at this stage.
- Is better practice as a full-stack portfolio project than a Streamlit prototype.
- Can later support routing, saved reports, dashboard pages, charts, and richer UI
  components without rearchitecting.
- TypeScript support from day one, which pairs well with the typed Pydantic response
  schemas already defined in the backend.

**Streamlit note:** Streamlit could be a useful internal prototype for fast iteration,
but it should not be the main frontend if the goal is a full-stack investment research
platform. A Streamlit prototype would need to be discarded and replaced, not evolved.

---

## 4. Frontend App Structure

The following folder structure is proposed. **Do not create this yet.**
It is defined here as a target layout for Milestone 1 onward.

```
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    api/
      client.ts          # Base axios/fetch wrapper; base URL, error handling
      reportsApi.ts      # Functions for each backend endpoint
    components/
      ScoreCard.tsx           # Displays score + category as a styled card
      ReportSummaryCard.tsx   # One row/card for a saved report summary
      RiskList.tsx            # Bulleted list of key risks or positive factors
      LoadingState.tsx        # Spinner or skeleton while a request is in flight
      ErrorMessage.tsx        # Displays a user-friendly error with optional detail
    pages/
      DashboardPage.tsx       # Entry point, recent reports, quick actions
      AnalyzePage.tsx         # Ticker input, analyze/save actions, result preview
      ReportHistoryPage.tsx   # Table/list of all saved reports
      ReportDetailPage.tsx    # Full view of one saved StockReport
    types/
      report.ts          # TypeScript interfaces mirroring backend response shapes
    App.tsx              # Root component, router setup
    main.tsx             # Vite entry point
```

### Folder purposes

| Folder / File | Purpose |
|---------------|---------|
| `api/client.ts` | Single place to configure base URL, request headers, and shared error handling. All API calls go through here. |
| `api/reportsApi.ts` | One function per endpoint. Keeps component files free of raw `fetch` calls. |
| `components/` | Small, reusable UI pieces. None of these call the API directly. |
| `pages/` | One file per screen. Pages own layout and orchestrate data fetching; they compose components. |
| `types/report.ts` | TypeScript interfaces that mirror `StockReport`, `SavedReportSummary`, and `SavedReportDetail` from the backend. Keeps the rest of the codebase type-safe without importing Python models. |
| `App.tsx` | Top-level router and layout shell. |
| `main.tsx` | Vite entry point; renders `<App />`. |

---

## 5. Initial Screens

### A. Dashboard Page

**Route:** `/`

**Purpose:** Entry point into the app. Orientates the user, shows recent saves,
and surfaces quick actions.

**Should include:**

- A prominent "Analyze a ticker" button/card linking to the Analyze page.
- A "Recent reports" section showing the last 5–10 saved report summaries
  (ticker, category, score, date), each linking to the detail page.
- A "View full history" link to the Report History page.
- A visible disclaimer: *"This tool provides research support only. It does not
  provide financial advice and is not an automated trading system. All output
  should be treated as a starting point for your own due diligence."*

**API calls:** `GET /api/reports/history?limit=10`

---

### B. Analyze Ticker Page

**Route:** `/analyze`

**Purpose:** Let the user request a stock analysis and choose whether to save it.

**Should include:**

- A text input for the ticker symbol (uppercase, trimmed before submission).
- Two distinct actions:
  - **Analyze only** — calls `POST /api/analyze`. Result is shown in-page but not
    persisted. Useful for a quick look without cluttering history.
  - **Analyze and save** — calls `POST /api/reports/analyze`. Result is shown in-page
    and saved to history.
- A loading state while the request is in flight (analysis typically takes a few seconds
  against live data).
- A clear error display for invalid tickers (422), backend failures (500), or
  network errors.
- When analysis completes, show a result preview: category badge, score, confidence,
  technical/fundamental/news/risk summaries, key positives, key risks.
- A "View full saved report" link when the analyze-and-save path was used.

---

### C. Saved Reports / History Page

**Route:** `/history`

**Purpose:** Browse all saved StockReport snapshots in reverse-chronological order.

**Should include:**

- A table or card list where each row shows:
  - Ticker
  - Company name
  - Category (e.g., "Watchlist", "Buy Candidate")
  - Score (e.g., 72.5)
  - Confidence (e.g., "medium")
  - Created timestamp (formatted local time)
  - A "View" link to the detail page
- An empty state message when no reports have been saved yet.
- No pagination required in Milestone 1; the default limit of 50 from the API is
  sufficient. Filtering and pagination can be added later.

**API call:** `GET /api/reports/history`

**Future improvement (no backend changes needed yet):** The history endpoint already
accepts a `limit` query parameter. Future frontend milestones can add filter controls
for ticker, category, date range, or custom limit without requiring backend changes.

---

### D. Report Detail Page

**Route:** `/reports/:id`

**Purpose:** Display one full saved StockReport snapshot.

**Should include:**

- Header section: ticker, company name, category badge, score, confidence level.
- Analysis summaries (where present): technical summary, fundamental summary, news
  summary, risk summary — each in its own labelled section.
- Key positive factors as a bulleted list.
- Key risks as a bulleted list.
- Triggers: buy trigger and sell/avoid trigger where present.
- Metadata footer: data timestamp (formatted), data sources used, report ID,
  saved-at timestamp.
- A "← Back to history" link.
- A "Analyze again" shortcut that pre-fills the ticker on the Analyze page.

**API call:** `GET /api/reports/{report_id}`

---

## 6. API Contract

**Local development base URL:** `http://127.0.0.1:8000`

Backend schemas referenced throughout: `app/api/schemas/analysis.py`,
`app/api/schemas/reports.py`, `app/models/stock_report.py`.

---

### `GET /api/health`

| Field | Value |
|-------|-------|
| Method | GET |
| Path | `/api/health` |
| Purpose | Verify the backend is reachable before making analysis calls |
| Request body | None |
| Response (200) | `{ "status": "ok", "service": "investment-bot-api" }` |
| On success | Show a "connected" indicator; proceed normally |
| On error | Show a "Backend unavailable" banner; disable analysis actions |

---

### `POST /api/analyze`

| Field | Value |
|-------|-------|
| Method | POST |
| Path | `/api/analyze` |
| Purpose | Analyze a ticker; return a StockReport. Nothing is saved. |
| Request body | `{ "ticker": "AAPL" }` |
| Response (200) | Full `StockReport` object (see `app/models/stock_report.py`) |
| Response (422) | Unprocessable entity — invalid ticker or analysis pipeline error. `detail` field contains the message. |
| Response (500) | Unexpected backend error |
| On success | Render the result in-page |
| On 422 | Display the `detail` message in the error component |
| On 500 / network error | Display a generic "Analysis failed — try again" message |

---

### `POST /api/reports/analyze`

| Field | Value |
|-------|-------|
| Method | POST |
| Path | `/api/reports/analyze` |
| Purpose | Analyze a ticker and persist the StockReport snapshot |
| Request body | `{ "ticker": "AAPL" }` |
| Response (200) | `SavedReportDetail` — summary fields plus full `report` object (see `app/api/schemas/reports.py`) |
| Response (422) | Analysis pipeline error. `detail` contains the message. Nothing was saved. |
| Response (500) | Unexpected error. If `detail` is `"Failed to save report"`, analysis succeeded but persistence failed. |
| On success | Render result in-page; offer link to the saved report detail page using the returned `id` |
| On 422 | Display the error; do not navigate away |
| On 500 with "Failed to save report" | Warn the user that analysis succeeded but the result was not saved; show the analysis result anyway if available |
| On other 500 / network error | Display a generic error message |

---

### `GET /api/reports/history`

| Field | Value |
|-------|-------|
| Method | GET |
| Path | `/api/reports/history` |
| Query params | `limit` (optional, default 50) |
| Purpose | Return a list of saved report summaries, newest first |
| Response (200) | Array of `SavedReportSummary` objects — id, ticker, company_name, category, score, confidence, created_at |
| On success | Render the list |
| On empty list | Show an empty-state message: "No saved reports yet. Analyze a ticker to get started." |
| On error | Show an error message; do not crash the page |

---

### `GET /api/reports/{report_id}`

| Field | Value |
|-------|-------|
| Method | GET |
| Path | `/api/reports/{report_id}` |
| Purpose | Return one full saved StockReport snapshot |
| Response (200) | `SavedReportDetail` — summary fields plus full nested `report` object |
| Response (404) | Report not found |
| On success | Render the full detail page |
| On 404 | Show a "Report not found" message with a link back to history |
| On error | Show a generic error message |

---

## 7. Loading and Error States

| Scenario | Expected UI behavior |
|----------|---------------------|
| Backend unavailable (health check fails or request times out) | Show a persistent "Backend unavailable" banner at the top of the page; disable analyze and history features |
| Invalid ticker (422) | Inline error below the ticker input: display the `detail` message from the response |
| Analysis pipeline error (422 from backend) | Same as invalid ticker — show the specific error from `detail` |
| No saved reports yet | Empty state on the history page: "No saved reports yet. Use 'Analyze and save' to get started." |
| Report ID not found (404) | "Report not found" message with a back link; do not crash the route |
| Analysis in flight (typically 5–15 seconds against live data) | Show a spinner or progress indicator with a message like "Analyzing — this may take a few seconds" |
| Save failure after successful analysis (500 with "Failed to save report") | Show both: the analysis result (so the user can read it) and a warning that the result was not saved |
| Unexpected 500 from any endpoint | Generic message: "Something went wrong. Please try again." Do not expose internal error detail to the user. |

---

## 8. Data Ownership Rules

These rules apply to every frontend component and page, in every milestone:

| Rule | Rationale |
|------|-----------|
| Backend owns all analysis logic | `app/analysis/` is the only place signals are computed |
| Backend owns all scoring logic | `app/analysis/scoring.py` is the only place ratings and categories are produced |
| Backend owns StockReport generation | `app/reports/` is the only place StockReport objects are assembled |
| Backend owns persistence | `app/services/report_persistence_service.py` is the only place reports are saved and retrieved |
| Frontend only displays API responses and submits user actions | The frontend is a rendering and input layer |
| Frontend may format dates, numbers, and layout | ISO timestamps can be converted to local time; scores can be rounded for display |
| Frontend must not recalculate ratings or categories | Never derive "Buy Candidate" from a score client-side; always use the `final_category` field from the API |
| Frontend must not replicate signal weights or thresholds | These live in `app/analysis/scoring.py` and must not be duplicated anywhere in the frontend |

---

## 9. First Frontend Implementation Milestone

**Milestone name:** Frontend Milestone 1 — React + Vite shell with API connectivity

### In scope

- Scaffold a React + Vite + TypeScript project under `frontend/`.
- Configure a basic router (React Router v6 or equivalent).
- Implement `api/client.ts` with base URL configuration.
- Implement `api/reportsApi.ts` with functions for all five current endpoints.
- Implement `types/report.ts` with TypeScript interfaces mirroring backend schemas.
- Add a health check indicator on the app shell (connected / not connected).
- Implement the **Analyze page** (`/analyze`):
  - Ticker input.
  - Analyze-only action (POST /api/analyze).
  - Analyze-and-save action (POST /api/reports/analyze).
  - Loading state.
  - Error display.
  - Basic result display (category, score, confidence, summaries).

### Out of scope for Milestone 1

- Report History page (Milestone 2).
- Report Detail page (Milestone 2).
- Dashboard (Milestone 3).
- Charts and visualizations (Milestone 4).
- Watchlist UI (Milestone 5, after backend watchlist API exists).
- Mock trading UI (Milestone 6, after backend mock trading exists).
- Authentication.
- Deployment configuration.
- Portfolio features of any kind.
- Advanced styling or design system — functional layout is sufficient.

---

## 10. Later Frontend Milestones

| Milestone | Scope | Backend dependency |
|-----------|-------|--------------------|
| **2** | Saved report history page (GET /api/reports/history) and report detail page (GET /api/reports/{id}) | None — endpoints exist |
| **3** | Dashboard page: quick actions, recent reports preview, disclaimer | None — uses existing history endpoint |
| **4** | Charts and data visualization — score trend, signal breakdown, category distribution | May benefit from backend aggregation endpoints |
| **5** | Watchlist UI — browse, add, remove, scan | Requires backend watchlist API (not yet built) |
| **6** | Mock trading simulation UI | Requires backend simulation layer (Phase 7 in CLAUDE.md) |

---

## 11. Open Questions

These decisions should be resolved before Milestone 1 implementation begins:

| Question | Options / Notes |
|----------|----------------|
| Final stack confirmation | React + Vite is recommended; confirm before scaffolding |
| Styling approach | Plain CSS modules, Tailwind CSS, or a component library (shadcn/ui, Radix UI, etc.) |
| Repository layout | Frontend under `frontend/` in the same repo (recommended for a personal project) vs. a separate repo |
| API base URL configuration | Store in `frontend/.env` as `VITE_API_BASE_URL`; default to `http://127.0.0.1:8000` |
| CORS middleware | FastAPI currently has no CORS config. Add `fastapi.middleware.cors.CORSMiddleware` before Milestone 1 begins (a one-line backend change) |
| History pagination | Current endpoint supports `limit` only. Decide whether to add `offset` or cursor-based pagination before building the history page, or accept limit-only for Milestone 2 |

---

## 12. Recommended Next Step

**Do not implement frontend code immediately.**

Review this plan. Resolve the open questions in Section 11. When ready, open a new,
narrow implementation task:

> **"Frontend Milestone 1 — React + Vite shell with API connectivity"**
>
> Scaffold the frontend app, implement the API client, and build the Analyze page
> connected to POST /api/analyze and POST /api/reports/analyze. Follow the structure
> and rules defined in docs/frontend_plan.md.

Add `CORSMiddleware` to `app/api/main.py` as a prerequisite before that task begins.
