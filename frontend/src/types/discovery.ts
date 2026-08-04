/**
 * TypeScript interfaces mirroring the backend discovery schemas.
 * Display-layer types only — no screening, ranking, or scoring logic here.
 *
 * Source of truth: app/models/discovery.py, app/models/universe.py
 */

export type DiscoveryMode =
  | 'overall'
  | 'momentum'
  | 'quality'
  | 'value'
  | 'defensive'
  | 'avoid'

export type DiscoveryStage = 'prescreen' | 'analysis'

export interface DiscoveryModeInfo {
  key: DiscoveryMode
  label: string
  description: string
  ranking: string
}

export interface DiscoveryUniverseInfo {
  key: string
  name: string
  description: string
  size: number
}

export interface DiscoveryCandidate {
  ticker: string
  company_name: string | null
  sector: string | null
  industry: string | null
  mode: DiscoveryMode
  rank: number
  match_reason: string
  final_category: string
  score: number
  confidence_level: string
  current_price: number | null
  technical_score: number
  fundamental_score: number
  news_score: number
  risk_score: number
  technical_summary: string | null
  fundamental_summary: string | null
  news_summary: string | null
  risk_summary: string | null
  key_positive_factors: string[]
  key_risks: string[]
  buy_trigger: string | null
  sell_or_avoid_trigger: string | null
  data_timestamp: string | null
  data_sources_used: string[]
}

export interface DiscoveryWarning {
  ticker: string
  stage: DiscoveryStage
  message: string
}

export interface DiscoveryRun {
  mode: DiscoveryMode
  universe: string
  universe_name: string
  limit: number
  max_full_analysis: number
  universe_size: number
  prescreened_count: number
  shortlist_count: number
  analyzed_count: number
  results: DiscoveryCandidate[]
  warnings: DiscoveryWarning[]
  started_at: string
  completed_at: string
  data_sources_used: string[]
}

/** Query parameters accepted by GET /api/discovery. */
export interface DiscoveryQuery {
  mode: DiscoveryMode
  universe: string
  limit: number
  maxFullAnalysis: number
}
