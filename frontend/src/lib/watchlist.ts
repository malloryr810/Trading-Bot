/**
 * Pure display helpers for watchlist analysis results.
 *
 * Display-only: these select / format values the backend already produced.
 * They never recompute ratings, scores, or categories.
 */

import type { StockReport } from '../types/report'

/**
 * Pick the most relevant one-line summary already present on a report, in
 * priority order: technical → fundamental → news → risk. Returns null when no
 * summary is available. Does not derive or compute any text.
 */
export function pickPrimarySummary(report: StockReport): string | null {
  const candidates = [
    report.technical_summary,
    report.fundamental_summary,
    report.news_summary,
    report.risk_summary,
  ]
  for (const summary of candidates) {
    if (typeof summary === 'string' && summary.trim()) {
      return summary.trim()
    }
  }
  return null
}
