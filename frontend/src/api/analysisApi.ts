/**
 * Functions for each backend endpoint used in Milestone 1.
 *
 * Milestone 1 scope: health check, analyze-only, analyze-and-save.
 * History and detail endpoints will be added in Milestone 2.
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
