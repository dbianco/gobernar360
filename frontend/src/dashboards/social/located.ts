import type { LocatedKind } from '../../platform/geo/types'

/** Where a family lives is shown to editors and above; viewers get counts per zone. */
export const HOUSEHOLDS: LocatedKind = {
  dashboard: 'social',
  record: 'households',
  individualLevel: 'editor',
  path: (id) => `/d/social/households/${id}`,
}
