import type {
  Benefit,
  Delivery,
  Household,
  HouseholdDetail,
  Intervention,
  Named,
  Page,
  Person,
  Reports,
  SocialPerson,
  Summary,
} from './types'

export const FOOD: Named = { id: 'bc-1', name: 'Alimentos' }
export const HOUSING: Named = { id: 'bc-2', name: 'Hábitat' }
export const BOX: Benefit = {
  id: 'b-1',
  name: 'Módulo alimentario',
  description: 'Caja mensual.',
  category: FOOD,
}
export const SHEETS: Benefit = { id: 'b-2', name: 'Chapas', description: '', category: HOUSING }
export const BENEFITS = [SHEETS, BOX]
export const VISIT: Named = { id: 'it-1', name: 'Visita a domicilio' }
export const INTERVIEW: Named = { id: 'it-2', name: 'Entrevista presencial' }

export function makeRegistryPerson(overrides: Partial<Person> = {}): Person {
  return {
    id: 'p-1',
    first_name: 'Juana',
    last_name: 'Pérez',
    full_name: 'Pérez, Juana',
    dni: '12345678',
    birth_date: '1990-05-01',
    phone: '3472 555111',
    email: '',
    address: 'Belgrano 45',
    neighborhood: 'Centro',
    ...overrides,
  }
}

export const PEREZ_FAMILY: Named = { id: 'h-1', name: 'Familia Pérez' }

export function makePerson(overrides: Partial<SocialPerson> = {}): SocialPerson {
  return {
    id: 'sp-1',
    person: makeRegistryPerson(),
    household: PEREZ_FAMILY,
    relationship: 'head',
    ...overrides,
  }
}

export const LUIS = makePerson({
  id: 'sp-2',
  person: makeRegistryPerson({
    id: 'p-2',
    first_name: 'Luis',
    last_name: 'Gómez',
    full_name: 'Gómez, Luis',
    dni: null,
    neighborhood: '',
  }),
  household: null,
  relationship: null,
})

export function makeHousehold(overrides: Partial<Household> = {}): Household {
  return {
    ...PEREZ_FAMILY,
    address: 'Belgrano 45',
    neighborhood: 'Centro',
    member_count: 2,
    head: { id: 'sp-1', full_name: 'Pérez, Juana' },
    ...overrides,
  }
}

export function makeHouseholdDetail(overrides: Partial<HouseholdDetail> = {}): HouseholdDetail {
  return {
    ...makeHousehold(),
    members: [
      { id: 'sp-1', full_name: 'Pérez, Juana', dni: '12345678', relationship: 'head' },
      { id: 'sp-3', full_name: 'Pérez, Ana', dni: null, relationship: 'child' },
    ],
    ...overrides,
  }
}

export function makeDelivery(overrides: Partial<Delivery> = {}): Delivery {
  return {
    id: 'd-1',
    date: '2026-03-10',
    quantity: 2,
    note: 'Retira la hija',
    benefit: { id: BOX.id, name: BOX.name, category: FOOD },
    person: { id: 'sp-1', full_name: 'Pérez, Juana' },
    ...overrides,
  }
}

export const SECRET = 'Refiere situación de violencia en el hogar.'

export function makeIntervention(overrides: Partial<Intervention> = {}): Intervention {
  return {
    id: 'i-1',
    date: '2026-03-12',
    intervention_type: VISIT,
    person: { id: 'sp-1', full_name: 'Pérez, Juana' },
    performed_by: 'Lic. Marta Ruiz',
    description: SECRET,
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length): Page<T> => ({ items, total })

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    year: 2026,
    people: 16,
    households: 5,
    people_with_deliveries: 9,
    deliveries: 15,
    units: 39,
    interventions: 8,
    people_with_interventions: 7,
    benefits: [
      { benefit: 'Módulo alimentario', category: 'Alimentos', deliveries: 7, units: 8 },
      { benefit: 'Chapas', category: 'Hábitat', deliveries: 1, units: 12 },
    ],
    intervention_types: [
      { name: 'Visita a domicilio', count: 3 },
      { name: 'Entrevista presencial', count: 2 },
    ],
    ...overrides,
  }
}

const months = (counts: Record<number, number>) =>
  Array.from({ length: 12 }, (_, index) => ({ month: index + 1, count: counts[index + 1] ?? 0 }))

export function makeReports(overrides: Partial<Reports> = {}): Reports {
  return {
    year: 2026,
    deliveries_by_category: [
      { name: 'Alimentos', count: 9 },
      { name: 'Hábitat', count: 2 },
    ],
    deliveries_by_month: months({ 3: 6, 4: 5 }),
    interventions_by_type: [
      { name: 'Visita a domicilio', count: 3 },
      { name: 'Entrevista presencial', count: 2 },
    ],
    interventions_by_month: months({ 2: 1, 3: 4 }),
    people_by_neighborhood: [
      { name: 'Sur', count: 7 },
      { name: null, count: 1 },
    ],
    deliveries_by_neighborhood: [
      { name: 'Sur', count: 8 },
      { name: 'Norte', count: 3 },
    ],
    ...overrides,
  }
}
