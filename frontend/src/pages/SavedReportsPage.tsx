import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSavedReports } from '../api/reportsApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import type { SavedReportSummary } from '../types/report'

export function SavedReportsPage() {
  const [reports, setReports] = useState<SavedReportSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load on mount. State updates happen only in async callbacks (not
  // synchronously in the effect body) to avoid cascading renders.
  useEffect(() => {
    let active = true
    listSavedReports()
      .then((data) => {
        if (active) {
          setReports(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err, 'Failed to load saved reports.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="page">
      <h1>Saved Reports</h1>
      <p className="subtitle">
        Analysis snapshots you saved earlier. Read-only history — open one for
        the full report.
      </p>

      {loading && <LoadingState message="Loading saved reports…" />}
      {error && <ErrorMessage message={error} />}

      {!loading && !error && reports.length === 0 && (
        <p className="empty-state">
          No saved reports yet. Use{' '}
          <Link to="/analyze">Analyze</Link> and choose “Analyze and save” to
          create one.
        </p>
      )}

      {reports.length > 0 && (
        <ul className="report-list">
          {reports.map((report) => (
            <li key={report.id}>
              <Link to={`/reports/${report.id}`} className="report-card">
                <div className="report-card-main">
                  <span className="report-card-ticker">{report.ticker}</span>
                  {report.company_name && (
                    <span className="report-card-company">
                      {report.company_name}
                    </span>
                  )}
                </div>
                <div className="report-card-verdict">
                  <span className="category-badge">{report.category}</span>
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

      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>
    </div>
  )
}
