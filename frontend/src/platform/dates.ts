import { formatDate } from './format'

const TYPED = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/
// What the number keyboard of a phone can write.
const DIGITS = /^(\d{2})(\d{2})(\d{4})$/
const ISO = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * The ISO date (YYYY-MM-DD) a person wrote as day, month and year, or null when it is not
 * a date that exists. Pasting an ISO date works too.
 */
export function parseDate(text: string): string | null {
  const trimmed = text.trim()
  const iso = ISO.exec(trimmed)
  const typed = TYPED.exec(trimmed) ?? DIGITS.exec(trimmed)
  if (!iso && !typed) return null
  const [year, month, day] = iso ? iso.slice(1) : [typed![3], typed![2], typed![1]]
  const date = new Date(0)
  // Unlike the constructor, this does not read year 26 as 1926.
  date.setUTCFullYear(Number(year), Number(month) - 1, Number(day))
  const exists = date.getUTCMonth() === Number(month) - 1 && date.getUTCDate() === Number(day)
  if (!exists || Number(year) < 1900) return null
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
}

/** How a date is shown in a field: empty when there is none. */
export const dateText = (iso: string) => (iso ? formatDate(iso) : '')
