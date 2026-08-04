import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { checkHealth } from '../api/analysisApi'
import { listSavedReports } from '../api/reportsApi'
import { listWatchlists } from '../api/watchlistApi'
import { ComingSoonCard } from '../components/dashboard/ComingSoonCard'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PortfolioPanel } from '../components/portfolio/PortfolioPanel'
import { PageHeader } from '../components/layout/PageHeader'
import { countByCategory, sumBy } from '../lib/dashboard'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import { sortByScoreDesc } from '../lib/sort'
import type { SavedReportSummary } from '../types/report'
import type { WatchlistSummary } from '../types/watchlist'

type HealthStatus = 'checking' | 'ok' | 'unavailable'

/** Major indices we'd like to show once a market-data source is connected. */
const PLACEHOLDER_INDICES = ['S&P 500', 'Nasdaq', 'Dow Jones', 'Russell 2000']

const RECENT_REPORTS_LIMIT = 5
const TOP_CANDIDATES_LIMIT = 3

export function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus>('checking')

  const [watchlists, setWatchlists] = useState<WatchlistSummary[]>([])
  const [watchlistsLoading, setWatchlistsLoading] = useState(true)
  const [watchlistsError, setWatchlistsError] = useState<string | null>(null)

  const [reports, setReports] = useState<SavedReportSummary[]>([])
  const [reportsLoading, setReportsLoading] = useState(true)
  const [reportsError, setReportsError] = useState<string | null>(null)

  // Each section loads independently so one failure degrades only its own card.
  useEffect(() => {
    let active = true

    checkHealth()
      .then(() => {
        if (active) setHealth('ok')
      })
      .catch(() => {
        if (active) setHealth('unavailable')
      })

    listWatchlists()
      .then((data) => {
        if (active) {
          setWatchlists(data)
          setWatchlistsError(null)
        }
      })
      .catch((err: unknown) => {
        if (active)
          setWatchlistsError(getErrorMessage(err, 'Failed to load watchlists.'))
      })
      .finally(() => {
        if (active) setWatchlistsLoading(false)
      })

    listSavedReports()
      .then((data) => {
        if (active) {
          setReports(data)
          setReportsError(null)
        }
      })
      .catch((err: unknown) => {
        if (active)
          setReportsError(getErrorMessage(err, 'Failed to load saved reports.'))
      })
      .finally(() => {
        if (active) setReportsLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const totalTickers = sumBy(watchlists, (wl) => wl.ticker_count)
  const recentReports = reports.slice(0, RECENT_REPORTS_LIMIT)
  const topCandidates = sortByScoreDesc(reports).slice(0, TOP_CANDIDATES_LIMIT)
  const categoryCounts = countByCategory(reports)

  return (
    <div className="page">
      <PageHeader
        title="Research Dashboard"
        subtitle="Your stock research workspace — analyze tickers, curate watchlists, and review saved reports."
      />

      <div className="dashboard-actions">
        <Link to="/analyze" className="btn btn-primary">
          Analyze a ticker →
        </Link>
        <Link to="/watchlists" className="btn btn-secondary">
          Manage watchlists
        </Link>
        <Link to="/reports" className="btn btn-secondary">
          View saved reports
        </Link>
      </div>

      <div className="disclaimer">
        <strong>Research support only.</strong> This tool does not provide
        financial advice and is not an automated trading system. All output
        should be treated as a starting point for your own due diligence — not as
        a recommendation to buy, sell, or hold any security.
      </div>

      {/* ── Personal portfolio (real, manual holdings) ─────────────── */}
      <PortfolioPanel />

      <div className="dashboard-grid">
        {/* ── Market overview (not connected yet) ──────────────────── */}
        <ComingSoonCard
          title="Market Overview"
          description="Live index data isn't connected yet. Real-time / delayed market quotes are a later phase."
          wide
        >
          <ul className="market-strip" aria-hidden="true">
            {PLACEHOLDER_INDICES.map((name) => (
              <li key={name} className="market-index">
                <span className="market-index-name">{name}</span>
                <span className="market-index-value">—</span>
              </li>
            ))}
          </ul>
        </ComingSoonCard>

        {/* ── Watchlist summary (real) ─────────────────────────────── */}
        <section className="dashboard-card" aria-label="Watchlist summary">
          <div className="dashboard-card-head">
            <h2 className="dashboard-card-title">Watchlists</h2>
            <Link to="/watchlists" className="dashboard-card-link">
              Manage →
            </Link>
          </div>
          {watchlistsLoading && <LoadingState message="Loading watchlists…" />}
          {watchlistsError && <ErrorMessage message={watchlistsError} />}
          {!watchlistsLoading && !watchlistsError && (
            <>
              {watchlists.length === 0 ? (
                <p className="dashboard-card-note">
                  No watchlists yet.{' '}
                  <Link to="/watchlists">Create one</Link> to group tickers.
                </p>
              ) : (
                <div className="metric-row">
                  <div className="metric">
                    <span className="metric-value">{watchlists.length}</span>
                    <span className="metric-label">
                      {watchlists.length === 1 ? 'watchlist' : 'watchlists'}
                    </span>
                  </div>
                  <div className="metric">
                    <span className="metric-value">{totalTickers}</span>
                    <span className="metric-label">
                      {totalTickers === 1 ? 'ticker' : 'tickers'}
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        {/* ── Rating breakdown / top candidates (real) ─────────────── */}
        <section className="dashboard-card" aria-label="Saved report ratings">
          <div className="dashboard-card-head">
            <h2 className="dashboard-card-title">Saved Report Ratings</h2>
          </div>
          {reportsLoading && <LoadingState message="Loading ratings…" />}
          {reportsError && <ErrorMessage message={reportsError} />}
          {!reportsLoading && !reportsError && (
            <>
              {reports.length === 0 ? (
                <p className="dashboard-card-note">
                  No saved reports yet — ratings appear here once you save an
                  analysis.
                </p>
              ) : (
                <>
                  <ul className="category-count-list">
                    {categoryCounts.map((c) => (
                      <li key={c.category} className="category-count-row">
                        <span className="category-badge">{c.category}</span>
                        <span className="category-count">{c.count}</span>
                      </li>
                    ))}
                  </ul>
                  {topCandidates.length > 0 && (
                    <p className="dashboard-card-note">
                      Top by score:{' '}
                      {topCandidates.map((r, i) => (
                        <span key={r.id}>
                          {i > 0 && ', '}
                          <Link to={`/reports/${r.id}`}>{r.ticker}</Link> (
                          {r.score.toFixed(1)})
                        </span>
                      ))}
                    </p>
                  )}
                </>
              )}
            </>
          )}
        </section>

        {/* ── Recent saved reports (real) ──────────────────────────── */}
        <section
          className="dashboard-card dashboard-card--wide"
          aria-label="Recent saved reports"
        >
          <div className="dashboard-card-head">
            <h2 className="dashboard-card-title">Recent Reports</h2>
            <Link to="/reports" className="dashboard-card-link">
              View all →
            </Link>
          </div>
          {reportsLoading && <LoadingState message="Loading saved reports…" />}
          {reportsError && <ErrorMessage message={reportsError} />}
          {!reportsLoading && !reportsError && (
            <>
              {recentReports.length === 0 ? (
                <p className="dashboard-card-note">
                  No saved reports yet. Use{' '}
                  <Link to="/analyze">Analyze</Link> and choose “Analyze and
                  save” to create one.
                </p>
              ) : (
                <ul className="report-list">
                  {recentReports.map((report) => (
                    <li key={report.id}>
                      <Link
                        to={`/reports/${report.id}`}
                        className="report-card"
                      >
                        <div className="report-card-main">
                          <span className="report-card-ticker">
                            {report.ticker}
                          </span>
                          {report.company_name && (
                            <span className="report-card-company">
                              {report.company_name}
                            </span>
                          )}
                        </div>
                        <div className="report-card-verdict">
                          <span className="category-badge">
                            {report.category}
                          </span>
                          <span className="report-card-score">
                            Score {report.score.toFixed(1)}
                          </span>
                          <span className="report-card-confidence">
                            {report.confidence}
                          </span>
                        </div>
                        <span className="report-card-date">
                          {formatTimestamp(report.created_at)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>

        {/* ── Source status (informational, not a sidebar duplicate) ─ */}
        <section className="dashboard-card" aria-label="Source status">
          <div className="dashboard-card-head">
            <h2 className="dashboard-card-title">Source Status</h2>
          </div>
          <ul className="source-status-list">
            <li className="source-status-row">
              <span className="source-status-label">Backend API</span>
              <span className={`source-status-value source-status-${health}`}>
                {health === 'checking' && 'Checking…'}
                {health === 'ok' && 'Connected'}
                {health === 'unavailable' && 'Unavailable'}
              </span>
            </li>
            <li className="source-status-row">
              <span className="source-status-label">Market data</span>
              <span className="source-status-value">yfinance · end-of-day</span>
            </li>
            <li className="source-status-row">
              <span className="source-status-label">Intraday / real-time</span>
              <span className="source-status-value source-status-muted">
                Later phase
              </span>
            </li>
          </ul>
          {health === 'unavailable' && (
            <p className="dashboard-card-note">
              Start the FastAPI server:{' '}
              <code>uvicorn app.api.main:app --reload</code>
            </p>
          )}
        </section>
      </div>
    </div>
  )
}
