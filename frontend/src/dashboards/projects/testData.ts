import type { Indicator, Milestone, Project, Summary, Term } from './types'

export const TERM: Term = { id: 't-1', name: 'Gestión 2023-2027', start_year: 2023, end_year: 2027 }
export const OLD_TERM: Term = {
  id: 't-0',
  name: 'Gestión 2019-2023',
  start_year: 2019,
  end_year: 2023,
}
export const AXES = [
  { id: 'a-1', term_id: 't-1', name: 'Ciudad inclusiva' },
  { id: 'a-2', term_id: 't-1', name: 'Ciudad segura' },
]
export const OBJECTIVES = [
  { id: 'o-1', axis_id: 'a-1', name: 'Reducir el déficit habitacional' },
  { id: 'o-2', axis_id: 'a-2', name: 'Más iluminación' },
]
export const DEPARTMENTS = [
  { id: 'd-1', name: 'Obras Públicas' },
  { id: 'd-2', name: 'Salud' },
]
export const PROGRAMS = [{ id: 'p-1', name: 'Plan de bacheo' }]
export const OWNERS = [{ id: 'w-1', full_name: 'María Pérez' }]

export function makeMilestone(overrides: Partial<Milestone> = {}): Milestone {
  return {
    id: 'ms-1',
    name: 'Licitación',
    due_date: '2025-06-01',
    completed_on: null,
    in_alert: false,
    ...overrides,
  }
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'pr-1',
    term_id: TERM.id,
    name: 'Pavimentación',
    description: '',
    axis: AXES[0],
    objective: null,
    department: DEPARTMENTS[0],
    owner: null,
    program: null,
    priority: 'A',
    year: 2024,
    start_date: null,
    end_date: null,
    planned_budget: '0.00',
    executed_budget: '0.00',
    status: 'in_progress',
    effective_status: 'in_progress',
    progress: 0,
    manual_progress: null,
    sdgs: [],
    milestones: [],
    ...overrides,
  }
}

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    status_counts: { not_started: 2, in_progress: 5, delayed: 3, finished: 4 },
    active_count: 10,
    finished_count: 4,
    average_progress: 48,
    budget: {
      total: '1000000.00',
      planned: '400000.00',
      executed: '100000.00',
      planned_ratio: 0.4,
      executed_ratio: 0.25,
    },
    milestones: { total: 20, completed: 12, in_alert: 2 },
    by_department: [{ id: 'd-1', name: 'Obras Públicas', count: 9 }],
    by_owner: [],
    by_program: [],
    by_sdg: [{ sdg: 11, count: 6 }],
    ...overrides,
  }
}

export function makeIndicator(overrides: Partial<Indicator> = {}): Indicator {
  return {
    id: 'i-1',
    name: 'Cuadras pavimentadas',
    unit: 'cuadras',
    baseline: 120,
    target: 200,
    current_value: 150,
    objective: OBJECTIVES[0],
    axis: AXES[0],
    ...overrides,
  }
}
