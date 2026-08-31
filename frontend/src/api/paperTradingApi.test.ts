import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import {
  createAccount,
  getAccount,
  getAccountPositions,
  getAccountSummary,
  listAccounts,
  listTransactions,
  loadAccountView,
  recordBuy,
  recordSell,
} from './paperTradingApi'
import type {
  PaperAccountDetail,
  PaperAccountSummary,
  PaperAccountSummaryResponse,
  PaperTransaction,
} from '../types/paperTrading'

/**
 * Network is mocked at the `fetch` boundary — these tests never contact the
 * backend. They assert the request the client builds and the error the client
 * surfaces, not any accounting behaviour (which lives in the backend).
 */

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

/** Path of the nth fetch call, with the configurable base URL stripped off. */
function pathOf(callIndex: number): string {
  const url = fetchMock.mock.calls[callIndex][0] as string
  return new URL(url).pathname
}

function initOf(callIndex: number): RequestInit | undefined {
  return fetchMock.mock.calls[callIndex][1] as RequestInit | undefined
}

function bodyOf(callIndex: number): unknown {
  return JSON.parse(initOf(callIndex)?.body as string)
}

const ACCOUNT: PaperAccountSummary = {
  id: 7,
  name: 'Practice account',
  starting_cash: 10000,
  cash_balance: 8500,
  realized_gain_loss: 0,
  created_at: '2026-08-30T12:00:00Z',
  updated_at: '2026-08-30T12:30:00Z',
  positions_count: 1,
}

const DETAIL: PaperAccountDetail = {
  id: 7,
  name: 'Practice account',
  starting_cash: 10000,
  cash_balance: 8500,
  realized_gain_loss: 0,
  created_at: '2026-08-30T12:00:00Z',
  updated_at: '2026-08-30T12:30:00Z',
  positions: [],
}

const SUMMARY: PaperAccountSummaryResponse = {
  account_id: 7,
  account_name: 'Practice account',
  generated_at: '2026-08-30T12:31:00Z',
  starting_cash: 10000,
  cash_balance: 8500,
  realized_gain_loss: 0,
  unrealized_gain_loss: 120,
  open_positions_value: 1620,
  total_portfolio_value: 10120,
  total_return: 120,
  total_return_percent: 1.2,
  positions_count: 1,
  priced_positions_count: 1,
  positions: [],
  warnings: [],
  has_price_warnings: false,
}

const TRANSACTION: PaperTransaction = {
  id: 3,
  account_id: 7,
  transaction_type: 'BUY',
  ticker: 'AAPL',
  quantity: 10,
  price: 150,
  gross_amount: 1500,
  realized_gain_loss: 0,
  executed_at: '2026-08-30T12:30:00Z',
  created_at: '2026-08-30T12:30:00Z',
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('account reads', () => {
  it('loads the account list from the list endpoint', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([ACCOUNT]))

    const accounts = await listAccounts()

    expect(pathOf(0)).toBe('/api/paper-trading/accounts')
    expect(initOf(0)).toBeUndefined()
    expect(accounts).toEqual([ACCOUNT])
  })

  it('fetches one account, its summary, positions, and transactions', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(DETAIL))
      .mockResolvedValueOnce(jsonResponse(SUMMARY))
      .mockResolvedValueOnce(jsonResponse({ account_id: 7, positions: [] }))
      .mockResolvedValueOnce(jsonResponse([TRANSACTION]))

    await getAccount(7)
    await getAccountSummary(7)
    await getAccountPositions(7)
    await listTransactions(7)

    expect(pathOf(0)).toBe('/api/paper-trading/accounts/7')
    expect(pathOf(1)).toBe('/api/paper-trading/accounts/7/summary')
    expect(pathOf(2)).toBe('/api/paper-trading/accounts/7/positions')
    expect(pathOf(3)).toBe('/api/paper-trading/accounts/7/transactions')
  })

  it('keeps null summary totals null rather than coercing them to zero', async () => {
    const unpriced: PaperAccountSummaryResponse = {
      ...SUMMARY,
      unrealized_gain_loss: null,
      open_positions_value: null,
      total_portfolio_value: null,
      total_return: null,
      total_return_percent: null,
      priced_positions_count: 0,
      warnings: [{ ticker: 'AAPL', message: 'No price available.' }],
      has_price_warnings: true,
    }
    fetchMock.mockResolvedValueOnce(jsonResponse(unpriced))

    const summary = await getAccountSummary(7)

    expect(summary.total_portfolio_value).toBeNull()
    expect(summary.open_positions_value).toBeNull()
    expect(summary.has_price_warnings).toBe(true)
  })
})

describe('loadAccountView', () => {
  it('issues the three account reads together and returns them keyed', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(DETAIL))
      .mockResolvedValueOnce(jsonResponse(SUMMARY))
      .mockResolvedValueOnce(jsonResponse([TRANSACTION]))

    const view = await loadAccountView(7)

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect([pathOf(0), pathOf(1), pathOf(2)]).toEqual([
      '/api/paper-trading/accounts/7',
      '/api/paper-trading/accounts/7/summary',
      '/api/paper-trading/accounts/7/transactions',
    ])
    expect(view).toEqual({
      detail: DETAIL,
      summary: SUMMARY,
      transactions: [TRANSACTION],
    })
  })

  it('does not call the positions endpoint (the summary already carries them)', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(DETAIL))
      .mockResolvedValueOnce(jsonResponse(SUMMARY))
      .mockResolvedValueOnce(jsonResponse([]))

    await loadAccountView(7)

    const paths = fetchMock.mock.calls.map((_, i) => pathOf(i))
    expect(paths.some((p) => p.endsWith('/positions'))).toBe(false)
  })
})

describe('createAccount', () => {
  it('posts the name and starting cash as sent', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(DETAIL, 201))

    const created = await createAccount({
      name: 'Practice account',
      starting_cash: '10000.00',
    })

    expect(pathOf(0)).toBe('/api/paper-trading/accounts')
    expect(initOf(0)?.method).toBe('POST')
    expect(bodyOf(0)).toEqual({
      name: 'Practice account',
      starting_cash: '10000.00',
    })
    expect(created).toEqual(DETAIL)
  })

  it('surfaces a backend validation message (400)', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Starting cash must be greater than zero.' }, 400),
    )

    await expect(
      createAccount({ name: 'Bad', starting_cash: '0' }),
    ).rejects.toMatchObject({
      status: 400,
      message: 'Starting cash must be greater than zero.',
    })
  })
})

describe('recording simulated trades', () => {
  it('posts a buy with decimal strings preserved', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(TRANSACTION, 201))

    await recordBuy(7, { ticker: 'AAPL', quantity: '10', price: '150.25' })

    expect(pathOf(0)).toBe('/api/paper-trading/accounts/7/buy')
    expect(initOf(0)?.method).toBe('POST')
    expect(bodyOf(0)).toEqual({
      ticker: 'AAPL',
      quantity: '10',
      price: '150.25',
    })
  })

  it('posts a sell to the sell endpoint', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...TRANSACTION, transaction_type: 'SELL' }, 201),
    )

    const tx = await recordSell(7, {
      ticker: 'AAPL',
      quantity: '5',
      price: '160',
    })

    expect(pathOf(0)).toBe('/api/paper-trading/accounts/7/sell')
    expect(bodyOf(0)).toEqual({ ticker: 'AAPL', quantity: '5', price: '160' })
    expect(tx.transaction_type).toBe('SELL')
  })

  it('surfaces an insufficient-cash conflict (409) with the backend message', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: 'Insufficient cash: need $1,500.00, have $500.00.' },
        409,
      ),
    )

    const error = await recordBuy(7, {
      ticker: 'AAPL',
      quantity: '10',
      price: '150',
    }).catch((err: unknown) => err)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(409)
    expect((error as ApiError).message).toBe(
      'Insufficient cash: need $1,500.00, have $500.00.',
    )
  })

  it('surfaces an insufficient-shares conflict (409) on a sell', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Account holds 2 shares of AAPL, cannot sell 5.' }, 409),
    )

    await expect(
      recordSell(7, { ticker: 'AAPL', quantity: '5', price: '160' }),
    ).rejects.toMatchObject({
      status: 409,
      message: 'Account holds 2 shares of AAPL, cannot sell 5.',
    })
  })

  it('surfaces a missing account (404)', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Paper trading account 999 not found.' }, 404),
    )

    await expect(
      recordBuy(999, { ticker: 'AAPL', quantity: '1', price: '10' }),
    ).rejects.toMatchObject({ status: 404 })
  })
})

describe('post-trade refresh', () => {
  it('refreshes the account view and the account list after a buy', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(TRANSACTION, 201)) // buy
      .mockResolvedValueOnce(jsonResponse(DETAIL)) // detail
      .mockResolvedValueOnce(jsonResponse(SUMMARY)) // summary
      .mockResolvedValueOnce(jsonResponse([TRANSACTION])) // transactions
      .mockResolvedValueOnce(jsonResponse([ACCOUNT])) // account list

    await recordBuy(7, { ticker: 'AAPL', quantity: '10', price: '150' })
    const [view, accounts] = await Promise.all([
      loadAccountView(7),
      listAccounts(),
    ])

    expect(fetchMock.mock.calls.map((_, i) => pathOf(i))).toEqual([
      '/api/paper-trading/accounts/7/buy',
      '/api/paper-trading/accounts/7',
      '/api/paper-trading/accounts/7/summary',
      '/api/paper-trading/accounts/7/transactions',
      '/api/paper-trading/accounts',
    ])
    expect(view.transactions).toHaveLength(1)
    expect(accounts).toEqual([ACCOUNT])
  })

  it('refreshes the account view and the account list after a sell', async () => {
    const sellTx: PaperTransaction = {
      ...TRANSACTION,
      id: 4,
      transaction_type: 'SELL',
      realized_gain_loss: 100,
    }
    fetchMock
      .mockResolvedValueOnce(jsonResponse(sellTx, 201)) // sell
      .mockResolvedValueOnce(jsonResponse(DETAIL)) // detail
      .mockResolvedValueOnce(jsonResponse({ ...SUMMARY, realized_gain_loss: 100 }))
      .mockResolvedValueOnce(jsonResponse([sellTx, TRANSACTION]))
      .mockResolvedValueOnce(jsonResponse([{ ...ACCOUNT, realized_gain_loss: 100 }]))

    await recordSell(7, { ticker: 'AAPL', quantity: '5', price: '160' })
    const [view, accounts] = await Promise.all([
      loadAccountView(7),
      listAccounts(),
    ])

    expect(fetchMock.mock.calls.map((_, i) => pathOf(i))).toEqual([
      '/api/paper-trading/accounts/7/sell',
      '/api/paper-trading/accounts/7',
      '/api/paper-trading/accounts/7/summary',
      '/api/paper-trading/accounts/7/transactions',
      '/api/paper-trading/accounts',
    ])
    expect(view.summary.realized_gain_loss).toBe(100)
    expect(accounts[0].realized_gain_loss).toBe(100)
  })
})

describe('transport failures', () => {
  it('reports an unreachable backend as ApiError status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(listAccounts()).rejects.toMatchObject({
      status: 0,
      message: 'Backend unavailable. Is the FastAPI server running?',
    })
  })
})
