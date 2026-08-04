/**
 * TypeScript interfaces that mirror the backend portfolio schemas.
 * Display-layer types only — no analysis, scoring, or financial calculation
 * logic here. All portfolio totals are computed by the backend.
 *
 * Source of truth: app/api/schemas/portfolios.py
 */

export interface PortfolioSummary {
  id: number
  name: string
  description: string | null
  created_at: string
  updated_at: string
  holdings_count: number
}

export interface Holding {
  id: number
  portfolio_id: number
  ticker: string
  shares: number
  average_cost: number
  purchase_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PortfolioDetail {
  id: number
  name: string
  description: string | null
  created_at: string
  updated_at: string
  holdings: Holding[]
}

export interface CreatePortfolioRequest {
  name: string
  description?: string | null
}

export interface UpdatePortfolioRequest {
  name?: string | null
  description?: string | null
}

/**
 * Shares and average cost are sent as strings to preserve exact decimal
 * precision across the wire (the backend parses them as Decimals).
 */
export interface AddHoldingRequest {
  ticker: string
  shares: string
  average_cost: string
  purchase_date?: string | null
  notes?: string | null
}

export interface UpdateHoldingRequest {
  ticker?: string | null
  shares?: string | null
  average_cost?: string | null
  purchase_date?: string | null
  notes?: string | null
}

export interface DeleteResponse {
  status: string
  id: number
}

// --- Priced summary --------------------------------------------------------

export interface HoldingValuation {
  holding_id: number
  ticker: string
  shares: number
  average_cost: number
  purchase_date: string | null
  notes: string | null
  price_available: boolean
  current_price: number | null
  cost_basis: number
  market_value: number | null
  unrealized_gain_loss: number | null
  unrealized_return_pct: number | null
  weight_pct: number | null
}

export interface PortfolioSummaryWarning {
  ticker: string
  message: string
}

export interface PortfolioSummaryResponse {
  portfolio_id: number
  portfolio_name: string
  generated_at: string
  holdings_count: number
  priced_holdings_count: number
  total_cost_basis: number
  total_market_value: number | null
  total_unrealized_gain_loss: number | null
  total_unrealized_return_pct: number | null
  holdings: HoldingValuation[]
  warnings: PortfolioSummaryWarning[]
  has_price_warnings: boolean
}
