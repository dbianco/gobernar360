import { expect, it } from 'vitest'

import { dateText, parseDate } from './dates'

it.each([
  ['24/11/2026', '2026-11-24'],
  [' 5/1/2026 ', '2026-01-05'],
  ['05-01-2026', '2026-01-05'],
  ['5.1.2026', '2026-01-05'],
  ['24112026', '2026-11-24'],
  ['2026-11-24', '2026-11-24'],
  ['29/02/2024', '2024-02-29'],
  ['01/01/1900', '1900-01-01'],
])('reads %s as %s', (text, iso) => {
  expect(parseDate(text)).toBe(iso)
})

it.each([
  '',
  '24/11',
  '24/11/26',
  '24/11/202',
  '2411202',
  '24/11/20266',
  '31/02/2026',
  '29/02/2025',
  '00/01/2026',
  '01/00/2026',
  // Month first, as in the United States, is not a date here.
  '11/24/2026',
  '2026-13-01',
  '2026-02-30',
  '31/12/1899',
  '24/11/2026 a',
  'mañana',
])('does not take %j for a date', (text) => {
  expect(parseDate(text)).toBeNull()
})

it('writes dates as day, month and year, and nothing when there is none', () => {
  expect(dateText('2026-01-05')).toBe('05/01/2026')
  expect(dateText('')).toBe('')
})
