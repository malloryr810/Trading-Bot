/**
 * Functions for each /api/watchlists endpoint.
 *
 * One function per backend endpoint. All validation and business logic lives
 * in the backend service — these wrappers only shape the request and type the
 * response.
 */

import { del, get, patch, post } from './client'
import type {
  AddTickerRequest,
  CreateWatchlistRequest,
  DeleteResponse,
  UpdateWatchlistRequest,
  WatchlistAnalysisResponse,
  WatchlistDetail,
  WatchlistSnapshotDetail,
  WatchlistSnapshotSummary,
  WatchlistSummary,
} from '../types/watchlist'

/** GET /api/watchlists — list all saved watchlists (newest first). */
export async function listWatchlists(): Promise<WatchlistSummary[]> {
  return get<WatchlistSummary[]>('/api/watchlists')
}

/** POST /api/watchlists — create a new watchlist. */
export async function createWatchlist(
  payload: CreateWatchlistRequest,
): Promise<WatchlistDetail> {
  return post<WatchlistDetail>('/api/watchlists', payload)
}

/** GET /api/watchlists/{id} — fetch one watchlist with its tickers. */
export async function getWatchlist(id: number): Promise<WatchlistDetail> {
  return get<WatchlistDetail>(`/api/watchlists/${id}`)
}

/** PATCH /api/watchlists/{id} — update name and/or description. */
export async function updateWatchlist(
  id: number,
  payload: UpdateWatchlistRequest,
): Promise<WatchlistDetail> {
  return patch<WatchlistDetail>(`/api/watchlists/${id}`, payload)
}

/** DELETE /api/watchlists/{id} — delete a watchlist and its tickers. */
export async function deleteWatchlist(id: number): Promise<DeleteResponse> {
  return del<DeleteResponse>(`/api/watchlists/${id}`)
}

/** POST /api/watchlists/{id}/tickers — add a ticker to a watchlist. */
export async function addTickerToWatchlist(
  id: number,
  payload: AddTickerRequest,
): Promise<WatchlistDetail> {
  return post<WatchlistDetail>(`/api/watchlists/${id}/tickers`, payload)
}

/** DELETE /api/watchlists/{id}/tickers/{ticker} — remove a ticker. */
export async function removeTickerFromWatchlist(
  id: number,
  ticker: string,
): Promise<WatchlistDetail> {
  return del<WatchlistDetail>(
    `/api/watchlists/${id}/tickers/${encodeURIComponent(ticker)}`,
  )
}

/**
 * POST /api/watchlists/{id}/analyze — run the analysis pipeline over every
 * ticker in the watchlist. On-demand only; results are not saved server-side.
 */
export async function analyzeWatchlist(
  id: number,
): Promise<WatchlistAnalysisResponse> {
  return post<WatchlistAnalysisResponse>(`/api/watchlists/${id}/analyze`, {})
}

/**
 * POST /api/watchlists/{id}/analysis-snapshots — explicitly run an on-demand
 * analysis once and save it as a historical snapshot. Distinct from analyze.
 */
export async function analyzeAndSaveSnapshot(
  id: number,
): Promise<WatchlistSnapshotDetail> {
  return post<WatchlistSnapshotDetail>(
    `/api/watchlists/${id}/analysis-snapshots`,
    {},
  )
}

/** GET /api/watchlists/{id}/analysis-snapshots — saved snapshots, newest first. */
export async function listWatchlistSnapshots(
  id: number,
): Promise<WatchlistSnapshotSummary[]> {
  return get<WatchlistSnapshotSummary[]>(
    `/api/watchlists/${id}/analysis-snapshots`,
  )
}

/** GET /api/watchlist-analysis-snapshots/{snapshotId} — one snapshot's detail. */
export async function getWatchlistSnapshot(
  snapshotId: number,
): Promise<WatchlistSnapshotDetail> {
  return get<WatchlistSnapshotDetail>(
    `/api/watchlist-analysis-snapshots/${snapshotId}`,
  )
}
