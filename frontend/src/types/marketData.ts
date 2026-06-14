/**
 * TypeScript interfaces mirroring the backend market-data schemas.
 * Display-layer types only.
 *
 * Source of truth: app/api/schemas/market_data.py
 */

export interface PricePoint {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
}

export interface PriceHistoryResponse {
  ticker: string
  period: string
  interval: string
  data_timestamp: string | null
  prices: PricePoint[]
}
