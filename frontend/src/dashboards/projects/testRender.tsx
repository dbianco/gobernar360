import type { ReactElement } from 'react'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import type { AccessLevel } from '../../platform/types'
import { TermProvider } from './TermProvider'
import { AXES, DEPARTMENTS, OBJECTIVES, OLD_TERM, OWNERS, PROGRAMS, TERM } from './testData'
import type { Term } from './types'

export const BASE = '/dashboards/projects'

/** Mock the catalogs every projects screen loads. */
export function mockCatalogs(terms: Term[] = [OLD_TERM, TERM]) {
  mockApi('get', `${BASE}/terms`, terms)
  mockApi('get', `${BASE}/axes`, AXES)
  mockApi('get', `${BASE}/objectives`, OBJECTIVES)
  mockApi('get', `${BASE}/departments`, DEPARTMENTS)
  mockApi('get', `${BASE}/programs`, PROGRAMS)
  mockApi('get', `${BASE}/owners`, OWNERS)
}

/** Render a projects screen for a member with the given level, inside the term provider. */
export function renderProjects(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string; terms?: Term[] } = {},
) {
  mockCatalogs(options.terms)
  return renderApp(<TermProvider>{ui}</TermProvider>, {
    me: makeMe({ dashboards: { projects: options.level ?? 'editor' } }),
    route: options.route ?? '/d/projects',
  })
}
