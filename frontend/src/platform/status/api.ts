import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/client'
import { useAction } from '../useAction'
import type { MonthStatus, StatusColor } from './types'

const path = (dashboardKey: string) => `/dashboards/${dashboardKey}/status`

/** The lights set for a dashboard in one year. */
export function useDashboardStatus(dashboardKey: string, year: number) {
  return useQuery({
    queryKey: ['status', dashboardKey, year],
    queryFn: () => api<MonthStatus[]>(path(dashboardKey), { query: { year } }),
  })
}

/** Sets or clears (null) the light of a month; refreshes the strips and the overview. */
export function useSetStatus(dashboardKey: string) {
  const action = useAction(['status', 'overview'])
  const set = (year: number, month: number, color: StatusColor | null) =>
    action.run(() =>
      api(`${path(dashboardKey)}/${year}/${month}`, { method: 'PUT', body: { color } }),
    )
  return { set, error: action.error, pending: action.pending }
}
