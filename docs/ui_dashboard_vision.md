# UI Vision & Dashboard Redesign Plan

> **Status:** Planning document only. No frontend or backend code changes are
> part of this milestone. This doc defines the intended direction for the
> frontend before any redesign work begins. It supersedes the visual/layout
> direction implied in `docs/frontend_plan.md` (which remains accurate for the
> existing routes, API contract, and data-ownership rules).

---

## 1. Product Vision

Investment Bot is an **AI-assisted stock research dashboard** with **optional
manual portfolio tracking added later**. It exists to support two everyday jobs:

1. **See how my current holdings are doing** — once manual portfolio tracking is
   built. Until then, the portfolio surface stays hidden.
2. **Find and research stocks I may want to buy** — analyze a ticker, score it
   with the existing transparent rule-based engine, save reports, and group
   candidates into watchlists.

The backend (Python + FastAPI + SQLite) remains the single source of truth for
all data fetching, signal computation, scoring, report assembly, and
persistence. The frontend is a **display and input layer only** — it renders API
responses and submits user actions. This boundary does not change in any UI
phase. See `docs/frontend_plan.md` §8 (Data Ownership Rules) for the binding
contract.

---

## 2. What the App Is / Is Not

### It is

- A personal, single-user research and decision-support dashboard.
- A browser front door to the existing analysis engine and saved data.
- A place to research tickers, read scored reports, and curate watchlists.
- Eventually: a manual portfolio tracker (holdings entered by hand) and a richer
  charts/visual surface.

### It is not (permanent guardrails)

- Not a live or paper trading system.
- No broker APIs (Alpaca, Robinhood, IBKR, or any brokerage).
- No order execution of any kind.
- No alerts, scheduled scans, or background jobs.
- No automatic position management, allocation, or rebalancing logic.
- No margin or options logic.
- No ML / LLM scoring in the frontend.
- No mock trading simulation in the frontend.
- No duplication of backend scoring, signal, category, threshold, or weight
  logic in React.
- No changes to scoring rules, signal calculations, or rating thresholds.

If a feature would require the frontend to recalculate a rating or replicate
analysis logic, that feature belongs in the backend first.

---

## 3. Visual Direction

**Dark finance dashboard**, inspired by modern stock/market dashboards
(disciplined dark luxury, not neon "crypto" maximalism).

Principles:

- **Dark surface system with layering.** A deep base background, slightly raised
  surface cards, and a third elevation for emphasized panels. Depth comes from
  surface contrast and subtle borders/shadows, not heavy gradients.
- **Clear hierarchy through scale contrast.** Big numbers (price, score) read
  first; labels and metadata recede.
- **Semantic color, not decorative color.** Green/red reserved for
  gain/loss/direction and rating sentiment; a single accent (cool blue/teal) for
  interactive elements. Avoid coloring things just to fill space.
- **Designed interaction states.** Every clickable element gets intentional
  hover/focus/active states, including keyboard focus rings.
- **Restraint over decoration.** No fake financial sparkle. Charts and data viz
  are treated as part of the design system, added deliberately in later phases.
- **Accessibility baseline.** Maintain adequate contrast on dark surfaces;
  respect `prefers-reduced-motion`; keep semantic HTML (`header`, `nav`, `main`,
  `section`).

The current frontend uses a light theme with CSS custom properties already
defined in `frontend/src/styles.css` (`--color-*`, `--radius`, `--shadow`). The
redesign extends this token system into a dark palette rather than introducing a
new styling stack. Stack stays **React + Vite + TypeScript, plain CSS, native
fetch, React Router** per `CLAUDE.md`.

---

## 4. Navigation Model

**Permanent left sidebar on desktop.** The current top navbar (`App.tsx`) moves
to a persistent vertical sidebar as the primary navigation.

- Fixed left sidebar on desktop: product name/logo at top, primary nav links,
  backend/data status indicator near the bottom.
- Main content area to the right with a consistent page shell (page title,
  optional actions, content).
- On narrow/mobile widths the sidebar collapses to a top bar or drawer (exact
  collapse behavior decided in the App Shell phase).

### Nav items

| Item | Route | Status |
|------|-------|--------|
| Dashboard | `/` | Existing — redesigned |
| Analyze | `/analyze` | Existing |
| Watchlists | `/watchlists` | Existing |
| Saved Reports | `/reports` | Existing |
| Report Detail | `/reports/:id` | Existing (not a top-level nav item) |
| Portfolio | `/portfolio` | **Hidden** until manual holdings are built (Phase 7+) |

No existing route is removed or renamed during the shell/dashboard redesign.

---

## 5. Target Page Structure

| Page | Route | Purpose | Data source |
|------|-------|---------|-------------|
| Dashboard | `/` | At-a-glance overview + entry points | Existing read endpoints (see §6) |
| Analyze | `/analyze` | Analyze a ticker; show report; later, daily chart | `POST /api/analyze`, `POST /api/reports/analyze` |
| Watchlists | `/watchlists` | Watchlist CRUD + on-demand analysis; later cards + sparklines | `/api/watchlists*` |
| Saved Reports | `/reports` | Browse saved report snapshots | `GET /api/reports/history` |
| Report Detail | `/reports/:id` | Full saved report | `GET /api/reports/{id}` |
| Portfolio | `/portfolio` | Manual holdings + portfolio dashboard | **Future** — requires new backend (Phase 7–8) |

---

## 6. Dashboard Information Architecture

The redesigned Dashboard is the home surface. Each block is listed with its data
status so we never ship unlabeled fake financial data.

| Block | Description | Data status |
|-------|-------------|-------------|
| **Market overview strip** | A row of major indices/benchmarks. | **Demo/Coming Soon** until a real market-data endpoint exists. Must be clearly labeled. |
| **Portfolio summary card** | Total value, day change, holdings count. | **Coming Soon** card until manual portfolio (Phase 7–8). Clearly labeled placeholder. |
| **Watchlist summary** | Named watchlists with ticker counts; quick links. | **Real** — `GET /api/watchlists`. |
| **Recent saved reports** | Last 5–10 saved reports (ticker, category, score, date). | **Real** — `GET /api/reports/history?limit=10`. |
| **Top candidates** | Highest-scoring tickers from the latest watchlist analysis. | **Real but on-demand** — `POST /api/watchlists/{id}/analyze`. Results are not persisted today, so this is empty/placeholder until snapshots exist (Phase 6) or until the user runs an analysis in-session. |
| **Strong Buy / Buy Candidate counts** | Counts by rating category from recent reports/analysis. | **Real** — derived from already-returned API fields (`final_category`). Frontend only counts/groups values the backend produced; it never recomputes the category. |
| **API/data status** | Backend connectivity + data freshness. | **Real** — `GET /api/health`. |
| **Analyze/search ticker box** | Inline ticker input that routes to Analyze. | **Real** — entry point to existing analyze flow. |

**Important boundary:** "Strong Buy / Buy Candidate counts" and "Top candidates"
are *grouping and counting of values the backend already returned*
(`final_category`, `score`). This is display formatting, not analysis. The
frontend must never derive a category from a score or re-rank by recomputing a
rating.

---

## 7. Component / Layout Plan

Target structure under `frontend/src/`, extending the existing layout (organize
by surface area, small focused files):

```
src/
  components/
    layout/
      AppShell.tsx        # sidebar + main content frame
      Sidebar.tsx         # nav links + status indicator
      PageHeader.tsx      # consistent page title/actions row
    ui/
      Card.tsx            # raised surface card primitive
      StatTile.tsx        # big-number + label tile (price, score, counts)
      Badge.tsx           # category/sentiment badge (reuses existing badge styles)
      ComingSoon.tsx      # labeled Demo / Placeholder / Coming Soon wrapper
    dashboard/
      MarketOverviewStrip.tsx
      PortfolioSummaryCard.tsx
      WatchlistSummary.tsx
      RecentReports.tsx
      TopCandidates.tsx
      CategoryCounts.tsx
      DataStatus.tsx
      QuickAnalyzeBox.tsx
    StockReportView.tsx   # existing — reused as-is
    LoadingState.tsx      # existing
    ErrorMessage.tsx      # existing
  styles/
    tokens.css            # dark palette + spacing/typography tokens
    (component CSS co-located or grouped as the redesign lands)
```

- Existing presentational components (`StockReportView`, `LoadingState`,
  `ErrorMessage`) are retained and restyled via tokens, not rewritten.
- The existing `frontend/src/lib/` helpers (`format.ts`, `errors.ts`) stay the
  home for shared pure display/error logic.
- The API client layer (`frontend/src/api/*`) is unchanged by the UI redesign —
  same typed functions, same endpoints.

---

## 8. Real Data vs Placeholder/Demo Data Rules

- **Real data is preferred everywhere it already exists** via the current API.
- **Placeholder/demo data is allowed only when clearly labeled** as one of:
  **Demo**, **Placeholder**, or **Coming Soon**.
- A reusable `ComingSoon` (or equivalently labeled) wrapper marks every
  not-yet-real block so it can never be mistaken for live financial data.
- **No unlabeled fake financial numbers — ever.** A blank/empty state is always
  preferable to invented data.
- When a real endpoint returns empty (e.g. no saved reports yet), show a
  meaningful empty state, not filler.

---

## 9. Chart / Data Roadmap

Charts are added deliberately, simplest and most useful first:

1. **Daily historical ticker chart (first). — DONE (Phase 4).** On the Analyze
   page, using the existing market-data layer (`app/data/market_data.py`)
   surfaced through a read endpoint (`GET /api/market-data/{ticker}/history`).
   Static, point-in-time daily close history rendered with **Lightweight
   Charts**. Daily history only — **not** real-time/intraday (that remains
   item 4 / Phase 9).
2. **Watchlist mini sparklines (second).** Small daily trend lines on watchlist
   cards.
3. **Watchlist score trend (after snapshots exist).** Requires saved
   watchlist-analysis snapshots (Phase 6) before there is any history to trend.
4. **Intraday / real-time (later).** Gated behind a dedicated phase due to
   provider, cost, rate-limit, caching, and freshness concerns.

Chart library selection happened in Phase 4: **Lightweight Charts** is the chosen
library. No other charting dependency should be added without a new scoped task.

---

## 10. Manual Portfolio Tracking Roadmap

Manual-only, no broker linking, no automation.

- **Holdings are entered by hand:** ticker, shares, average cost, optional
  purchase date, optional notes.
- The portfolio surface stays **hidden** (no `/portfolio` nav item, no route)
  until the backend holdings model and endpoints are actually built.
- Portfolio value and gain/loss use **current prices fetched through the backend
  data layer** — never a broker feed.
- **Explicitly excluded forever:** broker linking, order execution, automated
  trading, allocation/rebalancing recommendations, margin, options.

A "Portfolio summary" / "Coming Soon" card may appear on the Dashboard before the
feature exists, **only if clearly labeled** per §8.

---

## 11. Live / Real-Time Data Goal (documented, later phase)

Real-time/intraday prices are a **desired eventual capability**, deliberately
deferred. Before any implementation, evaluate and document:

- **Provider** — yfinance is point-in-time/delayed; intraday/streaming may need a
  different provider with explicit terms.
- **Polling vs websocket** — refresh approach and its complexity.
- **Rate limits** — request budgets and backoff.
- **Caching** — server-side caching to avoid hammering providers and to control
  cost.
- **Cost** — paid data tiers vs free/delayed.
- **Freshness indicators** — the UI must show data age/staleness so delayed data
  is never presented as live.

This is Phase 9 and is not started.

---

## 12. Phased Implementation Plan

Each phase is independently shippable. No phase starts until the previous one is
stable. Phases beyond this doc are UI-direction phases layered on top of the
existing completed backend phases (see `CLAUDE.md` Phase Status).

| Phase | Name | Scope | Backend dependency |
|-------|------|-------|--------------------|
| **1** | **UI Vision Doc** | *This milestone.* Documentation only. | None |
| **2** | **App Shell Redesign** | Dark finance theme foundation (token palette), left sidebar, consistent page layout. Keep all existing routes working. No new backend features. No charts (unless trivially already present). No portfolio page. | None |
| **3** | **Dashboard Redesign** | Rebuild Dashboard from existing real backend data: watchlist summary, recent saved reports, category counts, analyze entry point, API/data status. Clearly labeled Coming Soon for portfolio/market blocks. No unlabeled fake financial data. | Existing read endpoints |
| **4** | **Chart Foundation** | Choose a chart library (planned, not assumed). Add a **daily historical ticker chart** to the Analyze page first, via the existing market-data layer. No real-time/intraday. | New read endpoint to expose price history (thin wrapper over existing data layer) |
| **5** | **Watchlist Visual Upgrade** | Watchlist cards + mini sparklines; improved on-demand analysis presentation. | Existing `/api/watchlists*` (+ price-history endpoint from Phase 4) |
| **6** | **Saved Watchlist Analysis Snapshots** | Persist on-demand watchlist scan history to enable score-trend views later. | New backend persistence (scoped separately) |
| **7** | **Manual Portfolio Tracking** | Manually entered holdings (ticker, shares, avg cost, optional date/notes). No broker linking, no automation, no allocation/rebalancing. | New backend holdings model + endpoints |
| **8** | **Portfolio Dashboard** | Portfolio value, holdings table, gain/loss, allocation visualization — all from manual holdings + backend-fetched prices. | Phase 7 backend |
| **9** | **Intraday / Real-Time Data** | Evaluate provider, polling/websocket, rate limits, caching, cost, freshness indicators before implementing. | New data provider + caching layer |

Phases 6–9 each require their own explicitly scoped backend task before any
implementation; they are named here for direction only.

---

## 13. Guardrails (explicit, every phase)

- No broker APIs, no live trading, no paper trading, no order execution.
- No alerts, scheduled scans, or background jobs.
- No automatic position management, allocation, or rebalancing.
- No margin or options logic.
- No ML; no mock simulation.
- No frontend duplication of backend scoring/analysis/category/weight/threshold
  logic.
- No changes to scoring rules, signal calculations, or rating thresholds.
- Frontend stays display + input only; backend remains the single source of
  truth.
- Placeholder/demo data only when clearly labeled (Demo / Placeholder / Coming
  Soon).
- CLI must keep working; UI changes never touch the analysis pipeline.

---

## 14. First Implementation Milestone Recommendation

**Recommended next milestone: Phase 2 — App Shell Redesign.**

Why this first:

- It is purely presentational and low-risk: a dark token palette + left sidebar +
  consistent page shell, with all existing routes and behavior preserved.
- It establishes the visual foundation (tokens, layout primitives) that every
  later phase builds on, so the Dashboard redesign (Phase 3) and charts (Phase 4)
  land into a consistent frame instead of being restyled twice.
- It needs **no backend changes, no new dependencies, and no API changes** — it
  only restyles and reorganizes the existing React layer.

Suggested scope for that future task:

> **"Phase 2 — App Shell Redesign"**
> Introduce a dark finance token palette in a `styles/tokens.css`, replace the
> top navbar with a permanent left sidebar (`AppShell` + `Sidebar`), add a
> consistent `PageHeader`, and restyle existing pages to the new shell. Keep all
> current routes, data flows, and the API client unchanged. No charts, no
> portfolio page, no backend changes.

Do not begin implementation until that milestone is explicitly opened.
