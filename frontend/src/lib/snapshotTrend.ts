/**
 * Pure transforms from saved watchlist snapshot summaries into trend-chart data.
 *
 * Display-only: these reuse values the backend already saved/derived on each
 * snapshot (`success_count`, `average_score`). No analysis, scoring, or
 * re-derivation of financial values happens here.
 */

import type { WatchlistSnapshotSummary } from '../types/watchlist'

/** A single point on a snapshot trend line. */
export interface SnapshotTrendPoint {
  /** UTC timestamp in whole seconds (Lightweight Charts time format). */
  time: number
  /** The plotted metric value for the snapshot. */
  value: number
}

/**
 * Build a chronological trend series from saved snapshot summaries.
 *
 * - `value` is extracted per snapshot via `getValue`; snapshots whose value is
 *   missing (`null`/`undefined`) or non-finite are dropped, so the chart never
 *   renders gaps or `NaN`.
 * - Drops snapshots whose `analyzed_at` is unparseable.
 * - Sorts ascending by time (the list endpoint returns newest first).
 * - Collapses duplicate timestamps, keeping the last value, because Lightweight
 *   Charts requires strictly ascending, unique times.
 * - Does not mutate the input array.
 */
function buildTrend(
  snapshots: readonly WatchlistSnapshotSummary[],
  getValue: (snapshot: WatchlistSnapshotSummary) => number | null | undefined,
): SnapshotTrendPoint[] {
  const points: SnapshotTrendPoint[] = []
  for (const snap of snapshots) {
    const ms = Date.parse(snap.analyzed_at)
    if (Number.isNaN(ms)) continue
    const value = getValue(snap)
    if (typeof value !== 'number' || !Number.isFinite(value)) continue
    points.push({ time: Math.floor(ms / 1000), value })
  }

  points.sort((a, b) => a.time - b.time)

  const unique: SnapshotTrendPoint[] = []
  for (const point of points) {
    const last = unique[unique.length - 1]
    if (last && last.time === point.time) {
      unique[unique.length - 1] = point
    } else {
      unique.push(point)
    }
  }
  return unique
}

/** Successful-ticker count over time, from saved snapshot summaries. */
export function toSnapshotSuccessTrendData(
  snapshots: readonly WatchlistSnapshotSummary[],
): SnapshotTrendPoint[] {
  return buildTrend(snapshots, (snap) => snap.success_count)
}

/**
 * Backend-derived average score over time, from saved snapshot summaries.
 * Snapshots with a null `average_score` (no successful scored results) are
 * dropped. The frontend never computes the average itself.
 */
export function toSnapshotAverageScoreTrendData(
  snapshots: readonly WatchlistSnapshotSummary[],
): SnapshotTrendPoint[] {
  return buildTrend(snapshots, (snap) => snap.average_score)
}
