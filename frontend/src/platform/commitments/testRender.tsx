import type { ReactElement } from 'react'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { ANA, LEO, PLAZA, ZOE } from './testData'

/** Mock who may be given commitments and what they may be linked to. */
export function mockCatalog() {
  mockApi('get', '/members', [ANA, LEO, ZOE])
  mockApi('get', '/subjects/kinds', [{ dashboard_key: 'projects', kind: 'project' }])
  mockApi('get', '/subjects/search', [PLAZA])
}

/** Render a screen for a member with no dashboards: commitments are everyone's. */
export function renderCommitments(ui: ReactElement, route = '/commitments') {
  mockCatalog()
  return renderApp(ui, { me: makeMe(), route })
}
