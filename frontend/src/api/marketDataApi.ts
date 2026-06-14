/**
 * Client for the read-only market-data history endpoint.
 *
 * GET /api/market-data/{ticker}/history — daily historical OHLCV prices.
 */

import { get } from './client'
import type { PriceHistoryResponse } from '../types/marketData'

/** Fetch daily historical price data for a ticker. */
export async function getPriceHistory(
  ticker: string,
  period = '1y',
  interval = '1d',
): Promise<PriceHistoryResponse> {
  const params = new URLSearchParams({ period, interval })
  return get<PriceHistoryResponse>(
    `/api/market-data/${encodeURIComponent(ticker)}/history?${params.toString()}`,
  )
}
