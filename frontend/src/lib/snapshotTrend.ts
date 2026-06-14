/**
 * Pure transform from saved watchlist snapshot summaries into trend-chart data.
 *
 * Display-only: it reuses the `success_count` that the backend already saved on
 * each snapshot. No analysis, scoring, or re-derivation of financial values.
 */

import type { WatchlistSnapshotSummary } from '../types/watchlist'

/** A single point on the snapshot success-count trend line. */
export interface SnapshotTrendPoint {
  /** UTC timestamp in whole seconds (Lightweight Charts time format). */
  time: number
  /** Successful ticker count recorded in the snapshot. */
  value: number
}

/**
 * Build a chronological success-count series from saved snapshot summaries.
 *
 * - Drops snapshots whose `analyzed_at` is unparseable or whose `success_count`
 *   is missing or non-finite, so the chart never renders gaps or `NaN`.
 * - Sorts ascending by time (the list endpoint returns newest first).
 * - Collapses duplicate timestamps, keeping the last value, because Lightweight
 *   Charts requires strictly ascending, unique times.
 * - Does not mutate the input array.
 */
export function toSnapshotSuccessTrendData(
  snapshots: readonly WatchlistSnapshotSummary[],
): SnapshotTrendPoint[] {
  const points: SnapshotTrendPoint[] = []
  for (const snap of snapshots) {
    const ms = Date.parse(snap.analyzed_at)
    if (Number.isNaN(ms)) continue
    if (
      typeof snap.success_count !== 'number' ||
      !Number.isFinite(snap.success_count)
    ) {
      continue
    }
    points.push({ time: Math.floor(ms / 1000), value: snap.success_count })
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
