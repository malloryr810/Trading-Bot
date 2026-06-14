import { describe, expect, test } from 'vitest'
import { pickPrimarySummary } from './watchlist'
import type { StockReport } from '../types/report'

function makeReport(overrides: Partial<StockReport>): StockReport {
  return {
    ticker: 'AAPL',
    company_name: 'Apple Inc.',
    current_price: 100,
    final_category: 'Watchlist',
    score: 60,
    confidence_level: 'medium',
    technical_summary: null,
    fundamental_summary: null,
    news_summary: null,
    risk_summary: null,
    key_positive_factors: [],
    key_risks: [],
    buy_trigger: null,
    sell_or_avoid_trigger: null,
    data_timestamp: null,
    data_sources_used: [],
    ...overrides,
  }
}

describe('pickPrimarySummary', () => {
  test('returns null when no summaries are present', () => {
    expect(pickPrimarySummary(makeReport({}))).toBeNull()
  })

  test('prefers technical summary first', () => {
    const report = makeReport({
      technical_summary: 'Tech up',
      fundamental_summary: 'Fundies ok',
    })
    expect(pickPrimarySummary(report)).toBe('Tech up')
  })

  test('falls back through fundamental, news, then risk', () => {
    expect(pickPrimarySummary(makeReport({ fundamental_summary: 'F' }))).toBe('F')
    expect(pickPrimarySummary(makeReport({ news_summary: 'N' }))).toBe('N')
    expect(pickPrimarySummary(makeReport({ risk_summary: 'R' }))).toBe('R')
  })

  test('ignores blank/whitespace-only summaries', () => {
    const report = makeReport({
      technical_summary: '   ',
      fundamental_summary: 'Real summary',
    })
    expect(pickPrimarySummary(report)).toBe('Real summary')
  })

  test('trims the returned summary', () => {
    expect(pickPrimarySummary(makeReport({ technical_summary: '  hi  ' }))).toBe('hi')
  })
})
