/**
 * TypeScript interfaces that mirror the backend watchlist schemas.
 * Display-layer types only — no analysis, scoring, or validation logic here.
 *
 * Source of truth: app/api/schemas/watchlists.py
 */

export interface WatchlistSummary {
  id: number
  name: string
  description: string | null
  created_at: string
  updated_at: string
  ticker_count: number
}

export interface WatchlistDetail {
  id: number
  name: string
  description: string | null
  created_at: string
  updated_at: string
  tickers: string[]
}

export interface CreateWatchlistRequest {
  name: string
  description?: string | null
}

export interface UpdateWatchlistRequest {
  name?: string | null
  description?: string | null
}

export interface AddTickerRequest {
  ticker: string
}

export interface DeleteResponse {
  status: string
  id: number
}
