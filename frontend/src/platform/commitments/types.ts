/** An open commitment about a subject, whichever dashboard keeps it. */
export interface SubjectCommitment {
  id: string
  /** Which subject of those asked about it is for. */
  ref: string
  description: string
  owner: string
  due_date: string
  overdue: boolean
  times_postponed: number
  path: string
}
