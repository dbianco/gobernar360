import type {
  Actor,
  ActorDetail,
  Assignment,
  EconomicPerson,
  Named,
  Person,
  PersonDetail,
  Reports,
  Summary,
  Tool,
  ToolSubcategory,
} from './types'

export const SHOP: Named = { id: 'at-1', name: 'Comercio' }
export const INDUSTRY: Named = { id: 'at-2', name: 'Industria' }
export const FOOD: Named = { id: 'se-1', name: 'Alimentos' }
export const FINANCE: Named = { id: 'tc-1', name: 'Financiamiento' }
export const TRAINING: Named = { id: 'tc-2', name: 'Capacitación' }
export const MICROCREDITS: ToolSubcategory = {
  id: 'ts-1',
  category_id: FINANCE.id,
  name: 'Microcréditos',
}
export const COURSES: ToolSubcategory = { id: 'ts-2', category_id: TRAINING.id, name: 'Cursos' }

export const CREDIT: Tool = {
  id: 't-1',
  name: 'Microcrédito productivo',
  description: 'Hasta $ 1.500.000.',
  audience: 'both',
  category: FINANCE,
  subcategory: MICROCREDITS,
}
export const FAIR: Tool = {
  id: 't-2',
  name: 'Feria de emprendedores',
  description: '',
  audience: 'actors',
  category: TRAINING,
  subcategory: null,
}
export const WORKSHOP: Tool = {
  id: 't-3',
  name: 'Taller de oficios',
  description: '',
  audience: 'people',
  category: TRAINING,
  subcategory: COURSES,
}
export const TOOLS = [CREDIT, FAIR, WORKSHOP]

export function makeActor(overrides: Partial<Actor> = {}): Actor {
  return {
    id: 'a-1',
    name: 'Panadería La Espiga',
    actor_type: SHOP,
    sector: FOOD,
    cuit: '30711111118',
    address: 'San Martín 245',
    phone: '3472 555111',
    email: 'espiga@example.test',
    employee_count: 6,
    notes: '',
    ...overrides,
  }
}

export function makeRegistryPerson(overrides: Partial<Person> = {}): Person {
  const person = {
    id: 'p-1',
    first_name: 'Juana',
    last_name: 'Pérez',
    dni: '12345678',
    birth_date: '1990-05-01',
    phone: '3472 555222',
    email: '',
    address: 'Belgrano 45',
    neighborhood: 'Centro',
    ...overrides,
  }
  return { ...person, full_name: overrides.full_name ?? `${person.last_name}, ${person.first_name}` }
}

export function makePerson(
  overrides: Partial<Omit<EconomicPerson, 'person'>> & { person?: Partial<Person> } = {},
): EconomicPerson {
  return {
    id: 'ep-1',
    employment_status: 'self_employed',
    occupation: 'Costurera',
    ...overrides,
    person: makeRegistryPerson(overrides.person),
  }
}

export const LUIS = makePerson({
  id: 'ep-2',
  employment_status: 'unemployed',
  occupation: '',
  person: { id: 'p-2', first_name: 'Luis', last_name: 'Acosta', dni: '22333444' },
})

export function makeActorDetail(overrides: Partial<ActorDetail> = {}): ActorDetail {
  return { ...makeActor(), people: [{ id: 'l-1', role: 'owner', person: makePerson() }], ...overrides }
}

export function makePersonDetail(overrides: Partial<PersonDetail> = {}): PersonDetail {
  return {
    ...makePerson(),
    actors: [{ id: 'l-1', role: 'owner', actor: { id: 'a-1', name: 'Panadería La Espiga' } }],
    ...overrides,
  }
}

export function makeAssignment(overrides: Partial<Assignment> = {}): Assignment {
  return {
    id: 'as-1',
    date: '2026-03-10',
    note: 'Primera cuota',
    tool: { id: CREDIT.id, name: CREDIT.name },
    actor: { id: 'a-1', name: 'Panadería La Espiga' },
    person: null,
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length) => ({ items, total })

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    year: 2026,
    actors: { total: 12, with_assignments: 5 },
    people: { total: 14, with_assignments: 4 },
    tools: 6,
    assignments: 21,
    actor_tools: [{ tool: 'Feria de emprendedores', category: 'Comercialización', count: 3 }],
    person_tools: [{ tool: 'Taller de oficios', category: 'Capacitación', count: 2 }],
    ...overrides,
  }
}

export function makeReports(overrides: Partial<Reports> = {}): Reports {
  return {
    year: 2026,
    actors_by_type: [
      { name: 'Comercio', count: 4 },
      { name: null, count: 1 },
    ],
    actors_by_sector: [{ name: 'Alimentos', count: 5 }],
    people_by_employment_status: [
      { status: 'self_employed', count: 4 },
      { status: 'unemployed', count: 2 },
    ],
    assignments_by_category: [{ name: 'Capacitación', count: 9 }],
    assignments_by_month: Array.from({ length: 12 }, (_, index) => ({
      month: index + 1,
      count: index === 2 ? 7 : 0,
    })),
    ...overrides,
  }
}
