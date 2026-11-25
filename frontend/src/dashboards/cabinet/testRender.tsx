import type { ReactElement } from 'react'

import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { mockApi } from '../../test/server'
import { ANA, LEO, PLAZA, ZOE } from './testData'

export const BASE = '/dashboards/cabinet'

/** Mock who may owe commitments and what they may be linked to. */
export function mockCatalog() {
  mockApi('get', '/members', [ANA, LEO, ZOE])
  mockApi('get', '/subjects/kinds', [
    { dashboard_key: 'environment', kind: 'month' },
    { dashboard_key: 'projects', kind: 'project' },
  ])
  mockApi('get', '/subjects/search', [PLAZA])
}

/** Render a cabinet screen for a member with the given level. */
export function renderCabinet(
  ui: ReactElement,
  options: { level?: AccessLevel; route?: string } = {},
) {
  mockCatalog()
  return renderApp(ui, {
    me: makeMe({ dashboards: { cabinet: options.level ?? 'editor' } }),
    route: options.route ?? '/d/cabinet',
  })
}
