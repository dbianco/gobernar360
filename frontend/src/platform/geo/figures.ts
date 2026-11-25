import { formatMoney, formatNumber } from '../format'
import type { FigureValue, Metric } from './types'

/** A figure as people read it; `hidden` is what a value kept from the member says. */
export function formatFigure(value: FigureValue, metric: Metric, hidden: string): string {
  if (value === null) return hidden
  return metric.unit === 'money' ? formatMoney(value) : formatNumber(Number(value))
}
