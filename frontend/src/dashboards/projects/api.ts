import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'

import { api, type Query } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import type {
  AnnualBudget,
  Axis,
  Indicator,
  NamedRef,
  Objective,
  Owner,
  Project,
  ProjectFilters,
  Summary,
  Term,
} from './types'

export const BASE = '/dashboards/projects'
const KEY = 'projects'

function useGet<T>(name: string, path: string, query?: Query, enabled = true) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    enabled,
  })
}

export const useTerms = () => useGet<Term[]>('terms', '/terms')
export const useAxes = (termId?: string) =>
  useGet<Axis[]>('axes', '/axes', { term_id: termId }, Boolean(termId))
export const useObjectives = (termId?: string) =>
  useGet<Objective[]>('objectives', '/objectives', { term_id: termId }, Boolean(termId))
export const useDepartments = () => useGet<NamedRef[]>('departments', '/departments')
export const usePrograms = () => useGet<NamedRef[]>('programs', '/programs')
export const useOwners = () => useGet<Owner[]>('owners', '/owners')
export const useBudgets = (termId?: string) =>
  useGet<AnnualBudget[]>('budgets', `/terms/${termId}/budgets`, undefined, Boolean(termId))
export const useProjects = (termId: string, filters: ProjectFilters) =>
  useGet<Project[]>('projects', '/projects', { term_id: termId, ...filters })
export const useProject = (projectId: string) =>
  useGet<Project>('project', `/projects/${projectId}`)
export const useSummary = (termId: string, filters: ProjectFilters) =>
  useGet<Summary>('summary', '/summary', { term_id: termId, ...filters })
export const useIndicators = (termId: string) =>
  useGet<Indicator[]>('indicators', '/indicators', { term_id: termId })

/**
 * Runs a change against the API. On success every projects query (and the general
 * overview) is refreshed; on failure `error` holds a message to show.
 */
export function useAction() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const run = useCallback(
    async <T>(action: () => Promise<T>): Promise<T | undefined> => {
      setPending(true)
      setError(null)
      try {
        const result = await action()
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: [KEY] }),
          queryClient.invalidateQueries({ queryKey: ['overview'] }),
        ])
        return result
      } catch (caught) {
        setError(errorMessage(caught))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [queryClient],
  )

  return { run, error, pending, clearError: () => setError(null) }
}

export const send = <T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })
