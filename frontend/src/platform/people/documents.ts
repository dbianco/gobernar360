import { EMPTY } from '../format'
import type { DocumentQuery } from './types'

// The same rules the API has (platform/people.py).
const DNI = /^\d{6,9}$/
const CUIL = /^\d{11}$/
const CUIL_WEIGHTS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

export const normaliseDni = (value: string) => value.replace(/[.\s]/g, '')
export const validDni = (value: string) => DNI.test(normaliseDni(value))

export const normaliseCuil = (value: string) => value.replace(/[-.\s]/g, '')

/** Eleven digits, the last of which depends on the rest. */
export function validCuil(value: string): boolean {
  const cuil = normaliseCuil(value)
  if (!CUIL.test(cuil)) return false
  const total = CUIL_WEIGHTS.reduce((sum, weight, index) => sum + weight * Number(cuil[index]), 0)
  const digit = 11 - (total % 11)
  return (digit === 11 ? 0 : digit) === Number(cuil[10])
}

/** Whether a CUIL is of a document: it has it inside, padded to eight digits. */
export const cuilHasDni = (cuil: string, dni: string) =>
  normaliseCuil(cuil).slice(2, 10) === normaliseDni(dni).padStart(8, '0')

/** 20123456786 -> 20-12345678-6 */
export const formatCuil = (cuil: string | null): string =>
  cuil ? cuil.replace(/^(\d{2})(\d{8})(\d)$/, '$1-$2-$3') : EMPTY

/** What to ask the registry about: somebody is looked up by one of the two. */
export function documentQuery(typed: string): DocumentQuery | null {
  if (validDni(typed)) return { dni: normaliseDni(typed) }
  if (validCuil(typed)) return { cuil: normaliseCuil(typed) }
  return null
}
