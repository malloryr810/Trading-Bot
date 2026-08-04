/**
 * Pure display + form-validation helpers for the portfolio UI.
 *
 * These format values the backend already computed and validate holding-form
 * input for immediate UX feedback. They never recompute portfolio totals,
 * gains, or weights — that logic lives only in the backend services. The
 * backend remains the authority on validation; this is a pre-submit convenience.
 */

const MONEY_FORMAT: Intl.NumberFormatOptions = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}

/** Format a money value as USD with 2 decimals. Null renders as an em dash. */
export function formatMoney(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return `$${value.toLocaleString('en-US', MONEY_FORMAT)}`
}

/** Format a gain/loss with an explicit +/- sign. Null renders as an em dash. */
export function formatSignedMoney(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  const sign = value < 0 ? '-' : '+'
  return `${sign}$${Math.abs(value).toLocaleString('en-US', MONEY_FORMAT)}`
}

/** Format a percentage with 2 decimals. Null renders as an em dash. */
export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(2)}%`
}

/** Format a signed percentage (e.g. a return). Null renders as an em dash. */
export function formatSignedPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '—'
  const sign = value < 0 ? '-' : '+'
  return `${sign}${Math.abs(value).toFixed(2)}%`
}

/** Format a share quantity, trimming needless trailing zeros (up to 6 dp). */
export function formatShares(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits: 6 })
}

export type GainLossTone = 'gain' | 'loss' | 'flat' | 'none'

/** Classify a gain/loss value for styling. Null (unavailable) is 'none'. */
export function gainLossTone(value: number | null): GainLossTone {
  if (value === null || !Number.isFinite(value)) return 'none'
  if (value > 0) return 'gain'
  if (value < 0) return 'loss'
  return 'flat'
}

/** Build the Analyze-page path for a ticker (used by the row Analyze action). */
export function analyzePath(ticker: string): string {
  return `/analyze?ticker=${encodeURIComponent(ticker.trim().toUpperCase())}`
}

// --- Holding form validation ----------------------------------------------

export interface HoldingFormValues {
  ticker: string
  shares: string
  averageCost: string
  purchaseDate: string
  notes: string
}

export interface HoldingFormErrors {
  ticker?: string
  shares?: string
  averageCost?: string
  purchaseDate?: string
}

export interface HoldingFormValidation {
  valid: boolean
  errors: HoldingFormErrors
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Validate holding-form input, mirroring the backend rules: ticker required,
 * shares > 0, average cost >= 0, purchase date optional ISO (YYYY-MM-DD).
 * Returns per-field errors for display; the backend re-validates on submit.
 */
export function validateHoldingForm(
  values: HoldingFormValues,
): HoldingFormValidation {
  const errors: HoldingFormErrors = {}

  if (!values.ticker.trim()) {
    errors.ticker = 'Ticker is required.'
  }

  const shares = Number(values.shares)
  if (!values.shares.trim() || !Number.isFinite(shares)) {
    errors.shares = 'Enter a number of shares.'
  } else if (shares <= 0) {
    errors.shares = 'Shares must be greater than zero.'
  }

  const cost = Number(values.averageCost)
  if (!values.averageCost.trim() || !Number.isFinite(cost)) {
    errors.averageCost = 'Enter an average cost.'
  } else if (cost < 0) {
    errors.averageCost = 'Average cost must be zero or greater.'
  }

  const date = values.purchaseDate.trim()
  if (date) {
    if (!ISO_DATE.test(date) || Number.isNaN(Date.parse(date))) {
      errors.purchaseDate = 'Use YYYY-MM-DD.'
    }
  }

  return { valid: Object.keys(errors).length === 0, errors }
}
