import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getWatchlistSnapshot } from '../api/watchlistApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { AnalysisResultCard } from '../components/watchlist/AnalysisResultCard'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import { sortByScoreDesc } from '../lib/sort'
import type { WatchlistSnapshotDetail } from '../types/watchlist'

function BackLink() {
  return (
    <p className="detail-back">
      <Link to="/watchlists">← Back to Watchlists</Link>
    </p>
  )
}

/** Inner view, mounted per snapshot id so its load effect runs exactly once. */
function SnapshotDetail({ snapshotId }: { snapshotId: number }) {
  const [snapshot, setSnapshot] = useState<WatchlistSnapshotDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getWatchlistSnapshot(snapshotId)
      .then((data) => {
        if (active) {
          setSnapshot(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err, 'Failed to load snapshot.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [snapshotId])

  const hasResults = snapshot != null && snapshot.results.length > 0
  const hasErrors = snapshot != null && snapshot.errors.length > 0

  return (
    <div className="page">
      <BackLink />
      <PageHeader
        title={snapshot ? snapshot.watchlist_name : 'Snapshot'}
        subtitle="Historical record of a manually triggered watchlist analysis."
      />

      {loading && <LoadingState message="Loading snapshot…" />}
      {error && <ErrorMessage message={error} />}

      {snapshot && (
        <>
          <p className="snapshot-historical-note">
            Saved snapshot from {formatTimestamp(snapshot.analyzed_at)}. This page
            shows historical data captured at that time — it does not refresh and
            does not show current prices.
          </p>

          <div className="snapshot-summary">
            <div className="snapshot-stat">
              <span className="snapshot-stat-value">
                {snapshot.total_tickers}
              </span>
              <span className="snapshot-stat-label">Total tickers</span>
            </div>
            <div className="snapshot-stat">
              <span className="snapshot-stat-value snapshot-stat-ok">
                {snapshot.success_count}
              </span>
              <span className="snapshot-stat-label">Successful</span>
            </div>
            <div className="snapshot-stat">
              <span className="snapshot-stat-value snapshot-stat-fail">
                {snapshot.failure_count}
              </span>
              <span className="snapshot-stat-label">Failed</span>
            </div>
            <div className="snapshot-stat">
              <span className="snapshot-stat-value snapshot-stat-time">
                {formatTimestamp(snapshot.analyzed_at)}
              </span>
              <span className="snapshot-stat-label">Analyzed</span>
            </div>
          </div>

          {hasResults && (
            <section className="snapshot-section" aria-label="Successful results">
              <h2 className="section-title">Results</h2>
              <ul className="watchlist-analysis-grid">
                {sortByScoreDesc(snapshot.results).map((result, i) => (
                  <AnalysisResultCard
                    key={result.ticker}
                    result={result}
                    rank={i + 1}
                  />
                ))}
              </ul>
            </section>
          )}

          {hasErrors && (
            <div className="snapshot-section analysis-errors">
              <h2 className="analysis-errors-title">
                Failed tickers ({snapshot.errors.length})
              </h2>
              <ul className="analysis-error-list">
                {snapshot.errors.map((e) => (
                  <li key={e.ticker} className="analysis-error-item">
                    <span className="analysis-error-ticker">{e.ticker}</span>
                    <span className="analysis-error-msg">{e.error}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!hasResults && !hasErrors && (
            <p className="empty-state">This snapshot has no saved results.</p>
          )}
        </>
      )}
    </div>
  )
}

export function WatchlistSnapshotDetailPage() {
  const { snapshotId } = useParams<{ snapshotId: string }>()
  const id = Number(snapshotId)

  if (!Number.isInteger(id) || id <= 0) {
    return (
      <div className="page">
        <BackLink />
        <ErrorMessage message="Invalid snapshot ID." />
      </div>
    )
  }

  // key remounts the view when navigating between snapshot ids.
  return <SnapshotDetail key={id} snapshotId={id} />
}
