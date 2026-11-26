import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'

import { backendEnv } from '../playwright.config.ts'

/** Migrate the end-to-end database and load a fresh copy of the demo data. */
export default function globalSetup() {
  const options = {
    cwd: path.resolve(import.meta.dirname, '../../backend'),
    env: { ...process.env, ...backendEnv },
    stdio: 'inherit' as const,
  }
  const inbox = backendEnv.GOBERNAR360_CIDI_FAKE_INBOX
  mkdirSync(path.dirname(inbox), { recursive: true })
  rmSync(inbox, { force: true })
  execFileSync('uv', ['run', 'alembic', 'upgrade', 'head'], options)
  execFileSync('uv', ['run', 'gobernar360', 'seed-demo', '--reset'], options)
}
