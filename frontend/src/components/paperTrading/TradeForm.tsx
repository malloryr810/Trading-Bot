import { useState } from 'react'
import {
  EMPTY_TRADE_FORM,
  validateTradeForm,
  type TradeFormErrors,
  type TradeFormValues,
} from '../../lib/paperTrading'

export type TradeMode = 'buy' | 'sell'

interface TradeFormProps {
  mode: TradeMode
  busy: boolean
  /** Tickers the account currently holds — sell-only suggestions. */
  heldTickers?: string[]
  onSubmit: (values: TradeFormValues) => void
}

const COPY: Record<TradeMode, { title: string; action: string; hint: string }> =
  {
    buy: {
      title: 'Simulated buy',
      action: 'Record buy',
      hint: 'Cash is debited at the price you enter. Nothing is ordered.',
    },
    sell: {
      title: 'Simulated sell',
      action: 'Record sell',
      hint: 'You can only sell shares the account holds — no short selling.',
    },
  }

/**
 * Buy/sell entry form for a simulated account.
 *
 * The price is typed by the user: this app never fetches a price in order to
 * "execute" a trade. Validation here is pre-submit UX only — the backend
 * re-validates and rejects an unaffordable buy or an oversized sell with 409.
 */
export function TradeForm({
  mode,
  busy,
  heldTickers = [],
  onSubmit,
}: TradeFormProps) {
  const [values, setValues] = useState<TradeFormValues>(EMPTY_TRADE_FORM)
  const [errors, setErrors] = useState<TradeFormErrors>({})
  const copy = COPY[mode]
  const listId = `paper-held-tickers-${mode}`

  function update<K extends keyof TradeFormValues>(key: K, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }))
    // Drop a field's error as soon as it is edited, so a stale message from an
    // earlier submit does not sit under a field the user has since corrected.
    setErrors((prev) => (key in prev ? { ...prev, [key]: undefined } : prev))
  }

  function handleSubmit() {
    const result = validateTradeForm(values)
    setErrors(result.errors)
    if (!result.valid) return
    onSubmit(values)
    setValues(EMPTY_TRADE_FORM)
    setErrors({})
  }

  return (
    <div className={`trade-form trade-form-${mode}`} aria-label={copy.title}>
      <h3 className="section-title">{copy.title}</h3>
      <div className="trade-form-grid">
        <label className="field">
          <span className="field-label">Ticker</span>
          <input
            type="text"
            className="text-input"
            placeholder="e.g. AAPL"
            list={mode === 'sell' ? listId : undefined}
            value={values.ticker}
            onChange={(e) => update('ticker', e.target.value.toUpperCase())}
            disabled={busy}
            aria-label={`${copy.title} ticker`}
          />
          {mode === 'sell' && (
            <datalist id={listId}>
              {heldTickers.map((ticker) => (
                <option key={ticker} value={ticker} />
              ))}
            </datalist>
          )}
          {errors.ticker && <span className="field-error">{errors.ticker}</span>}
        </label>

        <label className="field">
          <span className="field-label">Quantity</span>
          <input
            type="text"
            inputMode="decimal"
            className="text-input"
            placeholder="e.g. 10"
            value={values.quantity}
            onChange={(e) => update('quantity', e.target.value)}
            disabled={busy}
            aria-label={`${copy.title} quantity`}
          />
          {errors.quantity && (
            <span className="field-error">{errors.quantity}</span>
          )}
        </label>

        <label className="field">
          <span className="field-label">Price</span>
          <input
            type="text"
            inputMode="decimal"
            className="text-input"
            placeholder="e.g. 145.30"
            value={values.price}
            onChange={(e) => update('price', e.target.value)}
            disabled={busy}
            aria-label={`${copy.title} price`}
          />
          {errors.price && <span className="field-error">{errors.price}</span>}
        </label>
      </div>

      <div className="trade-form-actions">
        <button
          type="button"
          className={`btn ${mode === 'buy' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={handleSubmit}
          disabled={busy}
        >
          {busy ? 'Recording…' : copy.action}
        </button>
        <span className="action-hint">{copy.hint}</span>
      </div>
    </div>
  )
}
