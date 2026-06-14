import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  addTickerToWatchlist,
  analyzeAndSaveSnapshot,
  analyzeWatchlist,
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  listWatchlistSnapshots,
  removeTickerFromWatchlist,
  updateWatchlist,
} from '../api/watchlistApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { AnalysisResultCard } from '../components/watchlist/AnalysisResultCard'
import { WatchlistCard } from '../components/watchlist/WatchlistCard'
import { getErrorMessage } from '../lib/errors'
import { formatDate, formatTimestamp } from '../lib/format'
import { sortByScoreDesc } from '../lib/sort'
import type {
  WatchlistAnalysisResponse,
  WatchlistDetail,
  WatchlistSnapshotSummary,
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

  // Saved analysis snapshots for the selected watchlist (historical records).
  const [snapshots, setSnapshots] = useState<WatchlistSnapshotSummary[]>([])
  const [snapshotsLoading, setSnapshotsLoading] = useState(false)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)
  const [savingSnapshot, setSavingSnapshot] = useState(false)

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

  // Load saved snapshots for a watchlist. Called from event handlers (never an
  // effect body), so setting state here does not cascade on mount.
  async function loadSnapshots(watchlistId: number) {
    setSnapshotsLoading(true)
    setSnapshotError(null)
    try {
      setSnapshots(await listWatchlistSnapshots(watchlistId))
    } catch (err) {
      setSnapshotError(getErrorMessage(err, 'Failed to load snapshots.'))
    } finally {
      setSnapshotsLoading(false)
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
      void loadSnapshots(id)
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
      // A brand-new watchlist has no snapshots yet.
      setSnapshots([])
      setSnapshotError(null)
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
      setSnapshots([])
      setSnapshotError(null)
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

  // Explicit, user-triggered: run the analysis once and save it as a snapshot.
  async function handleAnalyzeAndSave() {
    if (!selected || selected.tickers.length === 0) return
    setSavingSnapshot(true)
    setSnapshotError(null)
    try {
      await analyzeAndSaveSnapshot(selected.id)
      await loadSnapshots(selected.id)
    } catch (err) {
      setSnapshotError(getErrorMessage(err, 'Failed to save snapshot.'))
    } finally {
      setSavingSnapshot(false)
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Watchlists"
        subtitle="Group tickers you want to research, then run on-demand analysis. Results are shown here and are not saved."
      />

      <div className="watchlist-layout">
        {/* ── Left: create + overview ─────────────────────────────── */}
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
            <div className="watchlist-grid">
              {watchlists.map((wl) => (
                <WatchlistCard
                  key={wl.id}
                  watchlist={wl}
                  selected={selected?.id === wl.id}
                  disabled={busy || analyzing || savingSnapshot}
                  onSelect={handleSelect}
                />
              ))}
            </div>
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
            <div className="selected-watchlist-panel">
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
                {selected.tickers.length === 1 ? 'ticker' : 'tickers'} · Created{' '}
                {formatDate(selected.created_at)} · Updated{' '}
                {formatDate(selected.updated_at)}
              </p>
              {selected.description && (
                <p className="watchlist-detail-desc">{selected.description}</p>
              )}

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
                      busy ||
                      analyzing ||
                      savingSnapshot ||
                      selected.tickers.length === 0
                    }
                  >
                    {analyzing ? 'Analyzing…' : 'Analyze watchlist'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleAnalyzeAndSave}
                    disabled={
                      busy ||
                      analyzing ||
                      savingSnapshot ||
                      selected.tickers.length === 0
                    }
                  >
                    {savingSnapshot ? 'Saving…' : 'Analyze & save snapshot'}
                  </button>
                </div>
                <span className="action-hint">
                  “Analyze watchlist” shows results here without saving. “Analyze
                  &amp; save snapshot” also records a historical snapshot.
                </span>
                {selected.tickers.length === 0 && (
                  <p className="empty-state">
                    Add at least one ticker to analyze.
                  </p>
                )}

                <p className="watchlist-future-note">
                  <span className="soon-tag">Soon</span> Per-ticker mini price
                  charts and snapshot score trends are planned for a later
                  milestone.
                </p>

                {analyzing && (
                  <LoadingState message="Analyzing watchlist — this may take a few seconds…" />
                )}
                {analysisError && <ErrorMessage message={analysisError} />}

                {analysis && (
                  <div className="analysis-result">
                    <div className="analysis-stats">
                      <span className="analysis-stat">
                        <strong>{analysis.total_tickers}</strong> total
                      </span>
                      <span className="analysis-stat is-success">
                        <strong>{analysis.successful_count}</strong> succeeded
                      </span>
                      <span className="analysis-stat is-fail">
                        <strong>{analysis.failed_count}</strong> failed
                      </span>
                    </div>
                    <p className="analysis-meta">
                      Analyzed {formatTimestamp(analysis.analyzed_at)} · on-demand
                      result, not saved to history
                    </p>

                    {analysis.results.length > 0 && (
                      <ul className="watchlist-analysis-grid">
                        {sortByScoreDesc(analysis.results).map((r, i) => (
                          <AnalysisResultCard
                            key={r.ticker}
                            result={r}
                            rank={i + 1}
                          />
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

              <div className="watchlist-snapshots">
                <h3 className="section-title">Saved snapshots</h3>
                <p className="action-hint">
                  Historical records of manually triggered analysis runs.
                </p>
                {snapshotError && <ErrorMessage message={snapshotError} />}
                {snapshotsLoading && (
                  <LoadingState message="Loading snapshots…" />
                )}
                {!snapshotsLoading && snapshots.length === 0 && (
                  <p className="empty-state">
                    No saved snapshots yet — use “Analyze &amp; save snapshot”.
                  </p>
                )}
                {snapshots.length > 0 && (
                  <ul className="snapshot-list">
                    {snapshots.map((snap) => (
                      <li key={snap.id}>
                        <Link
                          to={`/watchlists/${snap.watchlist_id}/snapshots/${snap.id}`}
                          className="snapshot-row"
                        >
                          <span className="snapshot-date">
                            {formatTimestamp(snap.analyzed_at)}
                          </span>
                          <span className="snapshot-counts">
                            <span>{snap.total_tickers} tickers</span>
                            <span className="snapshot-ok">
                              {snap.success_count} ok
                            </span>
                            {snap.failure_count > 0 && (
                              <span className="snapshot-fail">
                                {snap.failure_count} failed
                              </span>
                            )}
                            <span className="snapshot-open" aria-hidden="true">
                              →
                            </span>
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
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
