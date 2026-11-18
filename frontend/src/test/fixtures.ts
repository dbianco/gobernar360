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
