import { expect, it } from 'vitest'

import { dashboards } from './registry'

it('opens the screen of each record that has a place', () => {
  const located = dashboards.flatMap((dashboard) =>
    (dashboard.located ?? []).map((kind) => [dashboard.key, kind] as const),
  )

  expect(located.map(([key, kind]) => [key, kind.dashboard, kind.record, kind.path('x')])).toEqual([
    ['projects', 'projects', 'projects', '/d/projects/projects/x'],
    ['economic', 'economic', 'actors', '/d/economic/actors/x'],
    ['social', 'social', 'households', '/d/social/households/x'],
  ])
  // Only where a family lives is kept from viewers.
  expect(located.map(([, kind]) => kind.individualLevel)).toEqual(['viewer', 'viewer', 'editor'])
  // Every one hangs from its dashboard's own address.
  for (const [key, kind] of located) {
    const { basePath } = dashboards.find((dashboard) => dashboard.key === key)!
    expect(kind.path('x').startsWith(`${basePath}/`)).toBe(true)
  }
})
