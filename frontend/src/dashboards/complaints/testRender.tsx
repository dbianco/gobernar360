import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { CALENDAR, CENTRE, LIGHTS, NORTH, TYPES, WORKS } from './testData'

export const BASE = '/dashboards/complaints'

/** Mock the municipality's catalogs; returns the requests received. */
export function mockCatalog() {
  return {
    areas: mockApi('get', `${BASE}/areas`, [LIGHTS, WORKS]),
    zones: mockApi('get', `${BASE}/zones`, [CENTRE, NORTH]),
    types: mockApi('get', `${BASE}/types`, TYPES),
    calendar: mockApi('get', `${BASE}/calendar`, CALENDAR),
  }
}

/** Render a complaints screen for a member with the given level. */
export function renderComplaints(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string } = {},
) {
  const requests = mockCatalog()
  const view = renderApp(ui, {
    me: makeMe({ dashboards: { complaints: options.level ?? 'editor' } }),
    route: options.route ?? '/d/complaints',
  })
  return { ...view, requests }
}
