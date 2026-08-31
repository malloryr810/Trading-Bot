import { describe, expect, it } from 'vitest'
import {
  accountPositionsLabel,
  heldTickers,
  priceWarningsSummary,
  toTradeRequest,
  transactionTypeLabel,
  transactionTypeTone,
  validateAccountForm,
  validateTradeForm,
} from './paperTrading'
import type { PricedPaperPosition } from '../types/paperTrading'

function position(
  overrides: Partial<PricedPaperPosition> = {},
): PricedPaperPosition {
  return {
    position_id: 1,
    ticker: 'AAPL',
    quantity: 10,
    average_cost: 150,
    cost_basis: 1500,
    price_available: true,
    latest_price: 162,
    market_value: 1620,
    unrealized_gain_loss: 120,
    unrealized_gain_loss_percent: 8,
    ...overrides,
  }
}

describe('transactionTypeLabel', () => {
  it('renders BUY and SELL as readable labels', () => {
    expect(transactionTypeLabel('BUY')).toBe('Buy')
    expect(transactionTypeLabel('SELL')).toBe('Sell')
  })

  it('passes an unrecognised type through unchanged', () => {
    expect(transactionTypeLabel('TRANSFER')).toBe('TRANSFER')
  })
})

describe('transactionTypeTone', () => {
  it('maps the two known types to their own modifier', () => {
    expect(transactionTypeTone('BUY')).toBe('buy')
    expect(transactionTypeTone('sell')).toBe('sell')
  })

  it('falls back to a neutral modifier for anything else', () => {
    expect(transactionTypeTone('TRANSFER')).toBe('other')
  })
})

describe('accountPositionsLabel', () => {
  it('singularises one position', () => {
    expect(accountPositionsLabel(1)).toBe('1 position')
  })

  it('pluralises zero and many', () => {
    expect(accountPositionsLabel(0)).toBe('0 positions')
    expect(accountPositionsLabel(4)).toBe('4 positions')
  })
})

describe('priceWarningsSummary', () => {
  it('returns null when every position could be priced', () => {
    expect(priceWarningsSummary([])).toBeNull()
  })

  it('names the affected tickers and says values are not zero', () => {
    const note = priceWarningsSummary([
      { ticker: 'AAPL', message: 'No price.' },
      { ticker: 'MSFT', message: 'No price.' },
    ])
    expect(note).toContain('AAPL, MSFT')
    expect(note).toContain('2 positions')
    expect(note).toContain('not zero')
  })

  it('singularises a lone warning', () => {
    expect(priceWarningsSummary([{ ticker: 'AAPL', message: 'x' }])).toContain(
      '1 position',
    )
  })
})

describe('heldTickers', () => {
  it('lists the tickers of open positions', () => {
    expect(
      heldTickers([position(), position({ position_id: 2, ticker: 'MSFT' })]),
    ).toEqual(['AAPL', 'MSFT'])
  })

  it('returns an empty list when nothing is held', () => {
    expect(heldTickers([])).toEqual([])
  })
})

describe('validateAccountForm', () => {
  it('accepts a name and a positive starting cash', () => {
    const result = validateAccountForm({
      name: 'Practice',
      startingCash: '10000',
    })
    expect(result).toEqual({ valid: true, errors: {} })
  })

  it('requires a name', () => {
    const result = validateAccountForm({ name: '   ', startingCash: '100' })
    expect(result.valid).toBe(false)
    expect(result.errors.name).toBeDefined()
  })

  it('rejects blank, non-numeric, zero, and negative starting cash', () => {
    for (const startingCash of ['', 'abc', '0', '-5']) {
      const result = validateAccountForm({ name: 'Practice', startingCash })
      expect(result.valid).toBe(false)
      expect(result.errors.startingCash).toBeDefined()
    }
  })
})

describe('validateTradeForm', () => {
  it('accepts a ticker with a positive quantity and price', () => {
    const result = validateTradeForm({
      ticker: 'AAPL',
      quantity: '10',
      price: '150.25',
    })
    expect(result).toEqual({ valid: true, errors: {} })
  })

  it('requires a ticker', () => {
    const result = validateTradeForm({ ticker: '', quantity: '1', price: '1' })
    expect(result.errors.ticker).toBeDefined()
  })

  it('rejects a non-positive quantity', () => {
    for (const quantity of ['', 'abc', '0', '-1']) {
      const result = validateTradeForm({ ticker: 'AAPL', quantity, price: '1' })
      expect(result.valid).toBe(false)
      expect(result.errors.quantity).toBeDefined()
    }
  })

  it('rejects a non-positive price', () => {
    for (const price of ['', 'abc', '0', '-1']) {
      const result = validateTradeForm({ ticker: 'AAPL', quantity: '1', price })
      expect(result.valid).toBe(false)
      expect(result.errors.price).toBeDefined()
    }
  })

  it('does not check affordability — cash and share limits are the backend rule', () => {
    const result = validateTradeForm({
      ticker: 'AAPL',
      quantity: '1000000',
      price: '999999',
    })
    expect(result.valid).toBe(true)
  })
})

describe('toTradeRequest', () => {
  it('normalises the ticker and trims decimal strings without parsing them', () => {
    expect(
      toTradeRequest({
        ticker: '  aapl ',
        quantity: ' 10.500 ',
        price: ' 150.2500 ',
      }),
    ).toEqual({ ticker: 'AAPL', quantity: '10.500', price: '150.2500' })
  })
})
