import { useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type {
  Benefit,
  Delivery,
  Household,
  HouseholdDetail,
  Intervention,
  Named,
  Page,
  Reports,
  SocialPerson,
  Summary,
} from './types'

export const BASE = '/dashboards/social'
export const BASE_PATH = '/d/social'
export const PAGE_SIZE = 50
const KEY = 'social'

function useGet<T>(name: string, path: string, query?: Query, enabled = true) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    enabled,
    // Keep the rows on screen while the next page or search loads.
    placeholderData: (previous) => previous,
  })
}

export const useBenefitCategories = () =>
  useGet<Named[]>('benefit-categories', '/benefit-categories')
export const useBenefits = () => useGet<Benefit[]>('benefits', '/benefits')
export const useInterventionTypes = () =>
  useGet<Named[]>('intervention-types', '/intervention-types')

export const usePeople = (query: Query, enabled = true) =>
  useGet<Page<SocialPerson>>('people', '/people', query, enabled)
export const usePerson = (id: string) => useGet<SocialPerson>('person', `/people/${id}`)
export const useHouseholds = (query: Query) =>
  useGet<Page<Household>>('households', '/households', query)
export const useHousehold = (id: string) =>
  useGet<HouseholdDetail>('household', `/households/${id}`)
export const useDeliveries = (query: Query) =>
  useGet<Page<Delivery>>('deliveries', '/deliveries', query)
export const useInterventions = (query: Query) =>
  useGet<Page<Intervention>>('interventions', '/interventions', query)
export const useSummary = (year: number) => useGet<Summary>('summary', '/summary', { year })
export const useReports = (year: number) => useGet<Reports>('reports', '/reports', { year })

/** Changes to social data refresh every social query and the general overview. */
export const useAction = () => usePlatformAction([KEY, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })

export const get = <T>(path: string, query?: Query) => api<T>(`${BASE}${path}`, { query })
