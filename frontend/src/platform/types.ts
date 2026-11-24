export type AccessLevel = 'viewer' | 'editor' | 'admin'

export interface Municipality {
  id: string
  name: string
  slug: string
  kind: string
}

export interface Me {
  user: { id: string; email: string; full_name: string; is_platform_operator: boolean }
  memberships: { municipality: Municipality; is_admin: boolean }[]
  active_municipality_id: string | null
  dashboards: { key: string; level: AccessLevel }[]
  /** The user's municipalities that the platform operator suspended: nobody works in them. */
  suspended_municipalities: Municipality[]
}

const LEVEL_ORDER: AccessLevel[] = ['viewer', 'editor', 'admin']

/** Whether the user has at least `min` access to the dashboard in the active municipality. */
export function hasLevel(me: Me | null, key: string, min: AccessLevel): boolean {
  const level = me?.dashboards.find((dashboard) => dashboard.key === key)?.level
  return level !== undefined && LEVEL_ORDER.indexOf(level) >= LEVEL_ORDER.indexOf(min)
}

export function activeMembership(me: Me | null) {
  return me?.memberships.find((m) => m.municipality.id === me.active_municipality_id) ?? null
}
