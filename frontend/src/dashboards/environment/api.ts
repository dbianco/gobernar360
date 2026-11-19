import { useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type { Series, Subcategory, Summary, Value, Variable } from './types'

export const BASE = '/dashboards/environment'
export const BASE_PATH = '/d/environment'
const KEY = 'environment'

function useGet<T>(name: string, path: string, query?: Query, enabled = true) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    enabled,
  })
}

export const useSubcategories = () => useGet<Subcategory[]>('subcategories', '/subcategories')
export const useVariables = () => useGet<Variable[]>('variables', '/variables')
export const useValues = (year: number) => useGet<Value[]>('values', '/values', { year })
export const useSummary = (year: number) => useGet<Summary>('summary', '/summary', { year })
export const useSeries = (variableId: string, year: number) =>
  useGet<Series>('series', `/variables/${variableId}/series`, { year }, Boolean(variableId))

/** Changes to environment data refresh every environment query and the general overview. */
export const useAction = () => usePlatformAction([KEY, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })
