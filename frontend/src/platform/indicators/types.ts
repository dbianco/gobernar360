/** None is a plain count or amount; "percent" is already in percent; "ratio" is 0..1. */
export type IndicatorUnit = 'percent' | 'ratio' | null

export interface IndicatorDefinition {
  key: string
  unit: IndicatorUnit
  higher_is_better: boolean
  /** Whether its past months can be rebuilt from dated records. */
  reconstructible: boolean
}

/** One month of an indicator's last twelve, with the target of that month's year. */
export interface SeriesPoint {
  year: number
  month: number
  value: number | null
  target: number | null
}

/** An indicator today, against its past and against its target. */
export interface IndicatorEvolution {
  key: string
  unit: IndicatorUnit
  /** Null only for combined indicators, where neither direction is better. */
  higher_is_better: boolean | null
  reconstructible: boolean
  value: number | null
  /** At the close of the previous month. */
  previous_value: number | null
  change_previous_month: number | null
  /** At the close of the same month a year ago. */
  last_year_value: number | null
  change_last_year: number | null
  target: number | null
  /** Positive when better than the target, negative when worse, whichever the direction. */
  deviation: number | null
  deviation_ratio: number | null
  on_track: boolean | null
  /** Oldest first; the last point is the current month, as of today. */
  series: SeriesPoint[]
}

/** An indicator relating two dashboards, with the keys of those dashboards. */
export interface CombinedEvolution extends IndicatorEvolution {
  dashboard_keys: string[]
}

/** The indicators recorded for each month of a year; the current month is as of today. */
export interface YearValues {
  year: number
  indicators: IndicatorDefinition[]
  months: { month: number; values: Record<string, number | null> }[]
}

export interface IndicatorTarget extends IndicatorDefinition {
  target: number | null
}
