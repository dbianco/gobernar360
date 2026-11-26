import type { UserRef } from '../directory'
import type { Subject } from '../subjects/types'

/** In the order they are shown. */
export const STATES = ['overdue', 'open', 'done', 'dropped'] as const
export type State = (typeof STATES)[number]

/** An open commitment about a subject, as its page and its status strip list it. */
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

/** What whoever is signed in may do with a commitment. */
export interface Rights {
  see: boolean
  /** Say it is done. */
  finish: boolean
  /** Change who owes it, by when and who is attached. */
  reschedule: boolean
  /** Drop or reopen it. */
  manage: boolean
  /** Change what was agreed and what it is about. */
  edit: boolean
  note: boolean
}

export interface Commitment {
  id: string
  description: string
  owner: UserRef
  /** Who gave an informal one. Null for those of a dashboard. */
  creator: UserRef | null
  /** Whether the owner is no longer a member of the municipality. */
  owner_left: boolean
  due_date: string
  /** The date it was given for; `due_date` is the one it has now. */
  agreed_due_date: string
  state: State
  completed_on: string | null
  times_postponed: number
  subject: Subject | null
  /** The dashboard that recorded it. Null for informal ones. */
  source: string | null
  /** Where it was recorded. Null for whoever has no access to the source. */
  origin: { label: string; path: string } | null
  /** Told when it is done. */
  followers: UserRef[]
  rights: Rights
}

export interface HistoryEntry {
  id: string
  at: string
  author: string | null
  note: string
  /** field -> [before, after] */
  changes: Record<string, [string | null, string | null]>
}

export interface CommitmentDetail extends Commitment {
  /** Newest first. */
  history: HistoryEntry[]
}

export const RELATIONS = ['mine', 'given', 'following'] as const
export type Relation = (typeof RELATIONS)[number]

/** Something a person was told and has not read. */
export interface News {
  kind: 'assigned' | 'done' | 'owner_left'
  actor: string | null
  at: string
}

export interface NotificationRow {
  id: string
  description: string
  owner: UserRef
  due_date: string
  state: State
  completed_on: string | null
  news: News[]
}

/** Something somebody who is no longer a member still owes. */
export interface LeftCommitment {
  id: string
  description: string
  owner: UserRef
  due_date: string
  source: string | null
  /** Whether whoever is signed in may give it to somebody else. */
  can_reassign: boolean
}

export interface LeftCommitments {
  commitments: LeftCommitment[]
  /** Others they may not see. Who gave them was told. */
  hidden: number
}

export interface Notifications {
  /** Open ones whoever is signed in owes. */
  mine: NotificationRow[]
  /** Other people's they gave or are attached to. */
  others: NotificationRow[]
}
