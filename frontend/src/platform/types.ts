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
}

/** One page of a list the API paginates. */
export interface Page<T> {
  items: T[]
  total: number
}
