import type { StatusColor } from '../status/types'

/** The kind of subject every dashboard has: one of its months. */
export const MONTH = 'month'

/** What a link points at: a month of a dashboard or a record it lets others point at. */
export interface SubjectRef {
  dashboard_key: string
  kind: string
  ref: string
}

/** A subject as the API shows it to whoever is signed in. */
export interface Subject {
  /** `restricted`: they may not know what it is. `deleted`: it no longer exists. */
  access: 'visible' | 'restricted' | 'deleted'
  kind: string
  dashboard_key: string | null
  ref: string | null
  label: string | null
  path: string | null
  /** The light of a month, when it has one. */
  color: StatusColor | null
}

export interface SubjectKind {
  dashboard_key: string
  kind: string
}

/** The reference of a subject that can be linked again, or null. */
export function refOf(subject: Subject | null | undefined): SubjectRef | null {
  if (subject?.access !== 'visible' || !subject.dashboard_key || !subject.ref) return null
  return { dashboard_key: subject.dashboard_key, kind: subject.kind, ref: subject.ref }
}
