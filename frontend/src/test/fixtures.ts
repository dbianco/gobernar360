import type { IndicatorEvolution, IndicatorUnit } from '../platform/indicators/types'
import type { AccessLevel, Me } from '../platform/types'

export const NOETINGER = { id: 'm-1', name: 'Noetinger', slug: 'noetinger', kind: 'municipality' }
export const SAIRA = { id: 'm-2', name: 'Saira', slug: 'saira', kind: 'commune' }

export function makeMe(
  options: {
    dashboards?: Record<string, AccessLevel>
    isAdmin?: boolean
    isOperator?: boolean
    municipalities?: (typeof NOETINGER)[]
    active?: string | null
  } = {},
): Me {
  const municipalities = options.municipalities ?? [NOETINGER]
  return {
    user: {
      id: 'u-1',
      email: 'ana@noetinger.test',
      full_name: 'Ana Gómez',
      phone: '',
      is_platform_operator: options.isOperator ?? false,
    },
    memberships: municipalities.map((municipality) => ({
      municipality,
      is_admin: options.isAdmin ?? false,
    })),
    active_municipality_id:
      options.active === undefined ? (municipalities[0]?.id ?? null) : options.active,
    dashboards: Object.entries(options.dashboards ?? {}).map(([key, level]) => ({ key, level })),
  }
}

/**
 * A headline indicator with its evolution, as the API returns it. The series covers the
 * twelve months up to June 2026 and holds no value except today's, unless given.
 */
export function makeEvolution(
  key: string,
  value: number | null,
  unit: IndicatorUnit = null,
  overrides: Partial<IndicatorEvolution> = {},
): IndicatorEvolution {
  const series = Array.from({ length: 12 }, (_, index) => {
    const monthIndex = 2026 * 12 + 5 - 11 + index
    return {
      year: Math.floor(monthIndex / 12),
      month: (monthIndex % 12) + 1,
      value: index === 11 ? value : null,
      target: null,
    }
  })
  return {
    key,
    unit,
    higher_is_better: true,
    reconstructible: false,
    value,
    previous_value: null,
    change_previous_month: null,
    last_year_value: null,
    change_last_year: null,
    target: null,
    deviation: null,
    deviation_ratio: null,
    on_track: null,
    series,
    ...overrides,
  }
}
