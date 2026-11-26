import { cuilHasDni, documentQuery, normaliseCuil, validCuil } from '../../platform/people/documents'
import type { DocumentQuery, Lookup } from '../../platform/people/types'

/** A resident not in the registry yet, added to it with the complaint. */
export interface NewPerson {
  first_name: string
  last_name: string
  cuil: string
  phone: string
  email: string
}

/** Who complains, as the complaint form holds it. */
export interface Complainant {
  anonymous: boolean
  /** Their DNI or their CUIL, as typed. */
  document: string
  /** What the registry answered, and about which document. */
  lookup: { document: string; result: Lookup } | null
  newPerson: NewPerson
}

export const EMPTY_COMPLAINANT: Complainant = {
  anonymous: true,
  document: '',
  lookup: null,
  newPerson: { first_name: '', last_name: '', cuil: '', phone: '', email: '' },
}

/** What tells a document from any other. */
export const documentKey = (query: DocumentQuery): string => query.dni ?? query.cuil

/** The registry's answer about the document currently typed, if it was asked. */
export function currentLookup(value: Complainant): Lookup | null {
  const query = documentQuery(value.document)
  if (query === null || value.lookup?.document !== documentKey(query)) return null
  return value.lookup.result
}

/**
 * What is wrong with the CUIL of the person to add, as a text of `people`. Somebody looked up
 * by their document may also say theirs; whoever was looked up by CUIL already did.
 */
export function cuilProblem(value: Complainant): 'cuilInvalid' | 'cuilMismatch' | null {
  const { cuil } = value.newPerson
  const dni = documentQuery(value.document)?.dni
  if (cuil === '' || dni === undefined) return null
  if (!validCuil(cuil)) return 'cuilInvalid'
  return cuilHasDni(cuil, dni) ? null : 'cuilMismatch'
}

/** The person to add to the registry with the complaint. */
export function newPersonOf(value: Complainant): Record<string, unknown> {
  const { cuil, ...rest } = value.newPerson
  // Looked up by CUIL, that is the only document known of them.
  return { ...rest, cuil: normaliseCuil(cuil) || null, ...documentQuery(value.document) }
}
