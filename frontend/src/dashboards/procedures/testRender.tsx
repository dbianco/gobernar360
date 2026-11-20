import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { OBRAS, RENAPER, RENTAS, RENTAS_SOURCE, REQUIREMENTS } from './testData'

export const BASE = '/dashboards/procedures'

/** Mock the municipality's areas, sources and requirements; returns the requests received. */
export function mockCatalog() {
  return {
    areas: mockApi('get', `${BASE}/areas`, [OBRAS, RENTAS]),
    sources: mockApi('get', `${BASE}/sources`, [RENAPER, RENTAS_SOURCE]),
    requirements: mockApi('get', `${BASE}/requirements`, REQUIREMENTS),
  }
}

/** Render a procedures screen for a member with the given level. */
export function renderProcedures(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string } = {},
) {
  const requests = mockCatalog()
  const view = renderApp(ui, {
    me: makeMe({ dashboards: { procedures: options.level ?? 'editor' } }),
    route: options.route ?? '/d/procedures',
  })
  return { ...view, requests }
}
