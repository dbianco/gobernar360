/** A person's data in the municipality's registry, shared by every dashboard. */
export interface Person {
  id: string
  first_name: string
  last_name: string
  full_name: string
  dni: string | null
  birth_date: string | null
  phone: string
  email: string
  address: string
  neighborhood: string
}

/** What the registry answers about a document number. */
export interface Lookup {
  person: Person | null
  /** The asking dashboard's id for the person, when it already incorporated them. */
  registered_id: string | null
}

/** The registry data a dashboard sends when it adds or edits a person. */
export type PersonBody = Omit<Person, 'id' | 'full_name'>
