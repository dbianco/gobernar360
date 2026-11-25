import type { FigureValue } from './types'

/** Shades from light to dark: one hue, so the order can be told without its colours. */
export const SHADES = ['#d0ebff', '#74c0fc', '#339af0', '#1864ab']

export interface ShadeStep {
  color: string
  from: number
  to: number
}

const asNumber = (value: FigureValue) => (value === null ? null : Number(value))

/**
 * The steps of a shaded map: as many as there are shades, or fewer when there are fewer
 * different values. Zero and hidden values are not shaded.
 */
export function shadeSteps(values: FigureValue[]): ShadeStep[] {
  const shaded = values
    .map(asNumber)
    .filter((value): value is number => value !== null && value > 0)
  if (shaded.length === 0) return []
  const distinct = [...new Set(shaded)].sort((a, b) => a - b)
  // Even groups of the different values: one very large zone does not turn the rest pale.
  const count = Math.min(SHADES.length, distinct.length)
  return Array.from({ length: count }, (_, step) => ({
    // The last steps of the scale when not all are needed, so that they stay visible.
    color: SHADES[SHADES.length - count + step],
    from: distinct[Math.floor((step * distinct.length) / count)],
    to: distinct[Math.floor(((step + 1) * distinct.length) / count) - 1],
  }))
}

export function shadeOf(value: FigureValue, steps: ShadeStep[]): string | null {
  const number = asNumber(value)
  if (number === null) return null
  return steps.find((step) => number >= step.from && number <= step.to)?.color ?? null
}
