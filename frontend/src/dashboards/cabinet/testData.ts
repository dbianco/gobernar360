import type { UserRef } from '../../platform/directory'
import type { Subject } from '../../platform/subjects/types'
import type { Page } from '../../platform/types'
import type {
  AgendaItem,
  AgendaProposal,
  Commitment,
  MeetingDetail,
  MeetingRow,
  Proposal,
  Summary,
} from './types'

// The same id as the signed-in person of test/fixtures.ts.
export const ANA: UserRef = { id: 'u-1', full_name: 'Ana Gómez' }
export const LEO: UserRef = { id: 'u-2', full_name: 'Leo Paz' }
export const ZOE: UserRef = { id: 'u-3', full_name: 'Zoe Ruiz' }

export const PLAZA: Subject = {
  access: 'visible',
  kind: 'project',
  dashboard_key: 'projects',
  ref: 'pr-1',
  label: 'Plaza central',
  path: '/d/projects/projects/pr-1',
  color: null,
}
export const OCTOBER: Subject = {
  access: 'visible',
  kind: 'month',
  dashboard_key: 'environment',
  ref: '2026-10',
  label: 'Ambiental, octubre de 2026',
  path: '/d/environment',
  color: 'red',
}
export const HIDDEN: Subject = {
  access: 'restricted',
  kind: 'project',
  dashboard_key: 'projects',
  ref: null,
  label: null,
  path: null,
  color: null,
}

export function makeCommitment(overrides: Partial<Commitment> = {}): Commitment {
  return {
    id: 'co-1',
    description: 'Certificar la obra',
    owner: LEO,
    due_date: '2026-11-20',
    state: 'overdue',
    completed_on: null,
    times_postponed: 2,
    subject: PLAZA,
    followers: [],
    item_id: 'it-9',
    meeting: { id: 'me-0', date: '2026-10-20', closed: true },
    ...overrides,
  }
}

export function makeItem(overrides: Partial<AgendaItem> = {}): AgendaItem {
  return {
    id: 'it-1',
    source: 'manual',
    title: 'Feria del libro',
    notes: '',
    discussed: false,
    carried: false,
    subject: null,
    topic: null,
    commitments: [],
    ...overrides,
  }
}

export const LIGHT_ITEM = makeItem({
  id: 'it-2',
  source: 'light',
  title: OCTOBER.label!,
  subject: OCTOBER,
})

export function makeMeeting(overrides: Partial<MeetingDetail> = {}): MeetingDetail {
  return {
    id: 'me-1',
    date: '2026-11-23',
    closed: false,
    closed_at: null,
    attendees: [ANA, LEO],
    guests: 'Ing. Funes',
    notes: '',
    items: [makeItem(), LIGHT_ITEM],
    carried_over: [],
    ...overrides,
  }
}

export function makeRow(overrides: Partial<MeetingRow> = {}): MeetingRow {
  return {
    id: 'me-1',
    date: '2026-11-23',
    closed: false,
    closed_at: null,
    items: 4,
    commitments: 2,
    ...overrides,
  }
}

export function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    key: 'light:environment:2026-10',
    source: 'light',
    title: OCTOBER.label!,
    subject: OCTOBER,
    commitment: null,
    carried: false,
    ...overrides,
  }
}

export const PROPOSALS: Proposal[] = [
  makeProposal(),
  makeProposal({
    key: 'commitment:co-1',
    source: 'commitment',
    title: 'Certificar la obra',
    subject: null,
    commitment: makeCommitment(),
  }),
  makeProposal({
    key: 'item:it-7',
    source: 'manual',
    title: 'Cronograma',
    subject: null,
    carried: true,
  }),
]

export function makeAgendaProposal(overrides: Partial<AgendaProposal> = {}): AgendaProposal {
  return {
    proposals: PROPOSALS,
    to_carry_over: 2,
    dashboards_not_considered: 0,
    previous_meeting_date: '2026-10-20',
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length): Page<T> => ({ items, total })

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    total: 9,
    by_state: { overdue: 2, open: 3, done: 3, dropped: 1 },
    on_time_share: 0.4,
    by_owner: [
      {
        owner: LEO,
        by_state: { overdue: 2, open: 1, done: 1, dropped: 0 },
        on_time_share: 0.25,
      },
      {
        owner: ANA,
        by_state: { overdue: 0, open: 2, done: 2, dropped: 1 },
        on_time_share: null,
      },
    ],
    most_postponed: [makeCommitment()],
    closed_meetings: 3,
    last_meeting: '2026-11-17',
    ...overrides,
  }
}
