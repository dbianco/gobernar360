import { expect, it } from 'vitest'

const sources = import.meta.glob('../**/*.tsx', { query: '?raw', import: 'default', eager: true })

it('never uses the date field of the browser, which shows dates in its own language', () => {
  const native = Object.entries(sources)
    .filter(([path]) => !path.includes('.test.'))
    .filter(([, source]) => /type="(date|datetime-local|month|week)"/.test(source as string))
    .map(([path]) => path)

  // Use <DateField>, which always shows DD/MM/YYYY.
  expect(native).toEqual([])
})
