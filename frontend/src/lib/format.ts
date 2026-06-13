/** Display helpers — pure formatting, no business logic. */

/**
 * Format an ISO timestamp for display in the user's locale.
 * Returns an em dash for missing values and the raw string if parsing fails.
 */
export function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
