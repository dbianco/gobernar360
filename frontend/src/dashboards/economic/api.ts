import { useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type {
  Actor,
  ActorDetail,
  Assignment,
  EconomicPerson,
  Named,
  Page,
  PersonDetail,
  Reports,
  Summary,
  Tool,
  ToolSubcategory,
} from './types'

export const BASE = '/dashboards/economic'
export const BASE_PATH = '/d/economic'
export const PAGE_SIZE = 50
const KEY = 'economic'

function useGet<T>(name: string, path: string, query?: Query, enabled = true) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    enabled,
    // Keep the rows on screen while the next page or search loads.
    placeholderData: (previous) => previous,
  })
}

export const useActorTypes = () => useGet<Named[]>('actor-types', '/actor-types')
export const useSectors = () => useGet<Named[]>('sectors', '/sectors')
export const useToolCategories = () => useGet<Named[]>('tool-categories', '/tool-categories')
export const useToolSubcategories = () =>
  useGet<ToolSubcategory[]>('tool-subcategories', '/tool-subcategories')
export const useTools = () => useGet<Tool[]>('tools', '/tools')

export const useActors = (query: Query) => useGet<Page<Actor>>('actors', '/actors', query)
export const useActor = (id: string) => useGet<ActorDetail>('actor', `/actors/${id}`)
export const usePeople = (query: Query, enabled = true) =>
  useGet<Page<EconomicPerson>>('people', '/people', query, enabled)
export const usePerson = (id: string) => useGet<PersonDetail>('person', `/people/${id}`)
export const useAssignments = (query: Query) =>
  useGet<Page<Assignment>>('assignments', '/assignments', query)
export const useSummary = (year: number) => useGet<Summary>('summary', '/summary', { year })
export const useReports = (year: number) => useGet<Reports>('reports', '/reports', { year })

/** Changes to economic data refresh every economic query and the general overview. */
export const useAction = () => usePlatformAction([KEY, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })

export const get = <T>(path: string, query?: Query) => api<T>(`${BASE}${path}`, { query })
