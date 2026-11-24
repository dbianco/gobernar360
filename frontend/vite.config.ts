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
    // Above the 5 s that waits for elements get (src/test/setup.ts).
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      // Tests and their helpers, the entry point and type-only modules are not app code.
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/**/testData.ts',
        'src/**/testRender.tsx',
        'src/main.tsx',
        'src/**/types.ts',
      ],
      reporter: ['text-summary', 'json-summary', 'json', 'html'],
      reportOnFailure: true,
      // `npm run test:coverage` fails below these.
      thresholds: { statements: 95, branches: 95, functions: 95, lines: 95 },
    },
  },
})
