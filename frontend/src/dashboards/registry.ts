import {
  IconBuildingStore,
  IconBulb,
  IconFileText,
  IconGavel,
  IconHeartHandshake,
  IconLeaf,
  IconMessageReport,
  type Icon,
} from '@tabler/icons-react'
import { type ComponentType, lazy, type LazyExoticComponent } from 'react'

/**
 * A dashboard installed in the web app. To add one: create its folder next to
 * this file and append an entry here. Entries must not import each other.
 */
export interface DashboardEntry {
  /** Same key the API uses for grants. */
  key: string
  labelKey: string
  /** Shown in the menu and on the dashboard's status light. */
  icon: Icon
  basePath: string
  routes: LazyExoticComponent<ComponentType>
}

export const dashboards: DashboardEntry[] = [
  {
    key: 'projects',
    labelKey: 'projects.title',
    icon: IconBulb,
    basePath: '/d/projects',
    routes: lazy(() => import('./projects/routes')),
  },
  {
    key: 'environment',
    labelKey: 'environment.title',
    icon: IconLeaf,
    basePath: '/d/environment',
    routes: lazy(() => import('./environment/routes')),
  },
  {
    key: 'economic',
    labelKey: 'economic.title',
    icon: IconBuildingStore,
    basePath: '/d/economic',
    routes: lazy(() => import('./economic/routes')),
  },
  {
    key: 'social',
    labelKey: 'social.title',
    icon: IconHeartHandshake,
    basePath: '/d/social',
    routes: lazy(() => import('./social/routes')),
  },
  {
    key: 'procedures',
    labelKey: 'procedures.title',
    icon: IconFileText,
    basePath: '/d/procedures',
    routes: lazy(() => import('./procedures/routes')),
  },
  {
    key: 'complaints',
    labelKey: 'complaints.title',
    icon: IconMessageReport,
    basePath: '/d/complaints',
    routes: lazy(() => import('./complaints/routes')),
  },
  {
    key: 'cabinet',
    labelKey: 'cabinet.title',
    icon: IconGavel,
    basePath: '/d/cabinet',
    routes: lazy(() => import('./cabinet/routes')),
  },
]

/** Translation key of a dashboard's name, or undefined for a key this build does not know. */
export function dashboardLabelKey(key: string): string | undefined {
  return dashboards.find((dashboard) => dashboard.key === key)?.labelKey
}
