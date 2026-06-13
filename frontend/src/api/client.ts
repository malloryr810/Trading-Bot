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

export async function get<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`)
  } catch {
    throw new ApiError(0, 'Backend unavailable. Is the FastAPI server running?')
  }
  if (!response.ok) {
    const body: { detail?: string } = await response.json().catch(() => ({}))
    throw new ApiError(response.status, body.detail ?? `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

async function sendJson<T>(
  method: 'POST' | 'PATCH',
  path: string,
  body: unknown,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Backend unavailable. Is the FastAPI server running?')
  }
  if (!response.ok) {
    const errorBody: { detail?: string } = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      errorBody.detail ?? `HTTP ${response.status}`,
    )
  }
  return response.json() as Promise<T>
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>('POST', path, body)
}

export async function patch<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>('PATCH', path, body)
}

export async function del<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' })
  } catch {
    throw new ApiError(0, 'Backend unavailable. Is the FastAPI server running?')
  }
  if (!response.ok) {
    const errorBody: { detail?: string } = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      errorBody.detail ?? `HTTP ${response.status}`,
    )
  }
  return response.json() as Promise<T>
}
