import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api, type Query } from '../../api/client'
import type { SubjectRef } from '../subjects/types'
import type { Page } from '../types'
import { useAction } from '../useAction'
import type { Commitment, CommitmentDetail, Notifications, SubjectCommitment } from './types'

/** First part of these queries' keys, for changes that must refresh them. */
export const COMMITMENTS = 'commitments'
export const NOTICES = 'notices'
export const PATH = '/commitments'
export const NOTIFICATIONS_PATH = '/notifications'

// How often what one was told is looked up again, so it shows without reloading.
const NOTICES_EVERY = 60_000

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

/** Those one owes, gave or is attached to. */
export function useCommitments(query: Query) {
  return useQuery({
    queryKey: [COMMITMENTS, 'list', query],
    queryFn: () => api<Page<Commitment>>(PATH, { query }),
    // Keep the rows on screen while the next page or search loads.
    placeholderData: (previous) => previous,
  })
}

export function useCommitment(id: string) {
  return useQuery({
    queryKey: [COMMITMENTS, 'one', id],
    queryFn: () => api<CommitmentDetail>(`${PATH}/${id}`),
  })
}

export function useNotifications() {
  return useQuery({
    queryKey: [NOTICES],
    queryFn: () => api<Notifications>('/notifications'),
    refetchInterval: NOTICES_EVERY,
    refetchOnWindowFocus: true,
  })
}

/** Changes to commitments refresh every place that shows them; `more` are other keys to. */
export const useCommitmentAction = (...more: string[]) =>
  useAction([COMMITMENTS, NOTICES, 'cabinet', 'overview', ...more])

export const send = <T = unknown>(method: 'POST' | 'PATCH', path: string, body: unknown) =>
  api<T>(path, { method, body })

/** Marks as read what one was told about a commitment, or about all of them. */
export async function markRead(commitmentId?: string): Promise<true> {
  await send('POST', '/notifications/read', commitmentId ? { commitment_id: commitmentId } : {})
  return true
}

/** Opening a commitment is reading what one was told about it. */
export function useReadOnOpen(id: string, hasNews: boolean) {
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!hasNews) return
    markRead(id)
      .then(() => queryClient.invalidateQueries({ queryKey: [NOTICES] }))
      // It stays as news, which is the worst that can happen.
      .catch(() => undefined)
  }, [id, hasNews, queryClient])
}
