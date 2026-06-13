import { ApiError } from '../api/client'

/**
 * Surface a user-facing message from an unknown thrown value.
 * Uses the backend-provided message for ApiError, otherwise a page-specific
 * fallback. Keeps error handling consistent across pages.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}
