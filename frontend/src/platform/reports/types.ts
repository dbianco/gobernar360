import type { StatusColor } from '../status/types'

export type ReportStatus = 'draft' | 'closed' | 'superseded'

/** One version of a month's report. */
export interface ReportSummary {
  id: string
  year: number
  month: number
  version: number
  status: ReportStatus
  closed_at: string | null
  reopened_at: string | null
  published: boolean
}

export interface ReportIndicator {
  key: string
  name: string
  unit: 'percent' | 'ratio' | null
  value: number | null
  target: number | null
  on_track: boolean | null
}

export interface ReportDashboard {
  key: string
  name: string
  light: StatusColor | null
  indicators: ReportIndicator[]
}

/** What closing a month would freeze, and the comments already written for it. */
export interface ReportPreview {
  year: number
  month: number
  version: number | null
  content: { dashboards: ReportDashboard[] }
  comments: Record<string, string>
}
