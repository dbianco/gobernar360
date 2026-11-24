import { expect, it } from 'vitest'

import locale from '../../locales/es-AR.json'

it('describes every indicator that has a name, and only those', () => {
  const names = Object.keys(locale.overview.indicators).sort()
  const descriptions = locale.overview.descriptions as Record<string, string>

  expect(Object.keys(descriptions).sort()).toEqual(names)
  expect(names.filter((key) => !descriptions[key]?.trim())).toEqual([])
})
