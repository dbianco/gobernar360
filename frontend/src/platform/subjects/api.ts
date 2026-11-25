import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/client'
import type { Subject, SubjectKind } from './types'

/** What the signed-in person may link to. */
export function useSubjectKinds() {
  return useQuery({
    queryKey: ['subjects', 'kinds'],
    queryFn: () => api<SubjectKind[]>('/subjects/kinds'),
  })
}

/** Subjects of one kind that match a search; none until a kind is chosen. */
export function useSubjectSearch(kind: SubjectKind | null, q: string) {
  return useQuery({
    queryKey: ['subjects', 'search', kind, q],
    queryFn: () =>
      api<Subject[]>('/subjects/search', {
        query: { dashboard_key: kind?.dashboard_key, kind: kind?.kind, q, limit: 24 },
      }),
    enabled: kind !== null,
    // Keep the options on screen while the next search loads.
    placeholderData: (previous) => previous,
  })
}
