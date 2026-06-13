import { defineConfig } from 'vitest/config'

// Lightweight unit-test setup for pure frontend logic (no DOM / browser).
// Component and e2e tests are intentionally out of scope for this harness.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
