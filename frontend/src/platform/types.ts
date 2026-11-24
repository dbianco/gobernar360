export type AccessLevel = 'viewer' | 'editor' | 'admin'

export interface Municipality {
  id: string
  name: string
  slug: string
  kind: string
}

export interface Me {
  user: {
    id: string
    email: string
    full_name: string
    phone: string
    is_platform_operator: boolean
  }
  /** False when the account only signs in through single sign-on. */
  has_password: boolean
  memberships: { municipality: Municipality; is_admin: boolean }[]
  active_municipality_id: string | null
  dashboards: { key: string; level: AccessLevel }[]
  /** The user's municipalities that the platform operator suspended: nobody works in them. */
  suspended_municipalities: Municipality[]
}

/** One page of a list the API paginates. */
export interface Page<T> {
  items: T[]
  total: number
}
