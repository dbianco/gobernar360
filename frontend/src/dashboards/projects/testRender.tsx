import type { ReactElement } from 'react'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import type { AccessLevel } from '../../platform/types'
import { TermProvider } from './TermProvider'
import { AXES, DEPARTMENTS, OBJECTIVES, OLD_TERM, OWNERS, PROGRAMS, TERM } from './testData'
import type { Term } from './types'

export const BASE = '/dashboards/projects'

/** Mock the catalogs every projects screen loads; returns the requests each one received. */
export function mockCatalogs(terms: Term[] = [OLD_TERM, TERM]) {
  return {
    terms: mockApi('get', `${BASE}/terms`, terms),
    axes: mockApi('get', `${BASE}/axes`, AXES),
    objectives: mockApi('get', `${BASE}/objectives`, OBJECTIVES),
    departments: mockApi('get', `${BASE}/departments`, DEPARTMENTS),
    programs: mockApi('get', `${BASE}/programs`, PROGRAMS),
    owners: mockApi('get', `${BASE}/owners`, OWNERS),
  }
}

/** Render a projects screen for a member with the given level, inside the term provider. */
export function renderProjects(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string; terms?: Term[] } = {},
) {
  const catalogRequests = mockCatalogs(options.terms)
  const view = renderApp(<TermProvider>{ui}</TermProvider>, {
    me: makeMe({ dashboards: { projects: options.level ?? 'editor' } }),
    route: options.route ?? '/d/projects',
  })
  return { ...view, catalogRequests }
}
