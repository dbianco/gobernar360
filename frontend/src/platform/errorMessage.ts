import { ApiError } from '../api/client'
import i18n from '../i18n'

/** Text to show a person for a failed request. */
export function errorMessage(error: unknown): string {
  const code = error instanceof ApiError ? error.code : 'generic'
  return i18n.t([`errors.${code}`, 'errors.generic'])
}
