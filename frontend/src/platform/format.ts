const LOCALE = 'es-AR'
const EMPTY = '—'

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 1): string {
  if (value === null || value === undefined) return EMPTY
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(value)
}

/** A value already expressed in percent, e.g. 42 -> "42 %". */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  return `${formatNumber(value)} %`
}

/** A 0..1 ratio shown as a percentage, e.g. 0.256 -> "25,6 %". */
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  return formatPercent(value * 100)
}

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

/** An ISO date (YYYY-MM-DD) as DD/MM/YYYY, without time-zone shifts. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return EMPTY
  const [year, month, day] = value.split('-')
  return `${day}/${month}/${year}`
}

/** An ISO moment as DD/MM/YYYY HH:mm in Argentine time. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return EMPTY
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat(LOCALE, {
      timeZone: 'America/Argentina/Buenos_Aires',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(value))
      .map((part) => [part.type, part.value]),
  )
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`
}

/** 12345678 -> 12.345.678 */
export function formatDni(dni: string | null): string {
  return dni ? dni.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : EMPTY
}

/** Today's date as YYYY-MM-DD in the browser's time zone. */
export function todayIso(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** The date of an ISO timestamp, in the browser's time zone, as DD/MM/YYYY. */
export function formatTimestampDate(value: string | null | undefined): string {
  if (!value) return EMPTY
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(value))
}
