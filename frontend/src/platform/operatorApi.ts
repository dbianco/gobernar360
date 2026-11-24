import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { Municipality } from './types'

export interface Suspension {
  /** ISO moment it was suspended. */
  at: string
  reason: string
  /** Who suspended it; null if that account no longer exists. */
  by: string | null
}

export interface MunicipalityDetail extends Municipality {
  /** Keys of the dashboards enabled for the municipality. */
  dashboards: string[]
  /** Set while the municipality is suspended. */
  suspension: Suspension | null
}

export const KINDS = ['municipality', 'commune'] as const

export const useMunicipalities = () =>
  useQuery({
    queryKey: ['platform', 'municipalities'],
    queryFn: () => api<MunicipalityDetail[]>('/platform/municipalities'),
  })

/** Every dashboard installed in the platform, enabled or not. */
export const useRegisteredDashboards = () =>
  useQuery({
    queryKey: ['platform', 'dashboards'],
    queryFn: () => api<string[]>('/platform/dashboards'),
  })
