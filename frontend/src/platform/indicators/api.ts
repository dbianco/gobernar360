import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/client'
import { useAction } from '../useAction'
import type { CombinedEvolution, IndicatorEvolution, IndicatorTarget, YearValues } from './types'

const path = (dashboardKey: string) => `/dashboards/${dashboardKey}`

// Keys start with the dashboard's own key, so its data changes refresh them too.

/** Every indicator of a dashboard, today and over the last twelve months. */
export function useEvolution(dashboardKey: string) {
  return useQuery({
    queryKey: [dashboardKey, 'evolution'],
    queryFn: () => api<IndicatorEvolution[]>(`${path(dashboardKey)}/evolution`),
  })
}

/** The indicators of each month of a year, for the status strip. */
export function useYearValues(dashboardKey: string, year: number) {
  return useQuery({
    queryKey: [dashboardKey, 'evolution-months', year],
    queryFn: () =>
      api<YearValues>(`${path(dashboardKey)}/evolution/months`, { query: { year } }),
  })
}

export function useTargets(dashboardKey: string, year: number) {
  return useQuery({
    queryKey: [dashboardKey, 'targets', year],
    queryFn: () => api<IndicatorTarget[]>(`${path(dashboardKey)}/targets`, { query: { year } }),
  })
}

/** Sets or clears (null) a target; refreshes the dashboard and the overview. */
export function useSetTarget(dashboardKey: string) {
  const action = useAction([dashboardKey, 'overview'])
  const set = (year: number, indicatorKey: string, value: number | null) =>
    action.run(() =>
      api(`${path(dashboardKey)}/targets/${year}/${indicatorKey}`, {
        method: 'PUT',
        body: { value },
      }),
    )
  return { set, error: action.error, pending: action.pending, clearError: action.clearError }
}

/** Indicators that relate two dashboards, for members who can see both. */
export function useCombinedIndicators() {
  return useQuery({
    queryKey: ['overview', 'combined'],
    queryFn: () => api<CombinedEvolution[]>('/overview/combined'),
  })
}
