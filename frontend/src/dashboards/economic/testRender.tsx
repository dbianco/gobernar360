import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { COURSES, FINANCE, FOOD, INDUSTRY, MICROCREDITS, SHOP, TOOLS, TRAINING } from './testData'

export const BASE = '/dashboards/economic'

/** Mock the municipality's lists and tools; returns the requests each one received. */
export function mockParameters() {
  return {
    actorTypes: mockApi('get', `${BASE}/actor-types`, [SHOP, INDUSTRY]),
    sectors: mockApi('get', `${BASE}/sectors`, [FOOD]),
    categories: mockApi('get', `${BASE}/tool-categories`, [TRAINING, FINANCE]),
    subcategories: mockApi('get', `${BASE}/tool-subcategories`, [COURSES, MICROCREDITS]),
    tools: mockApi('get', `${BASE}/tools`, TOOLS),
  }
}

/** Render an economic screen for a member with the given level. */
export function renderEconomic(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string } = {},
) {
  const requests = mockParameters()
  const view = renderApp(ui, {
    me: makeMe({ dashboards: { economic: options.level ?? 'editor' } }),
    route: options.route ?? '/d/economic',
  })
  return { ...view, requests }
}
