import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { analyzeAndSave, analyzeOnly } from '../api/analysisApi'
import { getPriceHistory } from '../api/marketDataApi'
import { StockPriceChart } from '../components/charts/StockPriceChart'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { StockReportView } from '../components/StockReportView'
import { getErrorMessage } from '../lib/errors'
import type { PriceHistoryResponse } from '../types/marketData'
import type { StockReport } from '../types/report'

export function AnalyzePage() {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<StockReport | null>(null)
  const [savedId, setSavedId] = useState<number | null>(null)

  // The ticker whose analysis succeeded — drives the price-history fetch.
  const [analyzedTicker, setAnalyzedTicker] = useState<string | null>(null)
  const [history, setHistory] = useState<PriceHistoryResponse | null>(null)
  const [chartLoading, setChartLoading] = useState(false)
  const [chartError, setChartError] = useState<string | null>(null)

  // Load price history whenever a new ticker is successfully analyzed. This is
  // independent of the analysis report: a chart failure never hides the report.
  // State is only updated inside async callbacks (reset happens in the handlers)
  // so the effect never triggers a synchronous cascade on mount.
  useEffect(() => {
    if (!analyzedTicker) return
    let active = true
    getPriceHistory(analyzedTicker)
      .then((data) => {
        if (active) setHistory(data)
      })
      .catch((err: unknown) => {
        if (active)
          setChartError(getErrorMessage(err, 'Could not load price history.'))
      })
      .finally(() => {
        if (active) setChartLoading(false)
      })
    return () => {
      active = false
    }
  }, [analyzedTicker])

  function clearResult() {
    setError(null)
    setReport(null)
    setSavedId(null)
    setAnalyzedTicker(null)
    setHistory(null)
    setChartError(null)
    setChartLoading(false)
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
      setChartLoading(true)
      setAnalyzedTicker(t)
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
      setChartLoading(true)
      setAnalyzedTicker(t)
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

      {report && (
        <section className="price-history-card" aria-label="Price history">
          <div className="price-history-head">
            <h2 className="section-title">Price History</h2>
            <span className="price-history-meta">Daily close · last 1 year</span>
          </div>
          {chartLoading && <LoadingState message="Loading price history…" />}
          {chartError && <ErrorMessage message={chartError} />}
          {!chartLoading && !chartError && history && (
            <>
              {history.prices.length === 0 ? (
                <p className="empty-state">
                  No price history available for {history.ticker}.
                </p>
              ) : (
                <StockPriceChart prices={history.prices} />
              )}
            </>
          )}
        </section>
      )}

      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>
    </div>
  )
}
