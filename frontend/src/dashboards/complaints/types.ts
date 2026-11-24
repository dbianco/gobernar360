import type { Person } from '../../platform/people/types'

export const STATES = [
  'received',
  'assigned',
  'in_progress',
  'waiting',
  'resolved',
  'closed',
  'rejected',
  'reopened',
] as const
export type State = (typeof STATES)[number]
/** States someone still has to act on. */
export const OPEN_STATES: State[] = ['received', 'assigned', 'in_progress', 'waiting', 'reopened']
/** Moves that must say why. */
export const NOTE_REQUIRED: State[] = ['rejected', 'reopened']

export const CLOCK_STATUSES = ['on_time', 'at_risk', 'overdue'] as const
export type ClockStatus = (typeof CLOCK_STATUSES)[number]

/** ISO weekdays, Monday = 1. */
export const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const

export interface Named {
  id: string
  name: string
}

export interface ComplaintType extends Named {
  area: Named
  /** Target resolution time in business days. */
  target_days: number
  is_active: boolean
}

export interface Holiday {
  id: string
  /** YYYY-MM-DD */
  date: string
  name: string
}

export interface Calendar {
  weekdays: number[]
  holidays: Holiday[]
}

/** The service clock of one complaint, in business days. */
export interface Clock {
  target_days: number
  used_days: number
  /** Negative once the target has been exceeded. */
  left_days: number
  /** YYYY-MM-DD. While waiting, where it falls if work resumes today. */
  deadline: string
  /** Null for a rejected complaint. */
  status: ClockStatus | null
  paused: boolean
  resolved_on: string | null
}

export interface Complaint {
  id: string
  number: number
  /** ISO date-time. */
  received_at: string
  type: Named
  area: Named
  zone: Named
  address: string
  state: State
  person: { id: string; full_name: string } | null
  clock: Clock
}

export type EventKind = 'created' | 'transition' | 'reassigned' | 'retyped' | 'comment'

export interface TimelineEvent {
  id: string
  kind: EventKind
  from_state: State | null
  to_state: State | null
  from_area: Named | null
  to_area: Named | null
  from_type: Named | null
  to_type: Named | null
  note: string
  at: string
  user: { id: string; full_name: string } | null
}

export interface ComplaintDetail extends Omit<Complaint, 'person'> {
  description: string
  person: Person | null
  /** States this complaint may move to next. */
  moves: State[]
  timeline: TimelineEvent[]
}

export interface Queue {
  area: Named
  open: number
  at_risk: number
  overdue: number
  paused: number
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface Resolution {
  received: number
  resolved: number
  on_time: number
  on_time_ratio: number | null
  median_days: number | null
  p90_days: number | null
}

export interface GroupResolution extends Resolution {
  id: string
  name: string
}

export interface Summary {
  period: { from: string; to: string }
  repeat_days: number
  backlog: {
    open: number
    overdue: number
    at_risk: number
    paused: number
    by_state: { state: State; count: number }[]
    by_status: { status: ClockStatus; count: number }[]
    ageing: { min_days: number; max_days: number | null; count: number }[]
  }
  totals: Resolution
  monthly: { month: string; received: number; resolved: number }[]
  by_type: GroupResolution[]
  by_area: GroupResolution[]
  repeated: {
    type: string
    address: string
    zone: string
    count: number
    first_received: string
    last_received: string
    numbers: number[]
  }[]
  top_zones: { name: string; count: number }[]
  top_types: { name: string; count: number }[]
}
