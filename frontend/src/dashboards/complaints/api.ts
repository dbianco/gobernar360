import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import type { DocumentQuery, Lookup } from '../../platform/people/types'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type {
  Calendar,
  Complaint,
  ComplaintDetail,
  ComplaintType,
  Named,
  Page,
  Queue,
  Summary,
} from './types'

export const BASE = '/dashboards/complaints'
export const BASE_PATH = '/d/complaints'
export const KEY = 'complaints'

function useGet<T>(
  name: string,
  path: string,
  query?: Query,
  options: { enabled?: boolean; keepPrevious?: boolean } = {},
) {
  const { enabled = true, keepPrevious = true } = options
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    // Keep the rows on screen while the next page or search loads.
    placeholderData: keepPrevious ? keepPreviousData : undefined,
    enabled,
  })
}

export const useAreas = () => useGet<Named[]>('areas', '/areas')
export const useZones = () => useGet<Named[]>('zones', '/zones')
export const useTypes = () => useGet<ComplaintType[]>('types', '/types')
export const useCalendar = () => useGet<Calendar>('calendar', '/calendar')
export const useComplaints = (query: Query) =>
  useGet<Page<Complaint>>('complaints', '/complaints', query)
export const useComplaint = (id: string) =>
  useGet<ComplaintDetail>('complaint', `/complaints/${id}`)
export const useQueues = () => useGet<Queue[]>('queues', '/queues')
// Another area's rows must never stand in for this one's while it loads.
export const useQueue = (areaId: string) =>
  useGet<Complaint[]>('queue', `/queues/${areaId}`, undefined, {
    enabled: areaId !== '',
    keepPrevious: false,
  })
export const useSummary = (query: Query) => useGet<Summary>('summary', '/summary', query)

export const lookupPerson = (document: DocumentQuery) =>
  api<Lookup>(`${BASE}/people/lookup`, { query: document })

/** Changes refresh every complaints query and the general overview. */
export const useAction = () => usePlatformAction([KEY, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })
