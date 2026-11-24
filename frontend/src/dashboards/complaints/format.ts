import type { TFunction } from 'i18next'

import type { Clock, State } from './types'

const TIME_ZONE = 'America/Argentina/Buenos_Aires'
const EMPTY = '—'

function parts(value: string, options: Intl.DateTimeFormatOptions) {
  const formatted = new Intl.DateTimeFormat('es-AR', { timeZone: TIME_ZONE, ...options })
    .formatToParts(new Date(value))
    .map((part) => [part.type, part.value])
  return Object.fromEntries(formatted) as Record<string, string>
}

/** An ISO moment as DD/MM/YYYY HH:mm in Argentine time. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return EMPTY
  const p = parts(value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}`
}

/** The Argentine calendar day of an ISO moment, as DD/MM/YYYY. */
export function formatDay(value: string | null | undefined): string {
  if (!value) return EMPTY
  const p = parts(value, { day: '2-digit', month: '2-digit', year: 'numeric' })
  return `${p.day}/${p.month}/${p.year}`
}

/** "2026-03" -> "Mar 2026" with the locale's month names. */
export function formatMonth(month: string, t: TFunction): string {
  const [year, number] = month.split('-')
  const names = t('app.monthNames', { returnObjects: true }) as string[]
  return `${names[Number(number) - 1]?.slice(0, 3) ?? number} ${year}`
}

const isFinished = (state: State) => ['resolved', 'closed', 'rejected'].includes(state)

/** How the clock of a complaint reads in words: days left, due today, late or solved. */
export function clockText(clock: Clock, state: State, t: TFunction): string {
  const key = (name: string, count: number) => t(`complaints.clockText.${name}`, { count })
  if (state === 'rejected') return t('app.none')
  if (isFinished(state)) return key('solvedIn', clock.used_days)
  if (clock.left_days < 0) return key('late', -clock.left_days)
  if (clock.left_days === 0) return t('complaints.clockText.dueToday')
  return key('left', clock.left_days)
}
