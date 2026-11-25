import { currentYear } from '../years'

/**
 * The day whose boundaries a year's figures use: the last one of a past year, so moving a
 * boundary does not rewrite it. None for this year and the next: today's.
 */
export function boundariesOf(year: number | string | undefined): string | undefined {
  return year !== undefined && Number(year) < currentYear() ? `${year}-12-31` : undefined
}
