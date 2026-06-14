/**
 * Pure transforms from the API price-history shape into Lightweight Charts
 * series data. Display-only — no analysis, no derived financial values.
 */

import type { PricePoint } from '../types/marketData'

/** A single point on a Lightweight Charts line/area series. */
export interface LinePoint {
  time: string
  value: number
}

/**
 * Map price points to a closing-price line series.
 *
 * Drops any point whose `close` is missing or non-finite so the chart never
 * renders gaps or `NaN`. Input order is preserved (the API returns
 * chronological data). The input array is not mutated.
 */
export function toClosingLineData(prices: readonly PricePoint[]): LinePoint[] {
  const points: LinePoint[] = []
  for (const point of prices) {
    if (typeof point.close === 'number' && Number.isFinite(point.close)) {
      points.push({ time: point.date, value: point.close })
    }
  }
  return points
}
