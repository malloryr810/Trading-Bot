/**
 * Functions for each /api/paper-trading endpoint.
 *
 * One function per backend endpoint, plus one composite reader
 * (`loadAccountView`) that issues the page's three account reads in parallel.
 * All validation, accounting, and valuation live in the backend services —
 * these wrappers only shape the request and type the response.
 *
 * Paper trading is simulated. A "buy" or "sell" here is a POST that writes a
 * database row at a price the caller supplied; no broker is contacted and no
 * real order is placed.
 */

import { get, post } from './client'
import type {
  BuyRequest,
  CreateAccountRequest,
  PaperAccountDetail,
  PaperAccountSummary,
  PaperAccountSummaryResponse,
  PaperAccountView,
  PaperPositionsResponse,
  PaperTransaction,
  SellRequest,
} from '../types/paperTrading'

const BASE = '/api/paper-trading/accounts'

/** GET /api/paper-trading/accounts — list all accounts (newest first). */
export async function listAccounts(): Promise<PaperAccountSummary[]> {
  return get<PaperAccountSummary[]>(BASE)
}

/** POST /api/paper-trading/accounts — open a simulated account. */
export async function createAccount(
  payload: CreateAccountRequest,
): Promise<PaperAccountDetail> {
  return post<PaperAccountDetail>(BASE, payload)
}

/** GET /api/paper-trading/accounts/{id} — one account with stored positions. */
export async function getAccount(id: number): Promise<PaperAccountDetail> {
  return get<PaperAccountDetail>(`${BASE}/${id}`)
}

/** GET /api/paper-trading/accounts/{id}/summary — account valued at current prices. */
export async function getAccountSummary(
  id: number,
): Promise<PaperAccountSummaryResponse> {
  return get<PaperAccountSummaryResponse>(`${BASE}/${id}/summary`)
}

/** GET /api/paper-trading/accounts/{id}/positions — priced open positions. */
export async function getAccountPositions(
  id: number,
): Promise<PaperPositionsResponse> {
  return get<PaperPositionsResponse>(`${BASE}/${id}/positions`)
}

/** GET /api/paper-trading/accounts/{id}/transactions — ledger, newest first. */
export async function listTransactions(
  id: number,
): Promise<PaperTransaction[]> {
  return get<PaperTransaction[]>(`${BASE}/${id}/transactions`)
}

/**
 * POST /api/paper-trading/accounts/{id}/buy — record a simulated buy.
 *
 * Insufficient cash comes back as an ApiError with status 409.
 */
export async function recordBuy(
  id: number,
  payload: BuyRequest,
): Promise<PaperTransaction> {
  return post<PaperTransaction>(`${BASE}/${id}/buy`, payload)
}

/**
 * POST /api/paper-trading/accounts/{id}/sell — record a simulated sell.
 *
 * Selling more than the account holds comes back as an ApiError with status
 * 409; short selling is not supported by the backend.
 */
export async function recordSell(
  id: number,
  payload: SellRequest,
): Promise<PaperTransaction> {
  return post<PaperTransaction>(`${BASE}/${id}/sell`, payload)
}

/**
 * Fetch everything the Paper Trading page shows for one account, in parallel.
 *
 * The summary response already carries the priced positions, so the separate
 * positions endpoint is deliberately not called here — it would repeat the
 * same market-data work for the same rows. `getAccountPositions` stays
 * available for callers that want only the positions view.
 */
export async function loadAccountView(id: number): Promise<PaperAccountView> {
  const [detail, summary, transactions] = await Promise.all([
    getAccount(id),
    getAccountSummary(id),
    listTransactions(id),
  ])
  return { detail, summary, transactions }
}
