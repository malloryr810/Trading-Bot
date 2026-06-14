import { describe, expect, test } from 'vitest'
import { countByCategory, sumBy } from './dashboard'

describe('countByCategory', () => {
  test('returns empty array for no items', () => {
    expect(countByCategory([])).toEqual([])
  })

  test('counts items grouped by category', () => {
    const result = countByCategory([
      { category: 'Buy Candidate' },
      { category: 'Watchlist' },
      { category: 'Buy Candidate' },
    ])
    expect(result).toEqual([
      { category: 'Buy Candidate', count: 2 },
      { category: 'Watchlist', count: 1 },
    ])
  })

  test('orders by count descending then category name ascending', () => {
    const result = countByCategory([
      { category: 'Zeta' },
      { category: 'Alpha' },
      { category: 'Alpha' },
      { category: 'Beta' },
      { category: 'Beta' },
    ])
    expect(result).toEqual([
      { category: 'Alpha', count: 2 },
      { category: 'Beta', count: 2 },
      { category: 'Zeta', count: 1 },
    ])
  })

  test('does not mutate the input array', () => {
    const input = [{ category: 'A' }, { category: 'B' }]
    const snapshot = [...input]
    countByCategory(input)
    expect(input).toEqual(snapshot)
  })
})

describe('sumBy', () => {
  test('returns 0 for an empty array', () => {
    expect(sumBy([], (n: number) => n)).toBe(0)
  })

  test('sums the picked field across items', () => {
    const watchlists = [{ ticker_count: 3 }, { ticker_count: 5 }, { ticker_count: 0 }]
    expect(sumBy(watchlists, (w) => w.ticker_count)).toBe(8)
  })
})
