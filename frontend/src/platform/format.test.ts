import { afterEach, expect, it, vi } from 'vitest'

import {
  formatDate,
  formatDni,
  formatMoney,
  formatNumber,
  formatPercent,
  formatRatio,
  todayIso,
} from './format'

afterEach(() => vi.useRealTimers())

it('writes numbers the Argentine way, with one decimal unless asked', () => {
  expect(formatNumber(1234567.891)).toBe('1.234.567,9')
  expect(formatNumber(1234.5678, 2)).toBe('1.234,57')
  expect(formatNumber(0)).toBe('0')
  expect(formatNumber(null)).toBe('—')
  expect(formatNumber(undefined)).toBe('—')
})

it('writes percentages and ratios', () => {
  expect(formatPercent(42)).toBe('42 %')
  expect(formatPercent(0)).toBe('0 %')
  expect(formatPercent(null)).toBe('—')
  expect(formatRatio(0.256)).toBe('25,6 %')
  expect(formatRatio(0)).toBe('0 %')
  expect(formatRatio(undefined)).toBe('—')
})

it('writes money in pesos without cents', () => {
  expect(formatMoney('85000000.00')).toMatch(/^\$\s?85\.000\.000$/)
  expect(formatMoney(1234.6)).toMatch(/^\$\s?1\.235$/)
  expect(formatMoney(0)).toMatch(/^\$\s?0$/)
  expect(formatMoney(null)).toBe('—')
})

it('writes ISO dates as day/month/year', () => {
  expect(formatDate('2026-03-09')).toBe('09/03/2026')
  expect(formatDate(null)).toBe('—')
  expect(formatDate('')).toBe('—')
})

it('writes documents with dots', () => {
  expect(formatDni('12345678')).toBe('12.345.678')
  expect(formatDni('1234567')).toBe('1.234.567')
  expect(formatDni('123')).toBe('123')
  expect(formatDni(null)).toBe('—')
})

it('gives today in the browser time zone', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 0, 5, 23, 30))

  expect(todayIso()).toBe('2026-01-05')
})
