import { describe, expect, it } from 'vitest'
import {
  analyzePath,
  formatMoney,
  formatPercent,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  gainLossTone,
  validateHoldingForm,
  type HoldingFormValues,
} from './portfolio'

function values(overrides: Partial<HoldingFormValues> = {}): HoldingFormValues {
  return {
    ticker: 'AAPL',
    shares: '10',
    averageCost: '100',
    purchaseDate: '',
    notes: '',
    ...overrides,
  }
}

describe('formatMoney', () => {
  it('formats with thousands separators and 2 decimals', () => {
    expect(formatMoney(1500)).toBe('$1,500.00')
  })

  it('renders null as an em dash', () => {
    expect(formatMoney(null)).toBe('—')
  })
})

describe('formatSignedMoney', () => {
  it('prefixes a plus for gains', () => {
    expect(formatSignedMoney(500)).toBe('+$500.00')
  })

  it('prefixes a minus for losses', () => {
    expect(formatSignedMoney(-500)).toBe('-$500.00')
  })

  it('renders null as an em dash', () => {
    expect(formatSignedMoney(null)).toBe('—')
  })
})

describe('formatPercent / formatSignedPercent', () => {
  it('formats a plain percent', () => {
    expect(formatPercent(37.5)).toBe('37.50%')
  })

  it('signs a positive return', () => {
    expect(formatSignedPercent(50)).toBe('+50.00%')
  })

  it('signs a negative return', () => {
    expect(formatSignedPercent(-12.3)).toBe('-12.30%')
  })

  it('renders null as an em dash', () => {
    expect(formatPercent(null)).toBe('—')
  })
})

describe('formatShares', () => {
  it('trims trailing zeros', () => {
    expect(formatShares(10)).toBe('10')
    expect(formatShares(10.5)).toBe('10.5')
  })
})

describe('gainLossTone', () => {
  it('classifies values', () => {
    expect(gainLossTone(1)).toBe('gain')
    expect(gainLossTone(-1)).toBe('loss')
    expect(gainLossTone(0)).toBe('flat')
    expect(gainLossTone(null)).toBe('none')
  })
})

describe('analyzePath', () => {
  it('builds an uppercased query path', () => {
    expect(analyzePath(' aapl ')).toBe('/analyze?ticker=AAPL')
  })
})

describe('validateHoldingForm', () => {
  it('accepts valid input', () => {
    expect(validateHoldingForm(values()).valid).toBe(true)
  })

  it('requires a ticker', () => {
    const result = validateHoldingForm(values({ ticker: '  ' }))
    expect(result.valid).toBe(false)
    expect(result.errors.ticker).toBeDefined()
  })

  it('rejects zero or negative shares', () => {
    expect(validateHoldingForm(values({ shares: '0' })).errors.shares).toBeDefined()
    expect(validateHoldingForm(values({ shares: '-5' })).errors.shares).toBeDefined()
  })

  it('rejects non-numeric shares', () => {
    expect(validateHoldingForm(values({ shares: 'abc' })).errors.shares).toBeDefined()
  })

  it('rejects negative average cost but allows zero', () => {
    expect(
      validateHoldingForm(values({ averageCost: '-1' })).errors.averageCost,
    ).toBeDefined()
    expect(validateHoldingForm(values({ averageCost: '0' })).valid).toBe(true)
  })

  it('accepts an empty purchase date but rejects a malformed one', () => {
    expect(validateHoldingForm(values({ purchaseDate: '' })).valid).toBe(true)
    expect(
      validateHoldingForm(values({ purchaseDate: '15-01-2025' })).errors
        .purchaseDate,
    ).toBeDefined()
  })
})
