import type { Series, Subcategory, Summary, Value, Variable, VariableSummary } from './types'

export const ENERGY: Subcategory = { id: 's-1', category: 'energy', name: 'Consumo eléctrico' }
export const WATER: Subcategory = { id: 's-2', category: 'water', name: 'Calidad del agua' }
export const SUBCATEGORIES = [ENERGY, WATER]

export const MONTHLY: Variable = {
  id: 'v-1',
  name: 'Consumo del palacio municipal',
  unit: 'kWh',
  frequency: 'monthly',
  target: 12000,
  direction: 'lower_is_better',
  source: 'municipal',
  annual_aggregation: 'sum',
  subcategory: ENERGY,
}
export const ANNUAL: Variable = {
  id: 'v-2',
  name: 'Puntos de monitoreo',
  unit: 'puntos',
  frequency: 'annual',
  target: 10,
  direction: 'higher_is_better',
  source: 'external',
  annual_aggregation: 'sum',
  subcategory: WATER,
}
export const VARIABLES = [MONTHLY, ANNUAL]

export const makeValue = (overrides: Partial<Value> = {}): Value => ({
  variable_id: MONTHLY.id,
  year: new Date().getFullYear(),
  period: 1,
  value: 1000,
  ...overrides,
})

const row = (variable: Variable, overrides: Partial<VariableSummary>): VariableSummary => ({
  variable,
  value: null,
  loaded: 0,
  expected: variable.frequency === 'monthly' ? 12 : 1,
  achievement: null,
  target_met: null,
  ...overrides,
})

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  const rows: Record<string, VariableSummary[]> = {
    energy: [row(MONTHLY, { value: 2500, loaded: 2, achievement: 1, target_met: true })],
    water: [row(ANNUAL, { value: 7.5, loaded: 1, achievement: 0.75, target_met: false })],
  }
  return {
    year: new Date().getFullYear(),
    variable_count: 2,
    loaded: 3,
    expected: 13,
    targets_met: 1,
    targets_missed: 1,
    categories: (
      ['energy', 'waste', 'water', 'air', 'mobility', 'biodiversity', 'governance'] as const
    ).map((category) => {
      const variables = rows[category] ?? []
      return {
        category,
        loaded: variables.reduce((sum, item) => sum + item.loaded, 0),
        expected: variables.reduce((sum, item) => sum + item.expected, 0),
        variables,
      }
    }),
    ...overrides,
  }
}

export function makeSeries(overrides: Partial<Series> = {}): Series {
  return {
    variable: MONTHLY,
    year: new Date().getFullYear(),
    monthly: Array.from({ length: 12 }, (_, index) => ({
      period: index + 1,
      value: index < 3 ? 1000 + index * 100 : null,
    })),
    annual: [
      { year: new Date().getFullYear() - 1, value: 13000, loaded: 12, expected: 12 },
      { year: new Date().getFullYear(), value: 3300, loaded: 3, expected: 12 },
    ],
    ...overrides,
  }
}
