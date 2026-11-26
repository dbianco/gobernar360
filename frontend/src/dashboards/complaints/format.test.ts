import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { clockText, formatDay, formatMonth } from './format'
import { makeClock } from './testData'
import type { TFunction } from 'i18next'

const translate = t as unknown as TFunction

it('writes the day in Argentina, or a dash without one', () => {
  // Past midnight in UTC is still the day before in Argentina.
  expect(formatDay('2026-03-02T01:30:00Z')).toBe('01/03/2026')
  expect(formatDay(null)).toBe('—')
  expect(formatDay(undefined)).toBe('—')
})

it('shortens the month, and shows as it came one that does not exist', () => {
  expect(formatMonth('2026-03', translate)).toBe('Mar 2026')
  expect(formatMonth('2026-13', translate)).toBe('13 2026')
})

it('reads the clock in words', () => {
  const text = (left_days: number) => clockText(makeClock({ left_days }), 'in_progress', translate)
  expect(text(2)).toBe(t('complaints.clockText.left', { count: 2 }))
  expect(text(0)).toBe(t('complaints.clockText.dueToday'))
  expect(text(-3)).toBe(t('complaints.clockText.late', { count: 3 }))
  expect(clockText(makeClock({ used_days: 5 }), 'closed', translate)).toBe(
    t('complaints.clockText.solvedIn', { count: 5 }),
  )
  expect(clockText(makeClock(), 'rejected', translate)).toBe(t('app.none'))
})
