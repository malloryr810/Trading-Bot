import { describe, expect, test } from 'vitest'
import { toClosingLineData } from './chartData'
import type { PricePoint } from '../types/marketData'

function point(date: string, close: number | null): PricePoint {
  return { date, open: null, high: null, low: null, close, volume: null }
}

describe('toClosingLineData', () => {
  test('returns empty array for no points', () => {
    expect(toClosingLineData([])).toEqual([])
  })

  test('maps date to time and close to value', () => {
    const result = toClosingLineData([point('2025-06-10', 104), point('2025-06-11', 105.5)])
    expect(result).toEqual([
      { time: '2025-06-10', value: 104 },
      { time: '2025-06-11', value: 105.5 },
    ])
  })

  test('drops points with null close', () => {
    const result = toClosingLineData([
      point('2025-06-10', 104),
      point('2025-06-11', null),
      point('2025-06-12', 106),
    ])
    expect(result).toEqual([
      { time: '2025-06-10', value: 104 },
      { time: '2025-06-12', value: 106 },
    ])
  })

  test('preserves input order', () => {
    const result = toClosingLineData([point('2025-06-12', 3), point('2025-06-10', 1)])
    expect(result.map((p) => p.time)).toEqual(['2025-06-12', '2025-06-10'])
  })

  test('does not mutate the input array', () => {
    const input = [point('2025-06-10', 104), point('2025-06-11', null)]
    const snapshot = [...input]
    toClosingLineData(input)
    expect(input).toEqual(snapshot)
  })
})
