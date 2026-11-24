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
    // Screens are driven through whole forms, and a coverage run instruments every module:
    // leave room beyond the default five seconds on a busy machine.
    testTimeout: 10000,
    // `npm run test:coverage` measures the app code and fails under the thresholds.
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/**/testData.ts',
        'src/**/testRender.tsx',
        'src/**/*.d.ts',
        // Mounts the app into index.html; nothing to unit test.
        'src/main.tsx',
      ],
      reporter: ['text-summary', 'text', 'html'],
      reportsDirectory: 'coverage',
      // The project's threshold: the run fails if any of them drops below it.
      thresholds: { statements: 95, branches: 95, functions: 95, lines: 95 },
    },
  },
})
