/**
 * Pure display helpers for the Discover page.
 *
 * These build query strings, label controls, and format values the backend
 * already produced. They never screen, rank, or score anything — ranking order
 * arrives from the API and is rendered as-is.
 */

import type {
  DiscoveryCandidate,
  DiscoveryMode,
  DiscoveryQuery,
  DiscoveryRun,
  DiscoveryWarning,
} from '../types/discovery'

/** Modes in the order they are offered in the UI. Mirrors the backend enum. */
export const DISCOVERY_MODES: DiscoveryMode[] = [
  'overall',
  'momentum',
  'quality',
  'value',
  'defensive',
  'avoid',
]

const MODE_LABELS: Record<DiscoveryMode, string> = {
  overall: 'Overall',
  momentum: 'Momentum',
  quality: 'Quality',
  value: 'Value',
  defensive: 'Defensive',
  avoid: 'Avoid / caution',
}

/** Result-count choices offered in the UI. */
export const LIMIT_CHOICES = [5, 10, 15, 20, 25] as const

export const DEFAULT_DISCOVERY_QUERY: DiscoveryQuery = {
  mode: 'overall',
  universe: 'starter_large_cap',
  limit: 10,
  maxFullAnalysis: 25,
}

/** Fallback label for a mode. The backend label is preferred when loaded. */
export function modeLabel(mode: DiscoveryMode): string {
  return MODE_LABELS[mode] ?? mode
}

/** Build the query string for GET /api/discovery (no leading `?`). */
export function buildDiscoveryQuery(query: DiscoveryQuery): string {
  return new URLSearchParams({
    mode: query.mode,
    universe: query.universe,
    limit: String(query.limit),
    max_full_analysis: String(query.maxFullAnalysis),
  }).toString()
}

/**
 * Clamp the requested result count to the analysis budget. The backend rejects
 * a limit above max_full_analysis; this keeps the controls from producing a
 * request that is guaranteed to 400.
 */
export function clampLimit(limit: number, maxFullAnalysis: number): number {
  if (!Number.isFinite(limit) || limit < 1) return 1
  return Math.min(Math.trunc(limit), Math.max(1, Math.trunc(maxFullAnalysis)))
}

/** Format a 0–100 score for display. Falsy/non-finite values render an em dash. */
export function formatScore(score: number | null): string {
  if (score === null || !Number.isFinite(score)) return '—'
  return score.toFixed(1)
}

/** Format a price for display. Null renders an em dash. */
export function formatPrice(price: number | null): string {
  if (price === null || !Number.isFinite(price)) return '—'
  return `$${price.toFixed(2)}`
}

export type CategoryTone = 'positive' | 'neutral' | 'negative'

/**
 * Classify a backend rating category for styling only. The mapping mirrors the
 * category names the scoring engine emits; it does not re-derive a category.
 */
export function categoryTone(category: string): CategoryTone {
  const normalized = category.trim().toLowerCase()
  if (normalized.includes('buy')) return 'positive'
  if (normalized.includes('avoid') || normalized.includes('sell')) return 'negative'
  return 'neutral'
}

/** Human-readable "Ticker · Sector · Industry" subtitle, skipping blanks. */
export function candidateSubtitle(candidate: DiscoveryCandidate): string {
  return [candidate.company_name, candidate.sector, candidate.industry]
    .filter((part): part is string => Boolean(part && part.trim()))
    .join(' · ')
}

/** One-line summary of a completed run's coverage, for the results header. */
export function runSummary(run: DiscoveryRun): string {
  const shown = run.results.length
  return (
    `Showing ${shown} of ${run.analyzed_count} fully analyzed ` +
    `${run.analyzed_count === 1 ? 'candidate' : 'candidates'} ` +
    `from ${run.universe_name} (${run.universe_size} tickers screened at most ` +
    `${run.max_full_analysis} deep).`
  )
}

/** Message shown when a run completed but produced no ranked candidates. */
export function emptyResultsMessage(run: DiscoveryRun): string {
  if (run.warnings.length > 0) {
    return (
      'No candidates could be analyzed in this run — every screened ticker was ' +
      'skipped. See the warnings below for the per-ticker reasons.'
    )
  }
  return 'No candidates matched this run. Try a different mode or universe.'
}

/** Short header for the warnings block, e.g. "3 tickers skipped (2 pre-screen)". */
export function warningsSummary(warnings: DiscoveryWarning[]): string {
  const prescreen = warnings.filter((w) => w.stage === 'prescreen').length
  const analysis = warnings.length - prescreen
  const parts: string[] = []
  if (prescreen > 0) parts.push(`${prescreen} pre-screen`)
  if (analysis > 0) parts.push(`${analysis} analysis`)
  const noun = warnings.length === 1 ? 'ticker' : 'tickers'
  return `${warnings.length} ${noun} skipped (${parts.join(', ')})`
}
