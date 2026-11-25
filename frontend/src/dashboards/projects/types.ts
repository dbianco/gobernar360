export type Priority = 'A+' | 'A' | 'B' | 'C'
export type StoredStatus = 'not_started' | 'in_progress' | 'finished'
export type EffectiveStatus = StoredStatus | 'delayed'

export const PRIORITIES: Priority[] = ['A+', 'A', 'B', 'C']
export const STORED_STATUSES: StoredStatus[] = ['not_started', 'in_progress', 'finished']
export const EFFECTIVE_STATUSES: EffectiveStatus[] = [
  'not_started',
  'in_progress',
  'delayed',
  'finished',
]
export const SDG_NUMBERS = Array.from({ length: 17 }, (_, index) => index + 1)

export interface NamedRef {
  id: string
  name: string
}

export interface Term extends NamedRef {
  start_year: number
  end_year: number
}

export interface AnnualBudget {
  year: number
  total_amount: string
}

export interface Axis extends NamedRef {
  term_id: string
}

export interface Objective extends NamedRef {
  axis_id: string
}

export interface Owner {
  id: string
  full_name: string
}

export interface Milestone {
  id: string
  name: string
  due_date: string
  completed_on: string | null
  in_alert: boolean
}

export interface Project {
  id: string
  term_id: string
  name: string
  description: string
  axis: NamedRef
  objective: NamedRef | null
  department: NamedRef
  owner: Owner | null
  program: NamedRef | null
  priority: Priority
  year: number
  start_date: string | null
  end_date: string | null
  planned_budget: string
  executed_budget: string
  status: StoredStatus
  effective_status: EffectiveStatus
  progress: number
  manual_progress: number | null
  sdgs: number[]
  milestones: Milestone[]
  zones: NamedRef[]
}

/** Body of a project create or update request. */
export interface ProjectInput {
  term_id?: string
  name: string
  description: string
  axis_id: string
  objective_id: string | null
  department_id: string
  owner_id: string | null
  program_id: string | null
  priority: Priority
  year: number
  start_date: string | null
  end_date: string | null
  planned_budget: string
  executed_budget: string
  status: StoredStatus
  manual_progress: number | null
  sdgs: number[]
}

export interface Indicator {
  id: string
  name: string
  unit: string
  baseline: number | null
  target: number | null
  current_value: number | null
  objective: NamedRef
  axis: NamedRef
}

export interface GroupCount extends NamedRef {
  count: number
}

export interface Summary {
  status_counts: Record<EffectiveStatus, number>
  active_count: number
  finished_count: number
  average_progress: number
  budget: {
    total: string | null
    planned: string
    executed: string
    planned_ratio: number | null
    executed_ratio: number | null
  }
  milestones: { total: number; completed: number; in_alert: number }
  by_department: GroupCount[]
  by_owner: GroupCount[]
  by_program: GroupCount[]
  by_sdg: { sdg: number; count: number }[]
}

export interface ProjectFilters {
  year?: string
  axis_id?: string
  department_id?: string
  owner_id?: string
  priority?: string
  status?: string
}
