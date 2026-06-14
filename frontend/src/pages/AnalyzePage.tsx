import { useState } from 'react'
import { Link } from 'react-router-dom'
import { analyzeAndSave, analyzeOnly } from '../api/analysisApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { StockReportView } from '../components/StockReportView'
import { getErrorMessage } from '../lib/errors'
import type { StockReport } from '../types/report'

export function AnalyzePage() {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<StockReport | null>(null)
  const [savedId, setSavedId] = useState<number | null>(null)

  function clearResult() {
    setError(null)
    setReport(null)
    setSavedId(null)
  }

  async function handleAnalyzeOnly() {
    const t = ticker.trim().toUpperCase()
    if (!t) {
      setError('Please enter a ticker symbol.')
      return
    }
    setLoading(true)
    clearResult()
    try {
      const result = await analyzeOnly(t)
      setReport(result)
    } catch (err) {
      setError(getErrorMessage(err, 'Analysis failed — please try again.'))
    } finally {
      setLoading(false)
    }
  }

  async function handleAnalyzeAndSave() {
    const t = ticker.trim().toUpperCase()
    if (!t) {
      setError('Please enter a ticker symbol.')
      return
    }
    setLoading(true)
    clearResult()
    try {
      const result = await analyzeAndSave(t)
      setReport(result.report)
      setSavedId(result.id)
    } catch (err) {
      setError(getErrorMessage(err, 'Analysis failed — please try again.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <PageHeader title="Analyze a Ticker" />

      <div className="analyze-form">
        <input
          type="text"
          className="ticker-input"
          placeholder="e.g. AAPL"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleAnalyzeOnly()
          }}
          disabled={loading}
          aria-label="Ticker symbol"
          autoFocus
        />
        <div className="analyze-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAnalyzeOnly}
            disabled={loading}
          >
            Analyze only
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleAnalyzeAndSave}
            disabled={loading}
          >
            Analyze and save
          </button>
        </div>
        <p className="action-hint">
          <em>Analyze only</em> returns results without saving.{' '}
          <em>Analyze and save</em> persists the report to history.
        </p>
      </div>

      {loading && (
        <LoadingState message="Analyzing — this may take a few seconds…" />
      )}
      {error && <ErrorMessage message={error} />}
      {report && (
        <StockReportView report={report} savedId={savedId ?? undefined} />
      )}

      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>
    </div>
  )
}
