import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { BENEFITS, FOOD, HOUSING, INTERVIEW, VISIT } from './testData'

export const BASE = '/dashboards/social'

/** Mock the municipality's catalogs; returns the requests each one received. */
export function mockParameters() {
  return {
    categories: mockApi('get', `${BASE}/benefit-categories`, [FOOD, HOUSING]),
    benefits: mockApi('get', `${BASE}/benefits`, BENEFITS),
    interventionTypes: mockApi('get', `${BASE}/intervention-types`, [INTERVIEW, VISIT]),
  }
}

/** Render a social screen for a member with the given level. */
export function renderSocial(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string } = {},
) {
  const requests = mockParameters()
  const view = renderApp(ui, {
    me: makeMe({ dashboards: { social: options.level ?? 'editor' } }),
    route: options.route ?? '/d/social',
  })
  return { ...view, requests }
}
