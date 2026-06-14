import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getSavedReport } from '../api/reportsApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { StockReportView } from '../components/StockReportView'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import type { SavedReportDetail } from '../types/report'

function BackLink() {
  return (
    <p className="detail-back">
      <Link to="/reports">← Back to Saved Reports</Link>
    </p>
  )
}

/** Inner view, mounted per report id so its load effect runs exactly once. */
function ReportDetail({ reportId }: { reportId: number }) {
  const [detail, setDetail] = useState<SavedReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getSavedReport(reportId)
      .then((data) => {
        if (active) {
          setDetail(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err, 'Failed to load report.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [reportId])

  return (
    <div className="page">
      <BackLink />
      <PageHeader title="Saved Report" />
      {loading && <LoadingState message="Loading report…" />}
      {error && <ErrorMessage message={error} />}
      {detail && (
        <>
          <p className="saved-notice">
            Report #{detail.id} · saved {formatTimestamp(detail.created_at)}
          </p>
          <StockReportView report={detail.report} />
        </>
      )}
    </div>
  )
}

export function ReportDetailPage() {
  const { id } = useParams<{ id: string }>()
  const reportId = Number(id)

  if (!Number.isInteger(reportId) || reportId <= 0) {
    return (
      <div className="page">
        <BackLink />
        <ErrorMessage message="Invalid report ID." />
      </div>
    )
  }

  // key remounts the view when navigating between report ids.
  return <ReportDetail key={reportId} reportId={reportId} />
}
