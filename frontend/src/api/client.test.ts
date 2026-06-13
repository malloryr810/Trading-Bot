import { describe, expect, it } from 'vitest'
import { extractErrorMessage } from './client'

describe('extractErrorMessage', () => {
  it('uses a string detail directly (raised HTTPException)', () => {
    const body = { detail: 'Watchlist 999 not found.' }
    expect(extractErrorMessage(body, 404)).toBe('Watchlist 999 not found.')
  })

  it('extracts the msg from a FastAPI validation array (422)', () => {
    const body = {
      detail: [
        { loc: ['body', 'ticker'], msg: 'Field required', type: 'missing' },
      ],
    }
    expect(extractErrorMessage(body, 422)).toBe('Field required')
  })

  it('joins multiple validation messages with "; "', () => {
    const body = { detail: [{ msg: 'first error' }, { msg: 'second error' }] }
    expect(extractErrorMessage(body, 422)).toBe('first error; second error')
  })

  it('falls back to the status message for an unknown JSON shape', () => {
    expect(extractErrorMessage({ foo: 'bar' }, 500)).toBe(
      'Request failed (HTTP 500).',
    )
  })

  it('falls back to the status message for a non-JSON / null body', () => {
    expect(extractErrorMessage(null, 500)).toBe('Request failed (HTTP 500).')
  })

  it('falls back when detail is a blank string', () => {
    expect(extractErrorMessage({ detail: '   ' }, 400)).toBe(
      'Request failed (HTTP 400).',
    )
  })

  it('falls back when a validation array has no usable msg fields', () => {
    expect(extractErrorMessage({ detail: [{ loc: ['x'] }] }, 422)).toBe(
      'Request failed (HTTP 422).',
    )
  })

  it('includes the actual status code in the fallback', () => {
    expect(extractErrorMessage(undefined, 503)).toBe(
      'Request failed (HTTP 503).',
    )
  })
})
