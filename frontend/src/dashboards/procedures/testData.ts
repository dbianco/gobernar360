import type {
  Named,
  Opportunities,
  Page,
  Procedure,
  ProcedureDetail,
  Requirement,
  RequirementLink,
  Source,
  Summary,
} from './types'

export const RENTAS: Named = { id: 'ar-1', name: 'Rentas' }
export const OBRAS: Named = { id: 'ar-2', name: 'Obras Privadas' }

export const RENTAS_SOURCE: Source = {
  id: 'so-1',
  name: 'Rentas municipal',
  level: 'municipal',
  area: RENTAS,
}
export const RENAPER: Source = { id: 'so-2', name: 'RENAPER', level: 'national', area: null }

export const FREE_DEBT: Requirement = {
  id: 'rq-1',
  name: 'Libre deuda municipal',
  description: 'Certificado de no adeudar tasas.',
  source: RENTAS_SOURCE,
  procedure_count: 4,
}
export const DNI: Requirement = {
  id: 'rq-2',
  name: 'DNI',
  description: '',
  source: RENAPER,
  procedure_count: 9,
}
export const FORM: Requirement = {
  id: 'rq-3',
  name: 'Formulario de solicitud',
  description: 'Lo completa el solicitante.',
  source: null,
  procedure_count: 0,
}
export const REQUIREMENTS = [DNI, FORM, FREE_DEBT]

export function makeProcedure(overrides: Partial<Procedure> = {}): Procedure {
  return {
    id: 'pr-1',
    name: 'Habilitación comercial',
    description: 'Para abrir un local.',
    area: RENTAS,
    audience: 'organizations',
    channel: 'in_person',
    url: '',
    cidi_level: null,
    fully_digital: false,
    is_free: false,
    cost: '25000.00',
    duration_days: 20,
    annual_volume: 180,
    is_active: true,
    requirement_count: 2,
    ...overrides,
  }
}

export function makeLink(overrides: Partial<RequirementLink> = {}): RequirementLink {
  return { id: 'ln-1', requirement: FREE_DEBT, mandatory: true, format: 'paper', note: '', ...overrides }
}

export function makeDetail(overrides: Partial<ProcedureDetail> = {}): ProcedureDetail {
  return {
    ...makeProcedure(),
    requirements: [
      makeLink({ id: 'ln-2', requirement: DNI, mandatory: false, format: 'digital', note: 'Copia.' }),
      makeLink(),
    ],
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length): Page<T> => ({ items, total })

export function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    procedures: 12,
    online: 5,
    cidi: 3,
    cidi_ratio: 0.6,
    digital: 2,
    digital_ratio: 0.1667,
    average_requirements: 3.4,
    requirements: 16,
    sources: 11,
    by_area: [
      { name: 'Rentas', count: 7 },
      { name: 'Obras Privadas', count: 5 },
    ],
    by_channel: [
      { channel: 'in_person', count: 7 },
      { channel: 'online', count: 2 },
      { channel: 'both', count: 3 },
    ],
    by_cidi_level: [
      { level: 1, count: 1 },
      { level: 2, count: 2 },
      { level: 3, count: 0 },
      { level: null, count: 9 },
    ],
    top_requirements: [
      { name: 'DNI', source: 'RENAPER', count: 9 },
      { name: 'Formulario de solicitud', source: null, count: 5 },
    ],
    ...overrides,
  }
}

export function makeOpportunities(overrides: Partial<Opportunities> = {}): Opportunities {
  return {
    sources: [
      { source: RENTAS_SOURCE, requirements: 2, procedures: 6, annual_volume: 3190 },
      { source: RENAPER, requirements: 1, procedures: 9, annual_volume: 7460 },
    ],
    without_source: { requirements: 3, procedures: 7, annual_volume: 2620 },
    ...overrides,
  }
}
