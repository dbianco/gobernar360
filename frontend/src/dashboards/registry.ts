import { type ComponentType, lazy, type LazyExoticComponent } from 'react'

/**
 * A dashboard installed in the web app. To add one: create its folder next to
 * this file and append an entry here. Entries must not import each other.
 */
export interface DashboardEntry {
  /** Same key the API uses for grants. */
  key: string
  labelKey: string
  basePath: string
  routes: LazyExoticComponent<ComponentType>
}

export const dashboards: DashboardEntry[] = [
  {
    key: 'projects',
    labelKey: 'projects.title',
    basePath: '/d/projects',
    routes: lazy(() => import('./projects/routes')),
  },
  {
    key: 'environment',
    labelKey: 'environment.title',
    basePath: '/d/environment',
    routes: lazy(() => import('./environment/routes')),
  },
]

/** Translation key of a dashboard's name, or undefined for a key this build does not know. */
export function dashboardLabelKey(key: string): string | undefined {
  return dashboards.find((dashboard) => dashboard.key === key)?.labelKey
}
