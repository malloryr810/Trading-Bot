/**
 * Functions for the core analysis endpoints: health check, analyze-only, and
 * analyze-and-save. Saved-report reads live in reportsApi.ts.
 */

import { get, post } from './client'
import type { StockReport, SavedReportDetail } from '../types/report'

export interface HealthResponse {
  status: string
  service: string
}

/** GET /api/health — verify the backend is reachable. */
export async function checkHealth(): Promise<HealthResponse> {
  return get<HealthResponse>('/api/health')
}

/** POST /api/analyze — analyze a ticker; result is NOT saved. */
export async function analyzeOnly(ticker: string): Promise<StockReport> {
  return post<StockReport>('/api/analyze', { ticker })
}

/** POST /api/reports/analyze — analyze a ticker and save the snapshot. */
export async function analyzeAndSave(ticker: string): Promise<SavedReportDetail> {
  return post<SavedReportDetail>('/api/reports/analyze', { ticker })
}
