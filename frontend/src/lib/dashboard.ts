/**
 * Pure display-only aggregation helpers for the dashboard.
 *
 * These count and group values the backend already produced (e.g. the
 * `category` from `final_category`). They never recompute ratings, scores, or
 * categories — that logic lives only in the backend scoring engine.
 */

export interface CategoryCount {
  category: string
  count: number
}

/**
 * Count how many items fall into each backend-provided `category`.
 *
 * Returns a new array ordered by count descending, then category name
 * ascending for stable ties. The input is not mutated.
 */
export function countByCategory(
  items: readonly { category: string }[],
): CategoryCount[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    counts.set(item.category, (counts.get(item.category) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count || a.category.localeCompare(b.category))
}

/** Sum a numeric field across items (e.g. total tickers across watchlists). */
export function sumBy<T>(items: readonly T[], pick: (item: T) => number): number {
  return items.reduce((total, item) => total + pick(item), 0)
}
