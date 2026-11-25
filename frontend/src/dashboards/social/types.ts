import type { Lookup, Person } from '../../platform/people/types'

export type { Lookup, Person }

export interface Named {
  id: string
  name: string
}

export interface Benefit extends Named {
  description: string
  category: Named
}

export const RELATIONSHIPS = [
  'head',
  'partner',
  'child',
  'parent',
  'sibling',
  'grandparent',
  'grandchild',
  'other_relative',
  'non_relative',
] as const
export type Relationship = (typeof RELATIONSHIPS)[number]

/** A person as this dashboard knows them; `id` is the dashboard's id for the person. */
export interface SocialPerson {
  id: string
  person: Person
  household: Named | null
  relationship: Relationship | null
}

export interface PersonRef {
  id: string
  full_name: string
}

export interface Household extends Named {
  address: string
  neighborhood: string
  member_count: number
  head: PersonRef | null
  /** Null for members who may not know where one household lives. */
  zones: Named[] | null
}

export interface Member extends PersonRef {
  dni: string | null
  relationship: Relationship
}

export interface HouseholdDetail extends Household {
  members: Member[]
}

export interface Delivery {
  id: string
  date: string
  quantity: number
  note: string
  benefit: Named & { category: Named }
  person: PersonRef
}

export interface Intervention {
  id: string
  date: string
  intervention_type: Named
  person: PersonRef
  performed_by: string
  /** null when the reader's level may not see this reserved text. */
  description: string | null
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface NameCount {
  name: string | null
  count: number
}

export interface MonthCount {
  month: number
  count: number
}

export interface Summary {
  year: number
  people: number
  households: number
  people_with_deliveries: number
  deliveries: number
  units: number
  interventions: number
  people_with_interventions: number
  benefits: { benefit: string; category: string; deliveries: number; units: number }[]
  intervention_types: NameCount[]
}

export interface Reports {
  year: number
  deliveries_by_category: NameCount[]
  deliveries_by_month: MonthCount[]
  interventions_by_type: NameCount[]
  interventions_by_month: MonthCount[]
  people_by_neighborhood: NameCount[]
  deliveries_by_neighborhood: NameCount[]
}

/** Which person's or household's records a list shows. */
export type RecordScope = { person_id: string } | { household_id: string }
