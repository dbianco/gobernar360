import { useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type {
  Named,
  Opportunities,
  Page,
  Procedure,
  ProcedureDetail,
  Requirement,
  Source,
  Summary,
} from './types'

export const BASE = '/dashboards/procedures'
export const BASE_PATH = '/d/procedures'
export const KEY = 'procedures'

function useGet<T>(name: string, path: string, query?: Query) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    // Keep the rows on screen while the next page or search loads.
    placeholderData: (previous) => previous,
  })
}

export const useAreas = () => useGet<Named[]>('areas', '/areas')
export const useSources = () => useGet<Source[]>('sources', '/sources')
export const useRequirements = (q = '') => useGet<Requirement[]>('requirements', '/requirements', { q })
export const useProcedures = (query: Query) =>
  useGet<Page<Procedure>>('procedures', '/procedures', query)
export const useProcedure = (id: string) => useGet<ProcedureDetail>('procedure', `/procedures/${id}`)
export const useSummary = () => useGet<Summary>('summary', '/summary')
export const useOpportunities = () => useGet<Opportunities>('opportunities', '/opportunities')

/** Changes to the inventory refresh every procedures query and the general overview. */
export const useAction = () => usePlatformAction([KEY, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })
