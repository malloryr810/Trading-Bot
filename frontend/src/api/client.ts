/**
 * Base API client.
 *
 * Builds URLs from VITE_API_BASE_URL (defaults to http://127.0.0.1:8000).
 * All responses are expected to be JSON. Non-2xx responses throw ApiError.
 * Network failures (backend unreachable) also throw ApiError with status 0.
 */

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ValidationErrorItem {
  msg?: string
}

/**
 * Turn a parsed error body into a readable message.
 *
 * FastAPI returns `detail` as a plain string for our raised HTTPExceptions, but
 * as an array of `{loc, msg, type}` objects for request-validation (422) errors.
 * Handle both so the UI never shows "[object Object]".
 */
function extractErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item): string | null =>
          item &&
          typeof item === 'object' &&
          typeof (item as ValidationErrorItem).msg === 'string'
            ? (item as ValidationErrorItem).msg!
            : null,
        )
        .filter((m): m is string => m !== null)
      if (messages.length > 0) {
        return messages.join('; ')
      }
    }
  }
  return `Request failed (HTTP ${status}).`
}

/** Single fetch + error-handling path shared by every verb. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(0, 'Backend unavailable. Is the FastAPI server running?')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, extractErrorMessage(body, response.status))
  }
  return response.json() as Promise<T>
}

function jsonInit(method: 'POST' | 'PATCH', body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, jsonInit('POST', body))
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, jsonInit('PATCH', body))
}

export function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}
