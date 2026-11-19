import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { SUBCATEGORIES, VARIABLES } from './testData'
import type { Subcategory, Variable } from './types'

export const BASE = '/dashboards/environment'

/** Mock what the municipality measures; returns the requests each list received. */
export function mockParameters(
  variables: Variable[] = VARIABLES,
  subcategories: Subcategory[] = SUBCATEGORIES,
) {
  return {
    subcategories: mockApi('get', `${BASE}/subcategories`, subcategories),
    variables: mockApi('get', `${BASE}/variables`, variables),
  }
}

/** Render an environment screen for a member with the given level. */
export function renderEnvironment(
  ui: ReactElement,
  options: { level?: AccessLevel; variables?: Variable[]; subcategories?: Subcategory[] } = {},
) {
  const requests = mockParameters(options.variables, options.subcategories)
  const view = renderApp(ui, {
    me: makeMe({ dashboards: { environment: options.level ?? 'editor' } }),
    route: '/d/environment',
  })
  return { ...view, requests }
}
