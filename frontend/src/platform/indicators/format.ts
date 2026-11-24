import { formatNumber, formatPercent, formatRatio } from '../format'
import type { IndicatorUnit } from './types'

const MINUS = '\u2212'

/** The translation key of an indicator's name. */
export const indicatorLabelKey = (key: string) => `overview.indicators.${key}`

/** The translation key of what an indicator measures. */
export const indicatorDescriptionKey = (key: string) => `overview.descriptions.${key}`

/** An indicator's value in its unit: "12", "42 %", "25,6 %". */
export function formatIndicator(value: number | null | undefined, unit: IndicatorUnit): string {
  if (unit === 'percent') return formatPercent(value)
  if (unit === 'ratio') return formatRatio(value)
  return formatNumber(value, 2)
}

/**
 * A difference between two values of an indicator, without its sign. Percentages and
 * ratios differ in percentage points: 0,25 -> 0,30 is "5 p.p.", not "5 %".
 */
export function formatAmount(value: number, unit: IndicatorUnit): string {
  const magnitude = Math.abs(value)
  if (unit === 'percent') return `${formatNumber(magnitude)} p.p.`
  if (unit === 'ratio') return `${formatNumber(magnitude * 100)} p.p.`
  return formatNumber(magnitude, 2)
}

/** A change with its sign: "+2", "−1,5 p.p.", "0". */
export function formatChange(value: number | null | undefined, unit: IndicatorUnit): string {
  if (value === null || value === undefined) return formatNumber(null)
  const amount = formatAmount(value, unit)
  if (amount === formatAmount(0, unit)) return amount
  return `${value > 0 ? '+' : MINUS}${amount}`
}

export type Trend = 'better' | 'worse' | 'same' | 'neutral'

/** Whether a change is good news, given the indicator's direction. */
export function trendOf(change: number | null, higherIsBetter: boolean | null): Trend {
  if (change === null || change === 0) return 'same'
  if (higherIsBetter === null) return 'neutral'
  return change > 0 === higherIsBetter ? 'better' : 'worse'
}
