import { describe, expect, it } from 'vitest'
import {
  buildDiscoveryQuery,
  candidateSubtitle,
  categoryTone,
  clampLimit,
  emptyResultsMessage,
  formatPrice,
  formatScore,
  modeLabel,
  runSummary,
  warningsSummary,
} from './discovery'
import type {
  DiscoveryCandidate,
  DiscoveryRun,
  DiscoveryWarning,
} from '../types/discovery'

function candidate(
  overrides: Partial<DiscoveryCandidate> = {},
): DiscoveryCandidate {
  return {
    ticker: 'AAPL',
    company_name: 'Apple Inc.',
    sector: 'Technology',
    industry: 'Consumer Electronics',
    mode: 'overall',
    rank: 1,
    match_reason: 'Composite score 72.0/100.',
    final_category: 'Buy Candidate',
    score: 72,
    confidence_level: 'medium',
    current_price: 190.5,
    technical_score: 70,
    fundamental_score: 65,
    news_score: 55,
    risk_score: 60,
    technical_summary: null,
    fundamental_summary: null,
    news_summary: null,
    risk_summary: null,
    key_positive_factors: [],
    key_risks: [],
    buy_trigger: null,
    sell_or_avoid_trigger: null,
    data_timestamp: null,
    data_sources_used: ['yfinance'],
    ...overrides,
  }
}

function run(overrides: Partial<DiscoveryRun> = {}): DiscoveryRun {
  return {
    mode: 'overall',
    universe: 'starter_large_cap',
    universe_name: 'Starter large cap (US)',
    limit: 10,
    max_full_analysis: 25,
    universe_size: 48,
    prescreened_count: 25,
    shortlist_count: 25,
    analyzed_count: 24,
    results: [candidate()],
    warnings: [],
    started_at: '2026-08-03T12:00:00Z',
    completed_at: '2026-08-03T12:01:00Z',
    data_sources_used: ['yfinance'],
    ...overrides,
  }
}

function warning(overrides: Partial<DiscoveryWarning> = {}): DiscoveryWarning {
  return { ticker: 'XYZ', stage: 'prescreen', message: 'No usable history.', ...overrides }
}

describe('modeLabel', () => {
  it('labels every supported mode', () => {
    expect(modeLabel('overall')).toBe('Overall')
    expect(modeLabel('momentum')).toBe('Momentum')
    expect(modeLabel('avoid')).toBe('Avoid / caution')
  })
})

describe('buildDiscoveryQuery', () => {
  it('maps camelCase controls onto the backend query names', () => {
    const query = buildDiscoveryQuery({
      mode: 'momentum',
      universe: 'starter_large_cap',
      limit: 5,
      maxFullAnalysis: 20,
    })
    expect(query).toBe(
      'mode=momentum&universe=starter_large_cap&limit=5&max_full_analysis=20',
    )
  })

  it('encodes universe keys safely', () => {
    const query = buildDiscoveryQuery({
      mode: 'overall',
      universe: 'a b',
      limit: 1,
      maxFullAnalysis: 1,
    })
    expect(query).toContain('universe=a+b')
  })
})

describe('clampLimit', () => {
  it('keeps a limit within the analysis budget', () => {
    expect(clampLimit(5, 25)).toBe(5)
  })

  it('caps a limit that exceeds the analysis budget', () => {
    expect(clampLimit(25, 10)).toBe(10)
  })

  it('never returns less than one', () => {
    expect(clampLimit(0, 25)).toBe(1)
    expect(clampLimit(-3, 25)).toBe(1)
  })

  it('handles a non-finite limit', () => {
    expect(clampLimit(Number.NaN, 25)).toBe(1)
  })
})

describe('formatScore / formatPrice', () => {
  it('formats a score to one decimal', () => {
    expect(formatScore(72.456)).toBe('72.5')
  })

  it('renders a missing score as an em dash', () => {
    expect(formatScore(null)).toBe('—')
  })

  it('formats a price with two decimals', () => {
    expect(formatPrice(190.5)).toBe('$190.50')
  })

  it('renders a missing price as an em dash', () => {
    expect(formatPrice(null)).toBe('—')
  })
})

describe('categoryTone', () => {
  it('treats buy categories as positive', () => {
    expect(categoryTone('Strong Buy Candidate')).toBe('positive')
    expect(categoryTone('Buy Candidate')).toBe('positive')
  })

  it('treats avoid and sell categories as negative', () => {
    expect(categoryTone('Avoid')).toBe('negative')
    expect(categoryTone('Sell / Exit Warning')).toBe('negative')
  })

  it('treats everything else as neutral', () => {
    expect(categoryTone('Watchlist')).toBe('neutral')
    expect(categoryTone('Hold')).toBe('neutral')
  })
})

describe('candidateSubtitle', () => {
  it('joins the available identity fields', () => {
    expect(candidateSubtitle(candidate())).toBe(
      'Apple Inc. · Technology · Consumer Electronics',
    )
  })

  it('skips missing fields', () => {
    expect(
      candidateSubtitle(candidate({ sector: null, industry: null })),
    ).toBe('Apple Inc.')
  })

  it('returns an empty string when nothing is available', () => {
    expect(
      candidateSubtitle(
        candidate({ company_name: null, sector: null, industry: null }),
      ),
    ).toBe('')
  })
})

describe('runSummary', () => {
  it('reports how many results are shown out of those analyzed', () => {
    expect(runSummary(run())).toContain('Showing 1 of 24 fully analyzed candidates')
  })

  it('names the universe and the analysis bound', () => {
    const summary = runSummary(run())
    expect(summary).toContain('Starter large cap (US)')
    expect(summary).toContain('48 tickers')
    expect(summary).toContain('25 deep')
  })

  it('uses the singular for a single analyzed candidate', () => {
    expect(runSummary(run({ analyzed_count: 1 }))).toContain('1 fully analyzed candidate ')
  })
})

describe('emptyResultsMessage', () => {
  it('points at the warnings when everything was skipped', () => {
    const message = emptyResultsMessage(run({ results: [], warnings: [warning()] }))
    expect(message).toContain('warnings below')
  })

  it('suggests other options when there is nothing to explain', () => {
    const message = emptyResultsMessage(run({ results: [], warnings: [] }))
    expect(message).toContain('different mode')
  })
})

describe('warningsSummary', () => {
  it('counts pre-screen and analysis skips separately', () => {
    const warnings = [
      warning(),
      warning({ ticker: 'ABC' }),
      warning({ ticker: 'DEF', stage: 'analysis' }),
    ]
    expect(warningsSummary(warnings)).toBe('3 tickers skipped (2 pre-screen, 1 analysis)')
  })

  it('omits a stage with no skips', () => {
    expect(warningsSummary([warning({ stage: 'analysis' })])).toBe(
      '1 ticker skipped (1 analysis)',
    )
  })
})
