import { useState } from 'react'
import {
  validateHoldingForm,
  type HoldingFormErrors,
  type HoldingFormValues,
} from '../../lib/portfolio'

interface HoldingFormProps {
  mode: 'add' | 'edit'
  initial?: Partial<HoldingFormValues>
  busy: boolean
  onSubmit: (values: HoldingFormValues) => void
  onCancel?: () => void
}

const EMPTY: HoldingFormValues = {
  ticker: '',
  shares: '',
  averageCost: '',
  purchaseDate: '',
  notes: '',
}

/**
 * Reusable add/edit holding form. Runs client-side validation (mirroring the
 * backend rules) purely for immediate feedback; the backend re-validates and
 * remains authoritative. Financial values are passed up as entered strings.
 */
export function HoldingForm({
  mode,
  initial,
  busy,
  onSubmit,
  onCancel,
}: HoldingFormProps) {
  const [values, setValues] = useState<HoldingFormValues>({
    ...EMPTY,
    ...initial,
  })
  const [errors, setErrors] = useState<HoldingFormErrors>({})

  function update<K extends keyof HoldingFormValues>(
    key: K,
    value: HoldingFormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit() {
    const result = validateHoldingForm(values)
    setErrors(result.errors)
    if (result.valid) onSubmit(values)
  }

  return (
    <div className="holding-form" aria-label={`${mode} holding`}>
      <div className="holding-form-grid">
        <label className="field">
          <span className="field-label">Ticker</span>
          <input
            type="text"
            className="text-input"
            placeholder="e.g. AAPL"
            value={values.ticker}
            onChange={(e) => update('ticker', e.target.value.toUpperCase())}
            disabled={busy}
            aria-label="Holding ticker"
          />
          {errors.ticker && <span className="field-error">{errors.ticker}</span>}
        </label>

        <label className="field">
          <span className="field-label">Shares</span>
          <input
            type="text"
            inputMode="decimal"
            className="text-input"
            placeholder="e.g. 10"
            value={values.shares}
            onChange={(e) => update('shares', e.target.value)}
            disabled={busy}
            aria-label="Holding shares"
          />
          {errors.shares && <span className="field-error">{errors.shares}</span>}
        </label>

        <label className="field">
          <span className="field-label">Average cost</span>
          <input
            type="text"
            inputMode="decimal"
            className="text-input"
            placeholder="e.g. 145.30"
            value={values.averageCost}
            onChange={(e) => update('averageCost', e.target.value)}
            disabled={busy}
            aria-label="Holding average cost"
          />
          {errors.averageCost && (
            <span className="field-error">{errors.averageCost}</span>
          )}
        </label>

        <label className="field">
          <span className="field-label">Purchase date</span>
          <input
            type="date"
            className="text-input"
            value={values.purchaseDate}
            onChange={(e) => update('purchaseDate', e.target.value)}
            disabled={busy}
            aria-label="Holding purchase date"
          />
          {errors.purchaseDate && (
            <span className="field-error">{errors.purchaseDate}</span>
          )}
        </label>

        <label className="field field--wide">
          <span className="field-label">Notes</span>
          <input
            type="text"
            className="text-input"
            placeholder="Optional"
            value={values.notes}
            onChange={(e) => update('notes', e.target.value)}
            disabled={busy}
            aria-label="Holding notes"
          />
        </label>
      </div>

      <div className="holding-form-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={busy}
        >
          {mode === 'add' ? 'Add holding' : 'Save changes'}
        </button>
        {onCancel && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}
