import { describe, expect, it } from 'vitest'
import { sortByScoreDesc } from './sort'

interface Scored {
  ticker: string
  score: number
}

describe('sortByScoreDesc', () => {
  it('orders items highest score first', () => {
    const items: Scored[] = [
      { ticker: 'A', score: 50 },
      { ticker: 'B', score: 80 },
      { ticker: 'C', score: 65 },
    ]
    expect(sortByScoreDesc(items).map((i) => i.ticker)).toEqual(['B', 'C', 'A'])
  })

  it('does not mutate the input array', () => {
    const items: Scored[] = [
      { ticker: 'A', score: 10 },
      { ticker: 'B', score: 90 },
    ]
    sortByScoreDesc(items)
    expect(items.map((i) => i.ticker)).toEqual(['A', 'B'])
  })

  it('preserves input order for equal scores (stable sort)', () => {
    const items: Scored[] = [
      { ticker: 'A', score: 60 },
      { ticker: 'B', score: 60 },
      { ticker: 'C', score: 60 },
    ]
    expect(sortByScoreDesc(items).map((i) => i.ticker)).toEqual(['A', 'B', 'C'])
  })

  it('handles negative scores predictably', () => {
    const items: Scored[] = [
      { ticker: 'A', score: -10 },
      { ticker: 'B', score: 5 },
      { ticker: 'C', score: 0 },
    ]
    expect(sortByScoreDesc(items).map((i) => i.ticker)).toEqual(['B', 'C', 'A'])
  })

  it('returns an empty array unchanged', () => {
    expect(sortByScoreDesc([])).toEqual([])
  })
})
