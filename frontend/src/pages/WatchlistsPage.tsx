import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  addTickerToWatchlist,
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  removeTickerFromWatchlist,
  updateWatchlist,
} from '../api/watchlistApi'
import { ApiError } from '../api/client'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import type { WatchlistDetail, WatchlistSummary } from '../types/watchlist'

function messageFrom(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}

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

  async function refreshList(): Promise<WatchlistSummary[]> {
    setListLoading(true)
    setListError(null)
    try {
      const data = await listWatchlists()
      setWatchlists(data)
      return data
    } catch (err) {
      setListError(messageFrom(err, 'Failed to load watchlists.'))
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
        if (active) setListError(messageFrom(err, 'Failed to load watchlists.'))
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
  }

  async function handleSelect(id: number) {
    setDetailError(null)
    try {
      applySelected(await getWatchlist(id))
    } catch (err) {
      setSelected(null)
      setDetailError(messageFrom(err, 'Failed to load watchlist.'))
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
      setListError(messageFrom(err, 'Failed to create watchlist.'))
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
      setDetailError(messageFrom(err, 'Failed to add ticker.'))
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
      setDetailError(messageFrom(err, 'Failed to remove ticker.'))
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
      setDetailError(messageFrom(err, 'Failed to update watchlist.'))
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
      await refreshList()
    } catch (err) {
      setDetailError(messageFrom(err, 'Failed to delete watchlist.'))
    } finally {
      setBusy(false)
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
              disabled={creating}
              aria-label="New watchlist name"
            />
            <input
              type="text"
              className="text-input"
              placeholder="Description (optional)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              disabled={creating}
              aria-label="New watchlist description"
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={creating}
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
                  disabled={busy}
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
                  disabled={busy}
                  aria-label="Edit watchlist name"
                />
                <input
                  type="text"
                  className="text-input"
                  placeholder="Description (optional)"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  disabled={busy}
                  aria-label="Edit watchlist description"
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleSaveEdit}
                  disabled={busy}
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
                    disabled={busy}
                    aria-label="Add ticker symbol"
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleAddTicker}
                    disabled={busy}
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
                          disabled={busy}
                          aria-label={`Remove ${ticker}`}
                        >
                          ×
                        </button>
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
