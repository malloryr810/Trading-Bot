import { useEffect, useState } from 'react'
import {
  addHolding,
  createPortfolio,
  deletePortfolio,
  getPortfolioSummary,
  listPortfolios,
  removeHolding,
  updateHolding,
  updatePortfolio,
} from '../../api/portfolioApi'
import { getErrorMessage } from '../../lib/errors'
import type { HoldingFormValues } from '../../lib/portfolio'
import type {
  PortfolioSummary,
  PortfolioSummaryResponse,
} from '../../types/portfolio'
import { ErrorMessage } from '../ErrorMessage'
import { LoadingState } from '../LoadingState'
import { HoldingForm } from './HoldingForm'
import { HoldingsTable } from './HoldingsTable'
import { PortfolioSelector } from './PortfolioSelector'
import { PortfolioSummaryCards } from './PortfolioSummaryCards'

/**
 * Container for the dashboard portfolio experience: portfolio selection + CRUD,
 * holding CRUD, and the priced summary. All financial values come from the
 * backend summary endpoint; this component only wires state and presentation.
 */
export function PortfolioPanel() {
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const [showEdit, setShowEdit] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')

  const [showAddHolding, setShowAddHolding] = useState(false)
  const [editingHoldingId, setEditingHoldingId] = useState<number | null>(null)

  async function loadSummary(id: number) {
    setSummaryLoading(true)
    setSummaryError(null)
    try {
      setSummary(await getPortfolioSummary(id))
    } catch (err) {
      setSummary(null)
      setSummaryError(getErrorMessage(err, 'Failed to load portfolio summary.'))
    } finally {
      setSummaryLoading(false)
    }
  }

  async function refreshList(): Promise<PortfolioSummary[]> {
    const data = await listPortfolios()
    setPortfolios(data)
    return data
  }

  // Initial load. State is set only in async callbacks so mount does not cascade.
  useEffect(() => {
    let active = true
    listPortfolios()
      .then((data) => {
        if (!active) return
        setPortfolios(data)
        setListError(null)
        if (data.length > 0) {
          setSelectedId(data[0].id)
          void loadSummary(data[0].id)
        }
      })
      .catch((err: unknown) => {
        if (active) setListError(getErrorMessage(err, 'Failed to load portfolios.'))
      })
      .finally(() => {
        if (active) setListLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  function resetForms() {
    setShowCreate(false)
    setShowEdit(false)
    setShowAddHolding(false)
    setEditingHoldingId(null)
    setActionError(null)
  }

  async function handleSelect(id: number) {
    setSelectedId(id)
    resetForms()
    await loadSummary(id)
  }

  async function handleCreate() {
    const name = newName.trim()
    if (!name) {
      setActionError('Please enter a portfolio name.')
      return
    }
    setBusy(true)
    setActionError(null)
    try {
      const created = await createPortfolio({
        name,
        description: newDescription.trim() || null,
      })
      setNewName('')
      setNewDescription('')
      setShowCreate(false)
      await refreshList()
      setSelectedId(created.id)
      await loadSummary(created.id)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to create portfolio.'))
    } finally {
      setBusy(false)
    }
  }

  function openEdit() {
    if (!summary) return
    setEditName(summary.portfolio_name)
    const current = portfolios.find((p) => p.id === summary.portfolio_id)
    setEditDescription(current?.description ?? '')
    setShowEdit(true)
    setActionError(null)
  }

  async function handleSaveEdit() {
    if (selectedId === null) return
    const name = editName.trim()
    if (!name) {
      setActionError('Portfolio name cannot be blank.')
      return
    }
    setBusy(true)
    setActionError(null)
    try {
      await updatePortfolio(selectedId, {
        name,
        description: editDescription.trim(),
      })
      setShowEdit(false)
      await refreshList()
      await loadSummary(selectedId)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to update portfolio.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleDeletePortfolio() {
    if (selectedId === null || !summary) return
    if (
      !window.confirm(
        `Delete portfolio "${summary.portfolio_name}" and all its holdings? This cannot be undone.`,
      )
    ) {
      return
    }
    setBusy(true)
    setActionError(null)
    try {
      await deletePortfolio(selectedId)
      resetForms()
      const remaining = await refreshList()
      if (remaining.length > 0) {
        setSelectedId(remaining[0].id)
        await loadSummary(remaining[0].id)
      } else {
        setSelectedId(null)
        setSummary(null)
      }
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to delete portfolio.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleAddHolding(values: HoldingFormValues) {
    if (selectedId === null) return
    setBusy(true)
    setActionError(null)
    try {
      await addHolding(selectedId, {
        ticker: values.ticker.trim(),
        shares: values.shares.trim(),
        average_cost: values.averageCost.trim(),
        purchase_date: values.purchaseDate.trim() || null,
        notes: values.notes.trim() || null,
      })
      setShowAddHolding(false)
      await refreshList()
      await loadSummary(selectedId)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to add holding.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleEditHolding(holdingId: number, values: HoldingFormValues) {
    if (selectedId === null) return
    setBusy(true)
    setActionError(null)
    try {
      await updateHolding(selectedId, holdingId, {
        ticker: values.ticker.trim(),
        shares: values.shares.trim(),
        average_cost: values.averageCost.trim(),
        purchase_date: values.purchaseDate.trim() || null,
        notes: values.notes.trim() || null,
      })
      setEditingHoldingId(null)
      await refreshList()
      await loadSummary(selectedId)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to update holding.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleRemoveHolding(holdingId: number) {
    if (selectedId === null) return
    if (!window.confirm('Remove this holding?')) return
    setBusy(true)
    setActionError(null)
    try {
      await removeHolding(selectedId, holdingId)
      await refreshList()
      await loadSummary(selectedId)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to remove holding.'))
    } finally {
      setBusy(false)
    }
  }

  const editingHolding =
    editingHoldingId !== null
      ? summary?.holdings.find((h) => h.holding_id === editingHoldingId) ?? null
      : null

  return (
    <section className="portfolio-panel" aria-label="Portfolio">
      <div className="portfolio-panel-head">
        <div>
          <h2 className="portfolio-panel-title">Portfolio</h2>
          <p className="portfolio-panel-subtitle">
            Manually tracked holdings, valued at current end-of-day prices. No
            brokerage connection, no trading — read-only tracking only.
          </p>
        </div>
      </div>

      {listLoading && <LoadingState message="Loading portfolios…" />}
      {listError && <ErrorMessage message={listError} />}

      {!listLoading && !listError && (
        <>
          <div className="portfolio-controls">
            <PortfolioSelector
              portfolios={portfolios}
              selectedId={selectedId}
              disabled={busy}
              onSelect={handleSelect}
              onNew={() => {
                setShowCreate((v) => !v)
                setActionError(null)
              }}
            />
            {selectedId !== null && summary && (
              <div className="portfolio-meta-actions">
                <button
                  type="button"
                  className="btn btn-small btn-secondary"
                  onClick={openEdit}
                  disabled={busy}
                >
                  Edit details
                </button>
                <button
                  type="button"
                  className="btn btn-small btn-danger"
                  onClick={handleDeletePortfolio}
                  disabled={busy}
                >
                  Delete
                </button>
              </div>
            )}
          </div>

          {actionError && <ErrorMessage message={actionError} />}

          {showCreate && (
            <div className="portfolio-inline-form">
              <h3 className="section-title">New portfolio</h3>
              <input
                type="text"
                className="text-input"
                placeholder="Name (e.g. Long-term)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                disabled={busy}
                aria-label="New portfolio name"
              />
              <input
                type="text"
                className="text-input"
                placeholder="Description (optional)"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                disabled={busy}
                aria-label="New portfolio description"
              />
              <div className="holding-form-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleCreate}
                  disabled={busy}
                >
                  Create portfolio
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreate(false)}
                  disabled={busy}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {showEdit && selectedId !== null && (
            <div className="portfolio-inline-form">
              <h3 className="section-title">Edit portfolio</h3>
              <input
                type="text"
                className="text-input"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={busy}
                aria-label="Edit portfolio name"
              />
              <input
                type="text"
                className="text-input"
                placeholder="Description (optional)"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                disabled={busy}
                aria-label="Edit portfolio description"
              />
              <div className="holding-form-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSaveEdit}
                  disabled={busy}
                >
                  Save changes
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEdit(false)}
                  disabled={busy}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {portfolios.length === 0 && !showCreate && (
            <p className="empty-state">
              No portfolios yet — use “New portfolio” to create one and start
              tracking holdings.
            </p>
          )}

          {selectedId !== null && (
            <>
              {summaryLoading && <LoadingState message="Pricing portfolio…" />}
              {summaryError && <ErrorMessage message={summaryError} />}

              {!summaryLoading && !summaryError && summary && (
                <div className="portfolio-body">
                  <PortfolioSummaryCards summary={summary} />

                  {summary.has_price_warnings && (
                    <div className="price-warning" role="status">
                      <strong>Some prices are unavailable.</strong> Market values
                      and returns exclude{' '}
                      {summary.warnings.map((w) => w.ticker).join(', ')}. Cost
                      basis still reflects every holding.
                    </div>
                  )}

                  <div className="holdings-head">
                    <h3 className="section-title">Holdings</h3>
                    <button
                      type="button"
                      className="btn btn-primary btn-small"
                      onClick={() => {
                        setShowAddHolding((v) => !v)
                        setEditingHoldingId(null)
                        setActionError(null)
                      }}
                      disabled={busy}
                    >
                      {showAddHolding ? 'Close' : 'Add holding'}
                    </button>
                  </div>

                  {showAddHolding && (
                    <HoldingForm
                      mode="add"
                      busy={busy}
                      onSubmit={handleAddHolding}
                      onCancel={() => setShowAddHolding(false)}
                    />
                  )}

                  {editingHolding && (
                    <HoldingForm
                      mode="edit"
                      busy={busy}
                      initial={{
                        ticker: editingHolding.ticker,
                        shares: String(editingHolding.shares),
                        averageCost: String(editingHolding.average_cost),
                        purchaseDate: editingHolding.purchase_date ?? '',
                        notes: editingHolding.notes ?? '',
                      }}
                      onSubmit={(values) =>
                        handleEditHolding(editingHolding.holding_id, values)
                      }
                      onCancel={() => setEditingHoldingId(null)}
                    />
                  )}

                  {summary.holdings.length === 0 ? (
                    <p className="empty-state">
                      No holdings yet — add one to see live valuations.
                    </p>
                  ) : (
                    <HoldingsTable
                      holdings={summary.holdings}
                      disabled={busy}
                      onEdit={(id) => {
                        setEditingHoldingId(id)
                        setShowAddHolding(false)
                        setActionError(null)
                      }}
                      onRemove={handleRemoveHolding}
                    />
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
