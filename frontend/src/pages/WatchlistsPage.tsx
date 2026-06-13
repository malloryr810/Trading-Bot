import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  addTickerToWatchlist,
  analyzeWatchlist,
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  removeTickerFromWatchlist,
  updateWatchlist,
} from '../api/watchlistApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import { sortByScoreDesc } from '../lib/sort'
import type {
  WatchlistAnalysisResponse,
  WatchlistDetail,
  WatchlistSummary,
} from '../types/watchlist'

export function WatchlistsPage() {
  const [watchlists, setWatchlists] = useState<WatchlistSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selected, setSelected] = useState<WatchlistDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [creating, setCreating] = useState(false)

  const [tickerInput, setTickerInput] = useState('')
  const [busy, setBusy] = useState(false)

  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // On-demand analysis result for the selected watchlist (not saved server-side).
  const [analysis, setAnalysis] = useState<WatchlistAnalysisResponse | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  async function refreshList(): Promise<WatchlistSummary[]> {
    setListLoading(true)
    setListError(null)
    try {
      const data = await listWatchlists()
      setWatchlists(data)
      return data
    } catch (err) {
      setListError(getErrorMessage(err, 'Failed to load watchlists.'))
      return []
    } finally {
      setListLoading(false)
    }
  }

  // Initial load. State is updated only in async callbacks (not synchronously
  // in the effect body) so we don't trigger cascading renders on mount.
  useEffect(() => {
    let active = true
    listWatchlists()
      .then((data) => {
        if (active) {
          setWatchlists(data)
          setListError(null)
        }
      })
      .catch((err: unknown) => {
        if (active) setListError(getErrorMessage(err, 'Failed to load watchlists.'))
      })
      .finally(() => {
        if (active) setListLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  function applySelected(detail: WatchlistDetail) {
    setSelected(detail)
    setEditName(detail.name)
    setEditDescription(detail.description ?? '')
    // Any selection change or ticker mutation invalidates a prior analysis.
    setAnalysis(null)
    setAnalysisError(null)
  }

  async function handleSelect(id: number) {
    setDetailError(null)
    try {
      applySelected(await getWatchlist(id))
    } catch (err) {
      setSelected(null)
      setDetailError(getErrorMessage(err, 'Failed to load watchlist.'))
    }
  }

  async function handleCreate() {
    const name = newName.trim()
    if (!name) {
      setListError('Please enter a watchlist name.')
      return
    }
    setCreating(true)
    setListError(null)
    try {
      const description = newDescription.trim()
      const created = await createWatchlist({
        name,
        description: description || null,
      })
      setNewName('')
      setNewDescription('')
      await refreshList()
      applySelected(created)
    } catch (err) {
      setListError(getErrorMessage(err, 'Failed to create watchlist.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleAddTicker() {
    if (!selected) return
    const ticker = tickerInput.trim().toUpperCase()
    if (!ticker) {
      setDetailError('Please enter a ticker symbol.')
      return
    }
    setBusy(true)
    setDetailError(null)
    try {
      applySelected(await addTickerToWatchlist(selected.id, { ticker }))
      setTickerInput('')
      await refreshList()
    } catch (err) {
      setDetailError(getErrorMessage(err, 'Failed to add ticker.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleRemoveTicker(ticker: string) {
    if (!selected) return
    setBusy(true)
    setDetailError(null)
    try {
      applySelected(await removeTickerFromWatchlist(selected.id, ticker))
      await refreshList()
    } catch (err) {
      setDetailError(getErrorMessage(err, 'Failed to remove ticker.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveEdit() {
    if (!selected) return
    const name = editName.trim()
    if (!name) {
      setDetailError('Watchlist name cannot be blank.')
      return
    }
    setBusy(true)
    setDetailError(null)
    try {
      applySelected(
        await updateWatchlist(selected.id, {
          name,
          description: editDescription.trim(),
        }),
      )
      await refreshList()
    } catch (err) {
      setDetailError(getErrorMessage(err, 'Failed to update watchlist.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!selected) return
    setBusy(true)
    setDetailError(null)
    try {
      await deleteWatchlist(selected.id)
      setSelected(null)
      setAnalysis(null)
      setAnalysisError(null)
      await refreshList()
    } catch (err) {
      setDetailError(getErrorMessage(err, 'Failed to delete watchlist.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleAnalyze() {
    if (!selected || selected.tickers.length === 0) return
    setAnalyzing(true)
    setAnalysisError(null)
    setAnalysis(null)
    try {
      setAnalysis(await analyzeWatchlist(selected.id))
    } catch (err) {
      setAnalysisError(getErrorMessage(err, 'Failed to analyze watchlist.'))
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="page">
      <h1>Watchlists</h1>
      <p className="subtitle">
        Create named lists of tickers to research later. Storage only — no
        analysis is run from here yet.
      </p>

      <div className="watchlist-layout">
        {/* ── Left: create + list ─────────────────────────────────── */}
        <section className="watchlist-list-pane" aria-label="Saved watchlists">
          <div className="watchlist-create">
            <h2 className="pane-title">New watchlist</h2>
            <input
              type="text"
              className="text-input"
              placeholder="Name (e.g. Semiconductors)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              disabled={creating || analyzing}
              aria-label="New watchlist name"
            />
            <input
              type="text"
              className="text-input"
              placeholder="Description (optional)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              disabled={creating || analyzing}
              aria-label="New watchlist description"
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={creating || analyzing}
            >
              {creating ? 'Creating…' : 'Create watchlist'}
            </button>
          </div>

          {listLoading && <LoadingState message="Loading watchlists…" />}
          {listError && <ErrorMessage message={listError} />}

          {!listLoading && !listError && watchlists.length === 0 && (
            <p className="empty-state">
              No watchlists yet — create one to get started.
            </p>
          )}

          {watchlists.length > 0 && (
            <ul className="watchlist-items">
              {watchlists.map((wl) => (
                <li key={wl.id}>
                  <button
                    type="button"
                    className={`watchlist-item${
                      selected?.id === wl.id ? ' is-selected' : ''
                    }`}
                    onClick={() => handleSelect(wl.id)}
                    disabled={busy || analyzing}
                  >
                    <span className="watchlist-item-name">{wl.name}</span>
                    <span className="watchlist-item-count">
                      {wl.ticker_count}{' '}
                      {wl.ticker_count === 1 ? 'ticker' : 'tickers'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ── Right: selected detail ──────────────────────────────── */}
        <section className="watchlist-detail-pane" aria-label="Watchlist detail">
          {!selected && !detailError && (
            <p className="empty-state">
              Select a watchlist to view and manage its tickers.
            </p>
          )}
          {detailError && <ErrorMessage message={detailError} />}

          {selected && (
            <div className="watchlist-detail">
              <div className="watchlist-detail-head">
                <h2 className="pane-title">{selected.name}</h2>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleDelete}
                  disabled={busy || analyzing}
                >
                  Delete
                </button>
              </div>
              <p className="watchlist-detail-meta">
                {selected.tickers.length}{' '}
                {selected.tickers.length === 1 ? 'ticker' : 'tickers'}
                {selected.description ? ` · ${selected.description}` : ''}
              </p>

              <div className="watchlist-edit">
                <h3 className="section-title">Edit details</h3>
                <input
                  type="text"
                  className="text-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  disabled={busy || analyzing}
                  aria-label="Edit watchlist name"
                />
                <input
                  type="text"
                  className="text-input"
                  placeholder="Description (optional)"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  disabled={busy || analyzing}
                  aria-label="Edit watchlist description"
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleSaveEdit}
                  disabled={busy || analyzing}
                >
                  Save changes
                </button>
              </div>

              <div className="watchlist-tickers">
                <h3 className="section-title">Tickers</h3>
                <div className="add-ticker-row">
                  <input
                    type="text"
                    className="text-input ticker-field"
                    placeholder="e.g. AAPL"
                    value={tickerInput}
                    onChange={(e) =>
                      setTickerInput(e.target.value.toUpperCase())
                    }
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAddTicker()
                    }}
                    disabled={busy || analyzing}
                    aria-label="Add ticker symbol"
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleAddTicker}
                    disabled={busy || analyzing}
                  >
                    Add
                  </button>
                </div>

                {selected.tickers.length === 0 ? (
                  <p className="empty-state">
                    No tickers yet — add one above.
                  </p>
                ) : (
                  <ul className="ticker-chips">
                    {selected.tickers.map((ticker) => (
                      <li key={ticker} className="ticker-chip">
                        <span>{ticker}</span>
                        <button
                          type="button"
                          className="ticker-remove"
                          onClick={() => handleRemoveTicker(ticker)}
                          disabled={busy || analyzing}
                          aria-label={`Remove ${ticker}`}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="watchlist-analyze">
                <h3 className="section-title">Analyze</h3>
                <div className="analyze-row">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleAnalyze}
                    disabled={
                      busy || analyzing || selected.tickers.length === 0
                    }
                  >
                    {analyzing ? 'Analyzing…' : 'Analyze watchlist'}
                  </button>
                  <span className="action-hint">
                    On-demand analysis — results show here and are not saved.
                  </span>
                </div>
                {selected.tickers.length === 0 && (
                  <p className="empty-state">
                    Add at least one ticker to analyze.
                  </p>
                )}

                {analyzing && (
                  <LoadingState message="Analyzing watchlist — this may take a few seconds…" />
                )}
                {analysisError && <ErrorMessage message={analysisError} />}

                {analysis && (
                  <div className="analysis-result">
                    <p className="analysis-summary">
                      <strong>{analysis.watchlist_name}</strong> ·{' '}
                      {analysis.total_tickers}{' '}
                      {analysis.total_tickers === 1 ? 'ticker' : 'tickers'} ·{' '}
                      {analysis.successful_count} succeeded ·{' '}
                      {analysis.failed_count} failed
                    </p>
                    <p className="analysis-meta">
                      Analyzed {formatTimestamp(analysis.analyzed_at)} · on-demand
                      result, not saved to history
                    </p>

                    {analysis.results.length > 0 && (
                      <ul className="analysis-list">
                        {sortByScoreDesc(analysis.results).map((r) => (
                          <li key={r.ticker} className="analysis-card">
                            <div className="analysis-card-main">
                              <span className="analysis-card-ticker">
                                {r.ticker}
                              </span>
                              {r.company_name && (
                                <span className="analysis-card-company">
                                  {r.company_name}
                                </span>
                              )}
                            </div>
                            <div className="analysis-card-verdict">
                              <span className="category-badge">
                                {r.category}
                              </span>
                              <span className="analysis-card-score">
                                Score {r.score.toFixed(1)}
                              </span>
                              <span className="analysis-card-confidence">
                                {r.confidence}
                              </span>
                              {r.current_price != null && (
                                <span className="analysis-card-price">
                                  ${r.current_price.toFixed(2)}
                                </span>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}

                    {analysis.errors.length > 0 && (
                      <div className="analysis-errors">
                        <h4 className="analysis-errors-title">
                          Failed tickers ({analysis.errors.length})
                        </h4>
                        <ul className="analysis-error-list">
                          {analysis.errors.map((e) => (
                            <li key={e.ticker} className="analysis-error-item">
                              <span className="analysis-error-ticker">
                                {e.ticker}
                              </span>
                              <span className="analysis-error-msg">
                                {e.error}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>

      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>
    </div>
  )
}
