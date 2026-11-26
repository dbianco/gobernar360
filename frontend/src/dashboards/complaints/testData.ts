import type {
  Calendar,
  Clock,
  Complaint,
  ComplaintDetail,
  ComplaintType,
  Named,
  Queue,
  Summary,
  TimelineEvent,
} from './types'

export const LIGHTS: Named = { id: 'ar-1', name: 'Alumbrado Público' }
export const WORKS: Named = { id: 'ar-2', name: 'Obras Públicas' }
export const CENTRE: Named = { id: 'zo-1', name: 'Centro' }
export const NORTH: Named = { id: 'zo-2', name: 'Norte' }

export const LAMP: ComplaintType = {
  id: 'ty-1',
  name: 'Luminaria apagada',
  area: LIGHTS,
  target_days: 3,
  is_active: true,
}
export const POTHOLE: ComplaintType = {
  id: 'ty-2',
  name: 'Bache',
  area: WORKS,
  target_days: 15,
  is_active: true,
}
export const RETIRED: ComplaintType = {
  id: 'ty-3',
  name: 'Operativo de ramas',
  area: LIGHTS,
  target_days: 10,
  is_active: false,
}
export const TYPES = [POTHOLE, LAMP, RETIRED]

export const CALENDAR: Calendar = {
  weekdays: [1, 2, 3, 4, 5],
  holidays: [{ id: 'ho-1', date: '2026-03-24', name: 'Día de la Memoria' }],
}

export function makeClock(overrides: Partial<Clock> = {}): Clock {
  return {
    target_days: 3,
    used_days: 1,
    left_days: 2,
    deadline: '2026-03-05',
    status: 'on_time',
    paused: false,
    resolved_on: null,
    ...overrides,
  }
}

export function makeComplaint(overrides: Partial<Complaint> = {}): Complaint {
  return {
    id: 'co-1',
    number: 101,
    received_at: '2026-03-02T12:30:00Z',
    type: { id: LAMP.id, name: LAMP.name },
    area: LIGHTS,
    zone: CENTRE,
    address: 'San Martín 450',
    state: 'in_progress',
    person: { id: 'pe-1', full_name: 'Fernández, Lucía' },
    clock: makeClock(),
    ...overrides,
  }
}

const event = (overrides: Partial<TimelineEvent>): TimelineEvent => ({
  id: 'ev-0',
  kind: 'transition',
  from_state: null,
  to_state: null,
  from_area: null,
  to_area: null,
  from_type: null,
  to_type: null,
  note: '',
  at: '2026-03-02T12:30:00Z',
  user: { id: 'us-1', full_name: 'Carla Carga' },
  ...overrides,
})

export const TIMELINE: TimelineEvent[] = [
  event({ id: 'ev-1', kind: 'created', to_state: 'received', to_area: LIGHTS }),
  event({
    id: 'ev-2',
    from_state: 'received',
    to_state: 'assigned',
    at: '2026-03-02T13:00:00Z',
  }),
  event({
    id: 'ev-3',
    from_state: 'assigned',
    to_state: 'in_progress',
    note: 'Cuadrilla en camino',
    at: '2026-03-03T14:15:00Z',
    user: null,
  }),
]

export function makeDetail(overrides: Partial<ComplaintDetail> = {}): ComplaintDetail {
  const { person: _person, ...complaint } = makeComplaint()
  return {
    ...complaint,
    description: 'No enciende desde el martes.',
    person: {
      id: 'pe-1',
      full_name: 'Fernández, Lucía',
      dni: '33123456',
      phone: '3472 55-1234',
    },
    moves: ['waiting', 'resolved', 'rejected'],
    timeline: TIMELINE,
    notices: [],
    ...overrides,
  }
}

export const QUEUES: Queue[] = [
  { area: LIGHTS, open: 4, at_risk: 1, overdue: 2, paused: 1 },
  { area: WORKS, open: 0, at_risk: 0, overdue: 0, paused: 0 },
]

const resolution = {
  received: 10,
  resolved: 8,
  on_time: 6,
  on_time_ratio: 0.75,
  median_days: 4,
  p90_days: 8.8,
}

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    period: { from: '2025-04-01', to: '2026-03-20' },
    repeat_days: 30,
    backlog: {
      open: 7,
      overdue: 2,
      at_risk: 1,
      paused: 1,
      by_state: [
        { state: 'received', count: 2 },
        { state: 'assigned', count: 1 },
        { state: 'in_progress', count: 3 },
        { state: 'waiting', count: 1 },
        { state: 'reopened', count: 0 },
      ],
      by_status: [
        { status: 'on_time', count: 4 },
        { status: 'at_risk', count: 1 },
        { status: 'overdue', count: 2 },
      ],
      ageing: [
        { min_days: 0, max_days: 7, count: 3 },
        { min_days: 8, max_days: 15, count: 2 },
        { min_days: 91, max_days: null, count: 2 },
      ],
    },
    totals: { ...resolution, received: 18, resolved: 14, on_time: 10, on_time_ratio: 10 / 14 },
    monthly: [
      { month: '2026-02', received: 8, resolved: 6 },
      { month: '2026-03', received: 10, resolved: 8 },
    ],
    by_type: [{ id: LAMP.id, name: LAMP.name, ...resolution }],
    by_area: [{ id: LIGHTS.id, name: LIGHTS.name, ...resolution, median_days: 5.5 }],
    repeated: [
      {
        type: LAMP.name,
        address: 'San Martín 450',
        zone: 'Centro',
        count: 3,
        first_received: '2026-03-02',
        last_received: '2026-03-18',
        numbers: [101, 107, 112],
      },
    ],
    top_zones: [{ name: 'Centro', count: 12 }],
    top_types: [{ name: LAMP.name, count: 10 }],
    ...overrides,
  }
}

export function emptySummary(): Summary {
  const none = {
    received: 0,
    resolved: 0,
    on_time: 0,
    on_time_ratio: null,
    median_days: null,
    p90_days: null,
  }
  return makeSummary({
    backlog: {
      open: 0,
      overdue: 0,
      at_risk: 0,
      paused: 0,
      by_state: [],
      by_status: [],
      ageing: [],
    },
    totals: none,
    monthly: [],
    by_type: [],
    by_area: [],
    repeated: [],
    top_zones: [],
    top_types: [],
  })
}
