import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/client'
import type { SubjectRef } from '../subjects/types'
import type { SubjectCommitment } from './types'

/** First part of these queries' keys, for changes that must refresh them. */
export const COMMITMENTS = 'commitments'

/** Open commitments about one record of a dashboard. */
export function useSubjectCommitments({ dashboard_key, kind, ref }: SubjectRef) {
  return useQuery({
    queryKey: [COMMITMENTS, dashboard_key, kind, ref],
    queryFn: () =>
      api<SubjectCommitment[]>(`/subjects/${dashboard_key}/${kind}/${ref}/commitments`),
  })
}

/** Open commitments about the months of a year of a dashboard. */
export function useMonthCommitments(dashboardKey: string, year: number) {
  return useQuery({
    queryKey: [COMMITMENTS, dashboardKey, year],
    queryFn: () =>
      api<SubjectCommitment[]>(`/subjects/${dashboardKey}/commitments`, { query: { year } }),
  })
}
