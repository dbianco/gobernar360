import type { LocatedKind } from '../../platform/geo/types'

export const ACTORS: LocatedKind = {
  dashboard: 'economic',
  record: 'actors',
  individualLevel: 'viewer',
  path: (id) => `/d/economic/actors/${id}`,
}
