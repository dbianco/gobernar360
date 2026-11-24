import type { Lookup } from '../../platform/people/types'

/** A resident not in the registry yet, added to it with the complaint. */
export interface NewPerson {
  first_name: string
  last_name: string
  phone: string
  email: string
}

/** Who complains, as the complaint form holds it. */
export interface Complainant {
  anonymous: boolean
  dni: string
  /** What the registry answered, and for which document. */
  lookup: { dni: string; result: Lookup } | null
  newPerson: NewPerson
}

export const EMPTY_COMPLAINANT: Complainant = {
  anonymous: true,
  dni: '',
  lookup: null,
  newPerson: { first_name: '', last_name: '', phone: '', email: '' },
}

export const normaliseDni = (value: string) => value.replace(/[.\s]/g, '')
export const validDni = (value: string) => /^\d{6,9}$/.test(normaliseDni(value))

/** The registry's answer about the document currently typed, if it was asked. */
export function currentLookup(value: Complainant): Lookup | null {
  return value.lookup?.dni === normaliseDni(value.dni) ? value.lookup.result : null
}
