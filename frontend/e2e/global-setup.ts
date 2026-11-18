import { execFileSync } from 'node:child_process'
import path from 'node:path'

import { backendEnv } from '../playwright.config.ts'

/** Migrate the end-to-end database and load a fresh copy of the demo data. */
export default function globalSetup() {
  const options = {
    cwd: path.resolve(import.meta.dirname, '../../backend'),
    env: { ...process.env, ...backendEnv },
    stdio: 'inherit' as const,
  }
  execFileSync('uv', ['run', 'alembic', 'upgrade', 'head'], options)
  execFileSync('uv', ['run', 'gobernar360', 'seed-demo', '--reset'], options)
}
