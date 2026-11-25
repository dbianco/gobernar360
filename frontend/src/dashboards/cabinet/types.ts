import type { State } from '../../platform/commitments/types'
import type { UserRef } from '../../platform/directory'
import type { Subject } from '../../platform/subjects/types'

export type ItemSource = 'manual' | 'light' | 'commitment'

export interface MeetingRef {
  id: string
  date: string
  closed: boolean
}

export interface Commitment {
  id: string
  description: string
  owner: UserRef
  due_date: string
  state: State
  completed_on: string | null
  times_postponed: number
  subject: Subject | null
  /** Told when it is done. */
  followers: UserRef[]
  item_id: string
  /** Where it was taken. */
  meeting: MeetingRef
}

export interface Proposal {
  key: string
  source: ItemSource
  title: string
  subject: Subject | null
  commitment: Commitment | null
  /** Left undiscussed in the previous meeting. */
  carried: boolean
}

export interface AgendaProposal {
  proposals: Proposal[]
  to_carry_over: number
  dashboards_not_considered: number
  previous_meeting_date: string | null
}

export interface MeetingRow extends MeetingRef {
  closed_at: string | null
  items: number
  commitments: number
}

export interface AgendaItem {
  id: string
  source: ItemSource
  title: string
  notes: string
  discussed: boolean
  carried: boolean
  subject: Subject | null
  /** The commitment the item follows up. */
  topic: Commitment | null
  commitments: Commitment[]
}

export interface MeetingDetail extends MeetingRef {
  closed_at: string | null
  attendees: UserRef[]
  guests: string
  notes: string
  items: AgendaItem[]
  carried_over: Commitment[]
}

export interface OwnerRow {
  owner: UserRef
  by_state: Record<State, number>
  on_time_share: number | null
}

export interface Summary {
  total: number
  by_state: Record<State, number>
  on_time_share: number | null
  by_owner: OwnerRow[]
  most_postponed: Commitment[]
  closed_meetings: number
  last_meeting: string | null
}
