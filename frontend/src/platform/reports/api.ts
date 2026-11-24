import { useQuery } from '@tanstack/react-query'

import { api } from '../../api/client'
import { useAction } from '../useAction'
import type { ReportPreview, ReportSummary } from './types'

const KEY = 'reports'

export function useReports() {
  return useQuery({ queryKey: [KEY], queryFn: () => api<ReportSummary[]>('/reports') })
}

export function usePreview(year: number, month: number) {
  return useQuery({
    queryKey: [KEY, 'preview', year, month],
    queryFn: () => api<ReportPreview>(`/reports/preview/${year}/${month}`),
  })
}

/** Closing, reopening and publishing; every change refreshes the list and the public page. */
export function useReportAction() {
  return useAction([KEY, 'publication'])
}

export const closeMonth = (year: number, month: number, comments: Record<string, string>) =>
  api<ReportSummary>(`/reports/${year}/${month}/close`, { method: 'POST', body: { comments } })

export const reopenReport = (id: string) =>
  api<ReportSummary>(`/reports/${id}/reopen`, { method: 'POST' })

export const setReportPublished = (id: string, published: boolean) =>
  api(`/reports/${id}/publication`, { method: 'PUT', body: { published } })
