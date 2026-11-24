import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { clockText, formatDateTime, formatDay, formatMonth } from './format'
import { makeClock } from './testData'

it('shows moments and days in Argentine time', () => {
  // 02:30 UTC on the 3rd is still the 2nd in Buenos Aires.
  expect(formatDateTime('2026-03-03T02:30:00Z')).toBe('02/03/2026 23:30')
  expect(formatDay('2026-03-03T02:30:00Z')).toBe('02/03/2026')
  expect(formatDateTime(null)).toBe('—')
  expect(formatMonth('2026-03', t as never)).toBe('Mar 2026')
})

it('reads the clock in words', () => {
  const say = (overrides: Parameters<typeof makeClock>[0], state = 'in_progress' as const) =>
    clockText(makeClock(overrides), state, t as never)

  expect(say({ left_days: 2 })).toBe(t('complaints.clockText.left', { count: 2 }))
  expect(say({ left_days: 1 })).toBe('Queda 1 día hábil')
  expect(say({ left_days: 0 })).toBe(t('complaints.clockText.dueToday'))
  expect(say({ left_days: -3 })).toBe('Vencido por 3 días hábiles')
  expect(clockText(makeClock({ used_days: 4 }), 'closed', t as never)).toBe(
    'Resuelto en 4 días hábiles',
  )
  expect(clockText(makeClock(), 'rejected', t as never)).toBe('—')
})

it('shows a dash for a missing day', () => {
  expect(formatDay(null)).toBe('—')
  expect(formatDay('')).toBe('—')
})
