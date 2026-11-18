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
