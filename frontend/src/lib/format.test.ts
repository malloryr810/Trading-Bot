import { describe, expect, it } from 'vitest'
import { formatDate, formatTimestamp } from './format'

describe('formatTimestamp', () => {
  it('formats a valid ISO timestamp into a non-empty localized string', () => {
    const result = formatTimestamp('2026-06-13T17:30:00Z')
    // Year is locale-independent; assert it survives formatting.
    expect(result).toContain('2026')
    expect(result).not.toBe('—')
  })

  it('returns an em-dash fallback for null', () => {
    expect(formatTimestamp(null)).toBe('—')
  })

  it('returns an em-dash fallback for an empty string', () => {
    expect(formatTimestamp('')).toBe('—')
  })

  it('does not throw on an invalid timestamp and returns a string', () => {
    expect(() => formatTimestamp('not-a-date')).not.toThrow()
    expect(typeof formatTimestamp('not-a-date')).toBe('string')
  })
})

describe('formatDate', () => {
  it('formats a valid ISO timestamp into a date string containing the year', () => {
    const result = formatDate('2026-06-13T17:30:00Z')
    // Year is locale-independent; assert it survives formatting.
    expect(result).toContain('2026')
    expect(result).not.toBe('—')
  })

  it('returns an em-dash fallback for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('returns an em-dash fallback for an empty string', () => {
    expect(formatDate('')).toBe('—')
  })

  it('does not throw on an invalid timestamp and returns a string', () => {
    expect(() => formatDate('not-a-date')).not.toThrow()
    expect(typeof formatDate('not-a-date')).toBe('string')
  })
})
