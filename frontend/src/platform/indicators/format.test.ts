import { expect, it } from 'vitest'

import { formatAmount, formatChange, formatIndicator, trendOf } from './format'

it('writes a value in its unit', () => {
  expect(formatIndicator(1234.5, null)).toBe('1.234,5')
  expect(formatIndicator(42, 'percent')).toBe('42 %')
  expect(formatIndicator(0.256, 'ratio')).toBe('25,6 %')
  expect(formatIndicator(null, 'ratio')).toBe('—')
})

it('writes differences of percentages and ratios in percentage points', () => {
  expect(formatAmount(-2.5, 'percent')).toBe('2,5 p.p.')
  expect(formatAmount(0.05, 'ratio')).toBe('5 p.p.')
  expect(formatAmount(-3, null)).toBe('3')
})

it('signs a change, but not a zero or a missing one', () => {
  expect(formatChange(2, null)).toBe('+2')
  expect(formatChange(-1.5, 'percent')).toBe('\u22121,5 p.p.')
  expect(formatChange(0, null)).toBe('0')
  expect(formatChange(0.0001, 'ratio')).toBe('0 p.p.')
  expect(formatChange(null, null)).toBe('—')
  expect(formatChange(undefined, 'ratio')).toBe('—')
})

it('judges a change by the direction of the indicator', () => {
  expect(trendOf(2, true)).toBe('better')
  expect(trendOf(2, false)).toBe('worse')
  expect(trendOf(-2, false)).toBe('better')
  expect(trendOf(0, true)).toBe('same')
  expect(trendOf(null, true)).toBe('same')
  expect(trendOf(1, null)).toBe('neutral')
})
