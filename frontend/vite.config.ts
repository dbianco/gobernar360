/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    host: 'localhost',
    // The API sets a same-site session cookie, so the browser must see one origin.
    proxy: { '/api': process.env.GOBERNAR360_API_URL ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    // Long form tests on a busy machine, or under coverage, can take several seconds.
    testTimeout: 15000,
    // `npm run coverage`: every source file of the app counts, tested or not.
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        // Test helpers and fixtures.
        'src/test/**',
        'src/**/testData.ts',
        'src/**/testRender.tsx',
        // Only mounts <App /> into the page; the browser tests cover it.
        'src/main.tsx',
      ],
      reporter: ['text-summary', 'text'],
      // `npm run coverage` fails below these. Branches count every `??` and `?.` fallback
      // in the templates, so their floor is lower.
      thresholds: { statements: 95, lines: 95, functions: 95, branches: 85 },
    },
  },
})
