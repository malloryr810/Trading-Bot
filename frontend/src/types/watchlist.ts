/**
 * TypeScript interfaces that mirror the backend watchlist schemas.
 * Display-layer types only — no analysis, scoring, or validation logic here.
 *
 * Source of truth: app/api/schemas/watchlists.py
 */

import type { StockReport } from './report'

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

// --- Analyze watchlist (on-demand, not saved) ------------------------------

export interface WatchlistAnalysisResult {
  ticker: string
  company_name: string | null
  category: string
  score: number
  confidence: string
  current_price: number | null
  report: StockReport
}

export interface WatchlistAnalysisError {
  ticker: string
  error: string
}

export interface WatchlistAnalysisResponse {
  watchlist_id: number
  watchlist_name: string
  analyzed_at: string
  total_tickers: number
  successful_count: number
  failed_count: number
  results: WatchlistAnalysisResult[]
  errors: WatchlistAnalysisError[]
}

// --- Saved analysis snapshots ----------------------------------------------

export interface WatchlistSnapshotSummary {
  id: number
  watchlist_id: number
  watchlist_name: string
  analyzed_at: string
  total_tickers: number
  success_count: number
  failure_count: number
  // Backend-derived mean score across successful ticker results; null when no
  // successful scored rows exist. Never recomputed in the frontend.
  average_score: number | null
  created_at: string
}

export interface WatchlistSnapshotDetail extends WatchlistSnapshotSummary {
  results: WatchlistAnalysisResult[]
  errors: WatchlistAnalysisError[]
}
