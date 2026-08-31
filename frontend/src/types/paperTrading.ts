/**
 * TypeScript interfaces that mirror the backend paper trading schemas.
 *
 * Display-layer types only — no accounting, valuation, or validation logic
 * here. Cash, cost basis, realized/unrealized gain-loss, and every total are
 * computed by the backend services and arrive pre-computed.
 *
 * Paper trading is a **simulation**: every row below describes a database
 * record the user typed in, at a price the user supplied. There is no broker,
 * no real account, and no real order.
 *
 * Source of truth: app/api/schemas/paper_trading.py
 */

// --- Requests --------------------------------------------------------------

/**
 * POST /api/paper-trading/accounts.
 *
 * `starting_cash` is sent as a string so the exact decimal the user typed
 * survives the wire (the backend parses it as a Decimal).
 */
export interface CreateAccountRequest {
  name: string
  starting_cash: string
}

/**
 * Body shared by the buy and sell endpoints (backend `TradeRequest`).
 *
 * `quantity` and `price` are sent as strings for the same decimal-precision
 * reason as `starting_cash`. The price is always supplied by the caller — the
 * backend never fetches a price to record a simulated trade.
 */
export interface PaperTradeRequest {
  ticker: string
  quantity: string
  price: string
  executed_at?: string | null
}

/** A simulated buy. Same shape as `PaperTradeRequest`; named for the caller. */
export type BuyRequest = PaperTradeRequest

/** A simulated sell. Same shape as `PaperTradeRequest`; named for the caller. */
export type SellRequest = PaperTradeRequest

// --- Responses -------------------------------------------------------------

/** One open position as stored, without market data. */
export interface PaperPosition {
  id: number
  account_id: number
  ticker: string
  quantity: number
  average_cost: number
  cost_basis: number
  created_at: string
  updated_at: string
}

/** One account as returned by the list endpoint. */
export interface PaperAccountSummary {
  id: number
  name: string
  starting_cash: number
  cash_balance: number
  realized_gain_loss: number
  created_at: string
  updated_at: string
  positions_count: number
}

/** One account with its stored (unpriced) open positions. */
export interface PaperAccountDetail {
  id: number
  name: string
  starting_cash: number
  cash_balance: number
  realized_gain_loss: number
  created_at: string
  updated_at: string
  positions: PaperPosition[]
}

/** One ledger row. `realized_gain_loss` is always 0 for BUY rows. */
export interface PaperTransaction {
  id: number
  account_id: number
  transaction_type: string
  ticker: string
  quantity: number
  price: number
  gross_amount: number
  realized_gain_loss: number
  executed_at: string
  created_at: string
}

// --- Priced views ----------------------------------------------------------

/**
 * An open position enriched with current-price calculations.
 *
 * Market-value-dependent fields are `null` (never zero) when the price could
 * not be fetched; `price_available` distinguishes the two cases.
 */
export interface PricedPaperPosition {
  position_id: number
  ticker: string
  quantity: number
  average_cost: number
  cost_basis: number
  price_available: boolean
  latest_price: number | null
  market_value: number | null
  unrealized_gain_loss: number | null
  unrealized_gain_loss_percent: number | null
}

/** One ticker whose current price could not be fetched. */
export interface PaperPriceWarning {
  ticker: string
  message: string
}

/** Priced open positions — GET /accounts/{id}/positions. */
export interface PaperPositionsResponse {
  account_id: number
  account_name: string
  generated_at: string
  positions_count: number
  priced_positions_count: number
  positions: PricedPaperPosition[]
  warnings: PaperPriceWarning[]
  has_price_warnings: boolean
}

/**
 * Valued account summary — GET /accounts/{id}/summary.
 *
 * `total_portfolio_value`, `total_return`, and `total_return_percent` are
 * `null` when some held position could not be priced: the total is genuinely
 * unknown then, and must never be rendered as zero.
 */
export interface PaperAccountSummaryResponse {
  account_id: number
  account_name: string
  generated_at: string
  starting_cash: number
  cash_balance: number
  realized_gain_loss: number
  unrealized_gain_loss: number | null
  open_positions_value: number | null
  total_portfolio_value: number | null
  total_return: number | null
  total_return_percent: number | null
  positions_count: number
  priced_positions_count: number
  positions: PricedPaperPosition[]
  warnings: PaperPriceWarning[]
  has_price_warnings: boolean
}

/** The three reads the Paper Trading page refreshes together. */
export interface PaperAccountView {
  detail: PaperAccountDetail
  summary: PaperAccountSummaryResponse
  transactions: PaperTransaction[]
}
