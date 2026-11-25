import type { LocatedKind } from '../../platform/geo/types'

export const PROJECTS: LocatedKind = {
  dashboard: 'projects',
  record: 'projects',
  individualLevel: 'viewer',
  path: (id) => `/d/projects/projects/${id}`,
}
