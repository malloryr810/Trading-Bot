import { describe, expect, test } from 'vitest'
import {
  toSnapshotAverageScoreTrendData,
  toSnapshotSuccessTrendData,
} from './snapshotTrend'
import type { WatchlistSnapshotSummary } from '../types/watchlist'

function snapshot(
  overrides: Partial<WatchlistSnapshotSummary> & {
    id: number
    analyzed_at: string
  },
): WatchlistSnapshotSummary {
  return {
    watchlist_id: 1,
    watchlist_name: 'Test',
    total_tickers: 5,
    success_count: 0,
    failure_count: 0,
    average_score: null,
    created_at: overrides.analyzed_at,
    ...overrides,
  }
}

describe('toSnapshotSuccessTrendData', () => {
  test('returns empty array for no snapshots', () => {
    expect(toSnapshotSuccessTrendData([])).toEqual([])
  })

  test('maps analyzed_at to seconds and success_count to value', () => {
    const result = toSnapshotSuccessTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', success_count: 4 }),
    ])
    expect(result).toEqual([{ time: Date.parse('2025-06-10T00:00:00Z') / 1000, value: 4 }])
  })

  test('sorts ascending by time (list arrives newest first)', () => {
    const result = toSnapshotSuccessTrendData([
      snapshot({ id: 2, analyzed_at: '2025-06-12T00:00:00Z', success_count: 5 }),
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', success_count: 3 }),
    ])
    expect(result.map((p) => p.value)).toEqual([3, 5])
    expect(result[0].time).toBeLessThan(result[1].time)
  })

  test('drops snapshots with unparseable timestamps', () => {
    const result = toSnapshotSuccessTrendData([
      snapshot({ id: 1, analyzed_at: 'not-a-date', success_count: 4 }),
      snapshot({ id: 2, analyzed_at: '2025-06-11T00:00:00Z', success_count: 2 }),
    ])
    expect(result).toEqual([{ time: Date.parse('2025-06-11T00:00:00Z') / 1000, value: 2 }])
  })

  test('drops snapshots with non-finite success_count', () => {
    const result = toSnapshotSuccessTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', success_count: Number.NaN }),
      snapshot({ id: 2, analyzed_at: '2025-06-11T00:00:00Z', success_count: 2 }),
    ])
    expect(result.map((p) => p.value)).toEqual([2])
  })

  test('collapses duplicate timestamps, keeping the last value', () => {
    const result = toSnapshotSuccessTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T12:00:00Z', success_count: 3 }),
      snapshot({ id: 2, analyzed_at: '2025-06-10T12:00:00Z', success_count: 4 }),
    ])
    expect(result).toEqual([{ time: Date.parse('2025-06-10T12:00:00Z') / 1000, value: 4 }])
  })

  test('does not mutate the input array', () => {
    const input = [
      snapshot({ id: 2, analyzed_at: '2025-06-12T00:00:00Z', success_count: 5 }),
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', success_count: 3 }),
    ]
    const before = [...input]
    toSnapshotSuccessTrendData(input)
    expect(input).toEqual(before)
  })
})

describe('toSnapshotAverageScoreTrendData', () => {
  test('returns empty array for no snapshots', () => {
    expect(toSnapshotAverageScoreTrendData([])).toEqual([])
  })

  test('maps analyzed_at to seconds and average_score to value', () => {
    const result = toSnapshotAverageScoreTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', average_score: 55 }),
    ])
    expect(result).toEqual([
      { time: Date.parse('2025-06-10T00:00:00Z') / 1000, value: 55 },
    ])
  })

  test('sorts ascending by time (list arrives newest first)', () => {
    const result = toSnapshotAverageScoreTrendData([
      snapshot({ id: 2, analyzed_at: '2025-06-12T00:00:00Z', average_score: 70 }),
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', average_score: 40 }),
    ])
    expect(result.map((p) => p.value)).toEqual([40, 70])
  })

  test('drops snapshots with null average_score', () => {
    const result = toSnapshotAverageScoreTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', average_score: null }),
      snapshot({ id: 2, analyzed_at: '2025-06-11T00:00:00Z', average_score: 62.5 }),
    ])
    expect(result).toEqual([
      { time: Date.parse('2025-06-11T00:00:00Z') / 1000, value: 62.5 },
    ])
  })

  test('drops snapshots with unparseable timestamps', () => {
    const result = toSnapshotAverageScoreTrendData([
      snapshot({ id: 1, analyzed_at: 'nope', average_score: 50 }),
      snapshot({ id: 2, analyzed_at: '2025-06-11T00:00:00Z', average_score: 30 }),
    ])
    expect(result.map((p) => p.value)).toEqual([30])
  })

  test('collapses duplicate timestamps, keeping the last value', () => {
    const result = toSnapshotAverageScoreTrendData([
      snapshot({ id: 1, analyzed_at: '2025-06-10T12:00:00Z', average_score: 30 }),
      snapshot({ id: 2, analyzed_at: '2025-06-10T12:00:00Z', average_score: 45 }),
    ])
    expect(result).toEqual([
      { time: Date.parse('2025-06-10T12:00:00Z') / 1000, value: 45 },
    ])
  })

  test('does not mutate the input array', () => {
    const input = [
      snapshot({ id: 2, analyzed_at: '2025-06-12T00:00:00Z', average_score: 70 }),
      snapshot({ id: 1, analyzed_at: '2025-06-10T00:00:00Z', average_score: 40 }),
    ]
    const before = [...input]
    toSnapshotAverageScoreTrendData(input)
    expect(input).toEqual(before)
  })
})
