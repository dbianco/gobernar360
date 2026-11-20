import { formatMoney } from '../../platform/format'
import type { Procedure } from './types'

/** What the person pays, as shown in lists and the detail view. */
export function costText(procedure: Pick<Procedure, 'is_free' | 'cost'>, freeText: string): string {
  if (procedure.is_free) return freeText
  return formatMoney(procedure.cost)
}
