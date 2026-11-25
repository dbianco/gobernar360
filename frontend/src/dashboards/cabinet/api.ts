import { useQuery } from '@tanstack/react-query'

import { api, type Query } from '../../api/client'
import { COMMITMENTS } from '../../platform/commitments/api'
import type { Page } from '../../platform/types'
import { useAction as usePlatformAction } from '../../platform/useAction'
import type {
  AgendaProposal,
  Commitment,
  CommitmentDetail,
  MeetingDetail,
  MeetingRow,
  Member,
  Summary,
} from './types'

export const BASE = '/dashboards/cabinet'
export const BASE_PATH = '/d/cabinet'
export const KEY = 'cabinet'

function useGet<T>(name: string, path: string, query?: Query, enabled = true) {
  return useQuery({
    queryKey: [KEY, name, path, query ?? null],
    queryFn: () => api<T>(`${BASE}${path}`, { query }),
    enabled,
    // Keep the rows on screen while the next page or search loads.
    placeholderData: (previous) => previous,
  })
}

export const useSummary = () => useGet<Summary>('summary', '/summary')
export const useMembers = () => useGet<Member[]>('members', '/members')
export const useMeetings = (query: Query) => useGet<Page<MeetingRow>>('meetings', '/meetings', query)
export const useMeeting = (id: string) => useGet<MeetingDetail>('meeting', `/meetings/${id}`)
export const useAgendaProposal = (date: string) =>
  useGet<AgendaProposal>('proposal', '/agenda-proposal', { date }, date !== '')
export const useCommitments = (query: Query) =>
  useGet<Page<Commitment>>('commitments', '/commitments', query)
export const useCommitment = (id: string) =>
  useGet<CommitmentDetail>('commitment', `/commitments/${id}`)

/** The meeting being prepared or held, if any: it is always the latest. */
export function useOpenMeeting() {
  const latest = useMeetings({ limit: 1, offset: 0 })
  return { ...latest, open: latest.data?.items.find((meeting) => !meeting.closed) ?? null }
}

/** Changes refresh every cabinet query, what other pages show of them and the overview. */
export const useAction = () => usePlatformAction([KEY, COMMITMENTS, 'overview'])

export const send = <T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
) => api<T>(`${BASE}${path}`, { method, body })

/** For answers without a body, so that a success can be told from a failure. */
export async function done(request: Promise<unknown>): Promise<true> {
  await request
  return true
}
