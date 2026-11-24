import type { IndicatorUnit } from '../platform/indicators/types'
import type { StatusColor } from '../platform/status/types'

/** A value shown to the public: `value` is null and `below` set when it is a small count. */
export interface PublicPoint {
  year: number
  month: number
  value: number | null
  below: number | null
  target: number | null
}

export interface PublicIndicator {
  key: string
  name: string
  dashboard_key: string
  unit: IndicatorUnit
  higher_is_better: boolean
  value: number | null
  value_below: number | null
  previous_value: number | null
  previous_below: number | null
  change_previous_month: number | null
  last_year_value: number | null
  last_year_below: number | null
  change_last_year: number | null
  target: number | null
  on_track: boolean | null
  series: PublicPoint[]
}

export interface PublicSite {
  slug: string
  name: string
  kind: 'municipality' | 'commune'
  small_count_threshold: number
  dashboards: {
    key: string
    name: string
    /** Oldest first. */
    lights: { year: number; month: number; color: StatusColor }[]
  }[]
  indicators: PublicIndicator[]
  reports: { year: number; month: number; version: number; closed_at: string }[]
}
