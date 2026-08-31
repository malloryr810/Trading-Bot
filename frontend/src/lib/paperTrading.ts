/**
 * Pure display + form-validation helpers for the paper trading UI.
 *
 * These validate form input for immediate UX feedback and describe values the
 * backend already computed. They never compute cash, cost basis, realized or
 * unrealized gain/loss, or any total — all of that accounting lives in
 * app/services/paper_trading_service.py and
 * app/services/paper_trading_summary_service.py, which stay authoritative.
 *
 * Money/share formatting is shared with the portfolio UI (see lib/portfolio):
 * those are generic display formatters, not portfolio accounting. The two
 * features remain otherwise separate — a manual portfolio records real
 * holdings, a paper trading account is a simulation with cash and a ledger.
 */

import type {
  PaperPriceWarning,
  PricedPaperPosition,
} from '../types/paperTrading'

// --- Display ---------------------------------------------------------------

/** Human label for a ledger row's transaction type. */
export function transactionTypeLabel(transactionType: string): string {
  const upper = transactionType.trim().toUpperCase()
  if (upper === 'BUY') return 'Buy'
  if (upper === 'SELL') return 'Sell'
  return transactionType
}

/** CSS modifier for a ledger row's transaction type. */
export function transactionTypeTone(transactionType: string): string {
  const upper = transactionType.trim().toUpperCase()
  return upper === 'BUY' || upper === 'SELL' ? upper.toLowerCase() : 'other'
}

/**
 * One-line description of an account for the selector list.
 * Values are read straight from the backend row; nothing is recomputed.
 */
export function accountPositionsLabel(positionsCount: number): string {
  return `${positionsCount} ${positionsCount === 1 ? 'position' : 'positions'}`
}

/**
 * Sentence describing unpriced positions, or null when everything is priced.
 * Used to explain why value-dependent totals render as an em dash rather than
 * zero — an unavailable price is not a zero price.
 */
export function priceWarningsSummary(
  warnings: PaperPriceWarning[],
): string | null {
  if (warnings.length === 0) return null
  const tickers = warnings.map((w) => w.ticker).join(', ')
  const noun = warnings.length === 1 ? 'position' : 'positions'
  return `Current price unavailable for ${warnings.length} ${noun} (${tickers}). Values that depend on a market price are shown as “—”, not zero.`
}

/** Tickers currently held, for the sell form's datalist. */
export function heldTickers(positions: PricedPaperPosition[]): string[] {
  return positions.map((p) => p.ticker)
}

// --- Account form ----------------------------------------------------------

export interface AccountFormValues {
  name: string
  startingCash: string
}

export interface AccountFormErrors {
  name?: string
  startingCash?: string
}

export interface FormValidation<E> {
  valid: boolean
  errors: E
}

/**
 * Validate the create-account form: name required, starting cash a number
 * greater than zero. The backend re-validates and remains authoritative.
 */
export function validateAccountForm(
  values: AccountFormValues,
): FormValidation<AccountFormErrors> {
  const errors: AccountFormErrors = {}

  if (!values.name.trim()) {
    errors.name = 'Account name is required.'
  }

  const cash = Number(values.startingCash)
  if (!values.startingCash.trim() || !Number.isFinite(cash)) {
    errors.startingCash = 'Enter a starting cash amount.'
  } else if (cash <= 0) {
    errors.startingCash = 'Starting cash must be greater than zero.'
  }

  return { valid: Object.keys(errors).length === 0, errors }
}

// --- Trade form ------------------------------------------------------------

export interface TradeFormValues {
  ticker: string
  quantity: string
  price: string
}

export interface TradeFormErrors {
  ticker?: string
  quantity?: string
  price?: string
}

export const EMPTY_TRADE_FORM: TradeFormValues = {
  ticker: '',
  quantity: '',
  price: '',
}

/**
 * Validate a buy or sell form: ticker required, quantity > 0, price > 0.
 *
 * Deliberately does NOT check the account's cash or share count — that is
 * accounting, and the backend owns it (it answers with HTTP 409 for
 * insufficient cash or shares, which the page surfaces verbatim).
 */
export function validateTradeForm(
  values: TradeFormValues,
): FormValidation<TradeFormErrors> {
  const errors: TradeFormErrors = {}

  if (!values.ticker.trim()) {
    errors.ticker = 'Ticker is required.'
  }

  const quantity = Number(values.quantity)
  if (!values.quantity.trim() || !Number.isFinite(quantity)) {
    errors.quantity = 'Enter a quantity.'
  } else if (quantity <= 0) {
    errors.quantity = 'Quantity must be greater than zero.'
  }

  const price = Number(values.price)
  if (!values.price.trim() || !Number.isFinite(price)) {
    errors.price = 'Enter a price.'
  } else if (price <= 0) {
    errors.price = 'Price must be greater than zero.'
  }

  return { valid: Object.keys(errors).length === 0, errors }
}

/** Turn validated form values into the request body (decimals as strings). */
export function toTradeRequest(values: TradeFormValues): {
  ticker: string
  quantity: string
  price: string
} {
  return {
    ticker: values.ticker.trim().toUpperCase(),
    quantity: values.quantity.trim(),
    price: values.price.trim(),
  }
}
