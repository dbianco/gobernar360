import type { UserRef } from '../directory'
import type { Subject } from '../subjects/types'
import type { Page } from '../types'
import type {
  Commitment,
  CommitmentDetail,
  News,
  NotificationRow,
  Notifications,
  Rights,
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
export const HIDDEN: Subject = {
  access: 'restricted',
  kind: 'project',
  dashboard_key: 'projects',
  ref: null,
  label: null,
  path: null,
  color: null,
}

export const NOTHING: Rights = {
  see: true,
  finish: false,
  reschedule: false,
  manage: false,
  edit: false,
  note: false,
}
export const EVERYTHING: Rights = {
  see: true,
  finish: true,
  reschedule: true,
  manage: true,
  edit: true,
  note: true,
}
/** What whoever owes it may do. */
export const OWNER: Rights = { ...NOTHING, finish: true, reschedule: true, note: true }

export function makeCommitment(overrides: Partial<Commitment> = {}): Commitment {
  return {
    id: 'co-1',
    description: 'Certificar la obra',
    owner: LEO,
    creator: null,
    owner_left: false,
    due_date: '2026-11-20',
    agreed_due_date: '2026-11-20',
    state: 'overdue',
    completed_on: null,
    times_postponed: 2,
    subject: PLAZA,
    source: 'cabinet',
    origin: { label: 'Reunión del 20/10/2026', path: '/d/cabinet/meetings/me-0' },
    followers: [],
    rights: { ...EVERYTHING, edit: false },
    ...overrides,
  }
}

export function makeInformal(overrides: Partial<Commitment> = {}): Commitment {
  return makeCommitment({
    id: 'co-2',
    description: 'Enviar la nota',
    creator: ANA,
    due_date: '2026-12-01',
    agreed_due_date: '2026-12-01',
    state: 'open',
    times_postponed: 0,
    subject: null,
    source: null,
    origin: null,
    ...overrides,
  })
}

export function makeDetail(overrides: Partial<CommitmentDetail> = {}): CommitmentDetail {
  return { ...makeCommitment(), history: [], ...overrides }
}

export const page = <T>(items: T[], total = items.length): Page<T> => ({ items, total })

export const ASSIGNED: News = { kind: 'assigned', actor: 'Zoe Ruiz', at: '2026-11-23T12:00:00Z' }
export const DONE: News = { kind: 'done', actor: 'Leo Paz', at: '2026-11-23T12:00:00Z' }

export function makeRow(overrides: Partial<NotificationRow> = {}): NotificationRow {
  return {
    id: 'co-1',
    description: 'Certificar la obra',
    owner: ANA,
    due_date: '2026-11-30',
    state: 'open',
    completed_on: null,
    news: [],
    ...overrides,
  }
}

export const NOTIFICATIONS: Notifications = {
  mine: [
    makeRow({ id: 'co-3', description: 'Señalizar', due_date: '2026-11-10', state: 'overdue' }),
    makeRow({ news: [ASSIGNED] }),
  ],
  others: [
    makeRow({
      id: 'co-2',
      description: 'Enviar la nota',
      owner: LEO,
      state: 'done',
      completed_on: '2026-11-22',
      news: [DONE],
    }),
    makeRow({ id: 'co-4', description: 'Pedir fotos', owner: LEO }),
  ],
}
