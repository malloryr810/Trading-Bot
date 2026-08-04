/**
 * Functions for each /api/portfolios endpoint.
 *
 * One function per backend endpoint. All validation, persistence, and financial
 * calculation live in the backend services — these wrappers only shape the
 * request and type the response.
 */

import { del, get, patch, post } from './client'
import type {
  AddHoldingRequest,
  CreatePortfolioRequest,
  DeleteResponse,
  Holding,
  PortfolioDetail,
  PortfolioSummary,
  PortfolioSummaryResponse,
  UpdateHoldingRequest,
  UpdatePortfolioRequest,
} from '../types/portfolio'

/** GET /api/portfolios — list all portfolios (newest first). */
export async function listPortfolios(): Promise<PortfolioSummary[]> {
  return get<PortfolioSummary[]>('/api/portfolios')
}

/** POST /api/portfolios — create a new portfolio. */
export async function createPortfolio(
  payload: CreatePortfolioRequest,
): Promise<PortfolioDetail> {
  return post<PortfolioDetail>('/api/portfolios', payload)
}

/** GET /api/portfolios/{id} — fetch one portfolio with its holdings. */
export async function getPortfolio(id: number): Promise<PortfolioDetail> {
  return get<PortfolioDetail>(`/api/portfolios/${id}`)
}

/** PATCH /api/portfolios/{id} — update name and/or description. */
export async function updatePortfolio(
  id: number,
  payload: UpdatePortfolioRequest,
): Promise<PortfolioDetail> {
  return patch<PortfolioDetail>(`/api/portfolios/${id}`, payload)
}

/** DELETE /api/portfolios/{id} — delete a portfolio and its holdings. */
export async function deletePortfolio(id: number): Promise<DeleteResponse> {
  return del<DeleteResponse>(`/api/portfolios/${id}`)
}

/** POST /api/portfolios/{id}/holdings — add a holding. */
export async function addHolding(
  portfolioId: number,
  payload: AddHoldingRequest,
): Promise<Holding> {
  return post<Holding>(`/api/portfolios/${portfolioId}/holdings`, payload)
}

/** PATCH /api/portfolios/{id}/holdings/{holdingId} — update a holding. */
export async function updateHolding(
  portfolioId: number,
  holdingId: number,
  payload: UpdateHoldingRequest,
): Promise<Holding> {
  return patch<Holding>(
    `/api/portfolios/${portfolioId}/holdings/${holdingId}`,
    payload,
  )
}

/** DELETE /api/portfolios/{id}/holdings/{holdingId} — remove a holding. */
export async function removeHolding(
  portfolioId: number,
  holdingId: number,
): Promise<DeleteResponse> {
  return del<DeleteResponse>(
    `/api/portfolios/${portfolioId}/holdings/${holdingId}`,
  )
}

/** GET /api/portfolios/{id}/summary — priced summary with calculations. */
export async function getPortfolioSummary(
  id: number,
): Promise<PortfolioSummaryResponse> {
  return get<PortfolioSummaryResponse>(`/api/portfolios/${id}/summary`)
}
