/** Pure display-ordering helpers — no scoring logic, just sorting by a field. */

/**
 * Return a new array sorted by `score` descending (highest first).
 *
 * Display-only: it orders items by the backend-provided `score` and never
 * recomputes it. The input array is not mutated. Ties preserve input order
 * (Array.prototype.sort is stable).
 */
export function sortByScoreDesc<T extends { score: number }>(
  items: readonly T[],
): T[] {
  return [...items].sort((a, b) => b.score - a.score)
}
