import { expect, it } from 'vitest'

import { makeMe } from '../test/fixtures'
import { activeMembership, hasLevel } from './access'

it('grants a level to those who have it or a higher one', () => {
  const me = makeMe({ dashboards: { projects: 'editor' } })

  expect(hasLevel(me, 'projects', 'viewer')).toBe(true)
  expect(hasLevel(me, 'projects', 'editor')).toBe(true)
  expect(hasLevel(me, 'projects', 'admin')).toBe(false)
})

it('grants nothing on a dashboard without access, or to nobody', () => {
  const me = makeMe({ dashboards: { projects: 'admin' } })

  expect(hasLevel(me, 'social', 'viewer')).toBe(false)
  expect(hasLevel(null, 'projects', 'viewer')).toBe(false)
})

it('finds the membership of the active municipality', () => {
  const me = makeMe({ isAdmin: true })

  expect(activeMembership(me)?.municipality.id).toBe(me.active_municipality_id)
  expect(activeMembership({ ...me, active_municipality_id: null })).toBeNull()
  expect(activeMembership(null)).toBeNull()
})
