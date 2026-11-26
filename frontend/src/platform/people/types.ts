/** A person's data in the municipality's registry, shared by every dashboard. */
export interface Person {
  id: string
  first_name: string
  last_name: string
  full_name: string
  dni: string | null
  /** Their tax number, 11 digits: the user name of their CiDi account, if they have one. */
  cuil: string | null
  birth_date: string | null
  phone: string
  email: string
  address: string
  neighborhood: string
}

/** Somebody is looked up in the registry by exact document, or by exact CUIL. */
export type DocumentQuery = { dni: string; cuil?: undefined } | { cuil: string; dni?: undefined }

/** What the registry answers about a document. */
export interface Lookup {
  person: Person | null
  /** The asking dashboard's id for the person, when it already incorporated them. */
  registered_id: string | null
}

/** The registry data a dashboard sends when it adds or edits a person. */
export type PersonBody = Omit<Person, 'id' | 'full_name'>
