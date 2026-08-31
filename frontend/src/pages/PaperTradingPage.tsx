import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createAccount,
  listAccounts,
  loadAccountView,
  recordBuy,
  recordSell,
} from '../api/paperTradingApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { PaperAccountSelector } from '../components/paperTrading/PaperAccountSelector'
import { PaperAccountSummaryCards } from '../components/paperTrading/PaperAccountSummaryCards'
import { PaperPositionsTable } from '../components/paperTrading/PaperPositionsTable'
import { TransactionLedger } from '../components/paperTrading/TransactionLedger'
import { TradeForm, type TradeMode } from '../components/paperTrading/TradeForm'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import {
  heldTickers,
  priceWarningsSummary,
  toTradeRequest,
  validateAccountForm,
  type AccountFormErrors,
  type TradeFormValues,
} from '../lib/paperTrading'
import { formatMoney } from '../lib/portfolio'
import type {
  PaperAccountSummary,
  PaperAccountView,
} from '../types/paperTrading'

/**
 * Paper trading — a simulation, not live trading.
 *
 * Every account, position, and ledger row here is a database record the user
 * entered, priced at a value the user supplied. No broker is connected, no
 * order is routed, and nothing trades automatically. The backend owns all
 * accounting and valuation; this page only collects input and displays results.
 */
export function PaperTradingPage() {
  const [accounts, setAccounts] = useState<PaperAccountSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [view, setView] = useState<PaperAccountView | null>(null)
  const [viewLoading, setViewLoading] = useState(false)
  const [viewError, setViewError] = useState<string | null>(null)

  const [newName, setNewName] = useState('')
  const [newStartingCash, setNewStartingCash] = useState('')
  const [createErrors, setCreateErrors] = useState<AccountFormErrors>({})
  const [creating, setCreating] = useState(false)

  const [trading, setTrading] = useState(false)
  const [tradeError, setTradeError] = useState<string | null>(null)

  // Identifies the newest in-flight account load. A response that is no longer
  // the newest is dropped, so a slow request for a previously selected account
  // can never overwrite the account the user is actually looking at.
  const viewRequestId = useRef(0)

  async function refreshView(accountId: number) {
    const requestId = ++viewRequestId.current
    setViewLoading(true)
    setViewError(null)
    try {
      const next = await loadAccountView(accountId)
      if (requestId !== viewRequestId.current) return
      setView(next)
    } catch (err) {
      if (requestId !== viewRequestId.current) return
      setView(null)
      setViewError(getErrorMessage(err, 'Failed to load account.'))
    } finally {
      if (requestId === viewRequestId.current) setViewLoading(false)
    }
  }

  async function refreshList(): Promise<PaperAccountSummary[]> {
    const data = await listAccounts()
    setAccounts(data)
    return data
  }

  // Initial load. State is set only in async callbacks so mount does not cascade.
  // The backend returns accounts newest first, so index 0 is the default.
  useEffect(() => {
    let active = true
    listAccounts()
      .then((data) => {
        if (!active) return
        setAccounts(data)
        setListError(null)
        if (data.length > 0) {
          setSelectedId(data[0].id)
          void refreshView(data[0].id)
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setListError(getErrorMessage(err, 'Failed to load paper trading accounts.'))
        }
      })
      .finally(() => {
        if (active) setListLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function handleSelect(accountId: number) {
    setSelectedId(accountId)
    setTradeError(null)
    await refreshView(accountId)
  }

  async function handleCreate() {
    const validation = validateAccountForm({
      name: newName,
      startingCash: newStartingCash,
    })
    setCreateErrors(validation.errors)
    if (!validation.valid) return

    setCreating(true)
    setListError(null)
    try {
      const created = await createAccount({
        name: newName.trim(),
        starting_cash: newStartingCash.trim(),
      })
      setNewName('')
      setNewStartingCash('')
      setTradeError(null)
      await refreshList()
      setSelectedId(created.id)
      await refreshView(created.id)
    } catch (err) {
      setListError(getErrorMessage(err, 'Failed to create account.'))
    } finally {
      setCreating(false)
    }
  }

  async function handleTrade(mode: TradeMode, values: TradeFormValues) {
    if (selectedId === null) return
    setTrading(true)
    setTradeError(null)
    try {
      const payload = toTradeRequest(values)
      if (mode === 'buy') {
        await recordBuy(selectedId, payload)
      } else {
        await recordSell(selectedId, payload)
      }
      // A trade changes cash, positions, and the ledger, plus the account row
      // shown in the selector — refresh both.
      await Promise.all([refreshView(selectedId), refreshList()])
    } catch (err) {
      setTradeError(
        getErrorMessage(
          err,
          `Failed to record simulated ${mode}.`,
        ),
      )
    } finally {
      setTrading(false)
    }
  }

  const summary = view?.summary ?? null
  const warningsNote = summary ? priceWarningsSummary(summary.warnings) : null

  return (
    <div className="page">
      <PageHeader
        title="Paper Trading"
        subtitle="A simulated account for practising trade decisions. Buys and sells are database rows recorded at prices you type in — no broker is connected and no real order is ever placed."
      />

      <p className="paper-sim-banner" role="note">
        <strong>Simulation only.</strong> This is not live trading, and it is
        separate from your manually tracked portfolio holdings.
      </p>

      <div className="watchlist-layout paper-layout">
        {/* ── Left: create + account list ─────────────────────────── */}
        <section className="watchlist-list-pane" aria-label="Paper trading accounts">
          <div className="watchlist-create">
            <h2 className="pane-title">New simulated account</h2>
            <label className="field">
              <span className="field-label">Account name</span>
              <input
                type="text"
                className="text-input"
                placeholder="e.g. Practice account"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                disabled={creating}
                aria-label="New account name"
              />
              {createErrors.name && (
                <span className="field-error">{createErrors.name}</span>
              )}
            </label>
            <label className="field">
              <span className="field-label">Starting cash</span>
              <input
                type="text"
                inputMode="decimal"
                className="text-input"
                placeholder="e.g. 10000"
                value={newStartingCash}
                onChange={(e) => setNewStartingCash(e.target.value)}
                disabled={creating}
                aria-label="New account starting cash"
              />
              {createErrors.startingCash && (
                <span className="field-error">{createErrors.startingCash}</span>
              )}
            </label>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? 'Creating…' : 'Open account'}
            </button>
            <span className="action-hint paper-create-hint">
              Starting cash is imaginary — it is never funded or withdrawn.
            </span>
          </div>

          {listLoading && <LoadingState message="Loading accounts…" />}
          {listError && <ErrorMessage message={listError} />}

          {!listLoading && !listError && accounts.length === 0 && (
            <p className="empty-state">
              No simulated accounts yet — open one to start practising.
            </p>
          )}

          {accounts.length > 0 && (
            <PaperAccountSelector
              accounts={accounts}
              selectedId={selectedId}
              disabled={creating || trading || viewLoading}
              onSelect={handleSelect}
            />
          )}
        </section>

        {/* ── Right: selected account ─────────────────────────────── */}
        <section
          className="watchlist-detail-pane"
          aria-label="Selected account detail"
        >
          {selectedId === null && !viewError && !listLoading && (
            <p className="empty-state">
              Select an account to view its positions and record simulated
              trades.
            </p>
          )}

          {viewLoading && <LoadingState message="Loading account…" />}
          {viewError && <ErrorMessage message={viewError} />}

          {view && summary && (
            <div className="selected-watchlist-panel">
              <div className="watchlist-detail-head">
                <h2 className="pane-title">{view.detail.name}</h2>
              </div>
              <p className="watchlist-detail-meta">
                Started with {formatMoney(view.detail.starting_cash)} ·{' '}
                {view.detail.positions.length}{' '}
                {view.detail.positions.length === 1 ? 'position' : 'positions'} ·
                Valued {formatTimestamp(summary.generated_at)}
              </p>

              <PaperAccountSummaryCards summary={summary} />

              {warningsNote && (
                <p className="price-warning" role="note">
                  {warningsNote}
                </p>
              )}

              <div className="paper-section">
                <h3 className="section-title">Open positions</h3>
                {summary.positions.length === 0 ? (
                  <p className="empty-state">
                    No open positions — record a simulated buy below.
                  </p>
                ) : (
                  <PaperPositionsTable positions={summary.positions} />
                )}
              </div>

              <div className="paper-section">
                <h3 className="section-title">Record a simulated trade</h3>
                {tradeError && <ErrorMessage message={tradeError} />}
                <div className="trade-forms">
                  <TradeForm
                    mode="buy"
                    busy={trading || viewLoading}
                    onSubmit={(values) => void handleTrade('buy', values)}
                  />
                  <TradeForm
                    mode="sell"
                    busy={trading || viewLoading}
                    heldTickers={heldTickers(summary.positions)}
                    onSubmit={(values) => void handleTrade('sell', values)}
                  />
                </div>
              </div>

              <div className="paper-section">
                <h3 className="section-title">Transaction ledger</h3>
                <p className="action-hint">
                  Append-only record of every simulated trade, newest first.
                </p>
                {view.transactions.length === 0 ? (
                  <p className="empty-state">No trades recorded yet.</p>
                ) : (
                  <TransactionLedger transactions={view.transactions} />
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
