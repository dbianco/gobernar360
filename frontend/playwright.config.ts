import { defineConfig } from '@playwright/test'

// End-to-end tests run their own API and web server against a dedicated database,
// which is wiped and re-seeded on every run. Ports differ from the dev servers.
const API_PORT = 8001
const WEB_PORT = 5174
const DATABASE = 'localhost:5434/gobernar360_e2e'

export const backendEnv = {
  GOBERNAR360_DATABASE_URL: `postgresql+psycopg://gobernar360_app:gobernar360_app@${DATABASE}`,
  GOBERNAR360_ADMIN_DATABASE_URL: `postgresql+psycopg://gobernar360:gobernar360@${DATABASE}`,
}

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  // Tests share one seeded database and some of them change it.
  workers: 1,
  fullyParallel: false,
  reporter: 'list',
  use: { baseURL: `http://localhost:${WEB_PORT}`, trace: 'retain-on-failure' },
  webServer: [
    {
      command: `uv run uvicorn gobernar360.main:create_app --factory --port ${API_PORT}`,
      cwd: '../backend',
      env: backendEnv,
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --port ${WEB_PORT}`,
      env: { GOBERNAR360_API_URL: `http://localhost:${API_PORT}` },
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
    },
  ],
})
