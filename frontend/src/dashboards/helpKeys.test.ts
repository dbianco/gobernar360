import { expect, it } from 'vitest'

import locale from '../locales/es-AR.json'

const sources = import.meta.glob('./**/*.tsx', { query: '?raw', import: 'default', eager: true })

function hasText(key: string): boolean {
  let node: unknown = locale
  for (const part of key.split('.')) {
    if (typeof node !== 'object' || node === null) return false
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === 'string'
}

it('has a text for every column help a dashboard table asks for', () => {
  const missing = Object.entries(sources).flatMap(([path, source]) =>
    [...(source as string).matchAll(/help=\{t\('([^']+)'\)\}/g)]
      .map((match) => match[1])
      .filter((key) => !hasText(key))
      .map((key) => `${path} ${key}`),
  )

  expect(missing).toEqual([])
})

it('explains deliveries with their own texts, not those of interventions', () => {
  const source = sources['./social/RecordTables.tsx'] as string
  const deliveries = source.slice(
    source.indexOf('function DeliveriesTable'),
    source.indexOf('function InterventionsTable'),
  )

  expect(deliveries).toContain('social.help.deliveries.date')
  expect(deliveries).not.toContain('social.help.interventions.')
})
