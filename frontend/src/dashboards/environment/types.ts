export const CATEGORIES = [
  'energy',
  'waste',
  'water',
  'air',
  'mobility',
  'biodiversity',
  'governance',
] as const
export type Category = (typeof CATEGORIES)[number]

export const FREQUENCIES = ['monthly', 'annual'] as const
export const DIRECTIONS = ['higher_is_better', 'lower_is_better'] as const
export const SOURCES = ['municipal', 'external'] as const
export const AGGREGATIONS = ['sum', 'average', 'last'] as const

/** Period of a value loaded for the whole year; months are 1 to 12. */
export const WHOLE_YEAR = 0
export const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const

export interface Subcategory {
  id: string
  category: Category
  name: string
}

export interface Variable {
  id: string
  name: string
  unit: string
  frequency: (typeof FREQUENCIES)[number]
  target: number | null
  direction: (typeof DIRECTIONS)[number]
  source: (typeof SOURCES)[number]
  annual_aggregation: (typeof AGGREGATIONS)[number]
  subcategory: Subcategory
}

export interface Value {
  variable_id: string
  year: number
  period: number
  value: number
}

export interface VariableSummary {
  variable: Variable
  /** The year's figure, from the values loaded so far. */
  value: number | null
  loaded: number
  expected: number
  /** Share of the target reached; 1 means met. */
  achievement: number | null
  target_met: boolean | null
}

export interface CategorySummary {
  category: Category
  loaded: number
  expected: number
  variables: VariableSummary[]
}

export interface Summary {
  year: number
  variable_count: number
  loaded: number
  expected: number
  targets_met: number
  targets_missed: number
  categories: CategorySummary[]
}

export interface Series {
  variable: Variable
  year: number
  monthly: { period: number; value: number | null }[]
  annual: { year: number; value: number; loaded: number; expected: number }[]
}
