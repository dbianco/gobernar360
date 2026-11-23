import type { AccessLevel, Me } from './types'

const LEVEL_ORDER: AccessLevel[] = ['viewer', 'editor', 'admin']

/** Whether the user has at least `min` access to the dashboard in the active municipality. */
export function hasLevel(me: Me | null, key: string, min: AccessLevel): boolean {
  const level = me?.dashboards.find((dashboard) => dashboard.key === key)?.level
  return level !== undefined && LEVEL_ORDER.indexOf(level) >= LEVEL_ORDER.indexOf(min)
}

export function activeMembership(me: Me | null) {
  return me?.memberships.find((m) => m.municipality.id === me.active_municipality_id) ?? null
}
