import type { Lookup, Person } from '../../platform/people/types'

export type { Lookup, Person }

export interface Named {
  id: string
  name: string
}

export interface ToolSubcategory extends Named {
  category_id: string
}

export const AUDIENCES = ['both', 'actors', 'people'] as const
export type Audience = (typeof AUDIENCES)[number]

export interface Tool extends Named {
  description: string
  audience: Audience
  category: Named
  subcategory: Named | null
}

export const EMPLOYMENT_STATUSES = [
  'unknown',
  'employed',
  'self_employed',
  'unemployed',
  'student',
  'retired',
  'other',
] as const
export type EmploymentStatus = (typeof EMPLOYMENT_STATUSES)[number]

/** A person as this dashboard knows them; `id` is the dashboard's id for the person. */
export interface EconomicPerson {
  id: string
  person: Person
  employment_status: EmploymentStatus
  occupation: string
}

export const ROLES = ['owner', 'contact', 'employee'] as const
export type Role = (typeof ROLES)[number]

export interface Actor extends Named {
  actor_type: Named | null
  sector: Named | null
  cuit: string
  address: string
  phone: string
  email: string
  employee_count: number | null
  notes: string
}

export interface ActorDetail extends Actor {
  people: { id: string; role: Role; person: EconomicPerson }[]
}

export interface PersonDetail extends EconomicPerson {
  actors: { id: string; role: Role; actor: Named }[]
}

export interface Assignment {
  id: string
  date: string
  note: string
  tool: Named
  actor: Named | null
  person: { id: string; full_name: string } | null
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface ToolCount {
  tool: string
  category: string
  count: number
}

export interface Summary {
  year: number
  actors: { total: number; with_assignments: number }
  people: { total: number; with_assignments: number }
  tools: number
  assignments: number
  actor_tools: ToolCount[]
  person_tools: ToolCount[]
}

export interface Reports {
  year: number
  actors_by_type: { name: string | null; count: number }[]
  actors_by_sector: { name: string | null; count: number }[]
  people_by_employment_status: { status: EmploymentStatus; count: number }[]
  assignments_by_category: { name: string | null; count: number }[]
  assignments_by_month: { month: number; count: number }[]
}
