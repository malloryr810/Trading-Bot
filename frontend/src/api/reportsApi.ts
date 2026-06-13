/**
 * Functions for the saved-report read endpoints under /api/reports.
 *
 * Display-only history: these wrappers fetch reports the backend already
 * persisted. No analysis is triggered here — saving happens via analyzeAndSave
 * in analysisApi.ts.
 */

import { get } from './client'
import type { SavedReportDetail, SavedReportSummary } from '../types/report'

/** GET /api/reports/history — list saved report summaries, newest first. */
export async function listSavedReports(
  limit = 50,
): Promise<SavedReportSummary[]> {
  return get<SavedReportSummary[]>(`/api/reports/history?limit=${limit}`)
}

/** GET /api/reports/{id} — fetch one full saved report snapshot. */
export async function getSavedReport(id: number): Promise<SavedReportDetail> {
  return get<SavedReportDetail>(`/api/reports/${id}`)
}
