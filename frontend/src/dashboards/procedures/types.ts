export const SOURCE_LEVELS = ['municipal', 'provincial', 'national', 'other'] as const
export const AUDIENCES = ['both', 'people', 'organizations'] as const
export const CHANNELS = ['in_person', 'online', 'both'] as const
export const FORMATS = ['paper', 'digital'] as const
export type SourceLevel = (typeof SOURCE_LEVELS)[number]
/** Levels of the provincial account, CiDi. */
export const CIDI_LEVELS = [1, 2, 3] as const
export type CidiLevel = (typeof CIDI_LEVELS)[number]
export type Channel = (typeof CHANNELS)[number]

export interface Named {
  id: string
  name: string
}

/** Who holds a piece of data or issues a document. */
export interface Source extends Named {
  level: SourceLevel
  area: Named | null
}

export interface RequirementRef extends Named {
  /** Null when the person brings it themselves. */
  source: Source | null
}

export interface Requirement extends RequirementRef {
  description: string
  procedure_count: number
}

export interface Procedure extends Named {
  description: string
  area: Named
  audience: string
  channel: Channel
  url: string
  /** The least level people sign in with; null when they do not, or it is not known. */
  cidi_level: CidiLevel | null
  /** Whether it can be done entirely from home. Worked out by the API. */
  fully_digital: boolean
  is_free: boolean
  /** A decimal as text, e.g. "1500.00". */
  cost: string | null
  duration_days: number | null
  annual_volume: number | null
  is_active: boolean
  requirement_count: number
}

/** A requirement asked for by one procedure. */
export interface RequirementLink {
  id: string
  requirement: RequirementRef
  mandatory: boolean
  format: string
  note: string
}

export interface ProcedureDetail extends Procedure {
  requirements: RequirementLink[]
}

export interface Page<T> {
  items: T[]
  total: number
}

export interface Summary {
  procedures: number
  online: number
  cidi: number
  /** Of the online ones; null when there are none. */
  cidi_ratio: number | null
  digital: number
  /** Of them all; null when there are none. */
  digital_ratio: number | null
  average_requirements: number | null
  requirements: number
  sources: number
  by_area: { name: string; count: number }[]
  by_channel: { channel: Channel; count: number }[]
  by_cidi_level: { level: CidiLevel | null; count: number }[]
  top_requirements: { name: string; source: string | null; count: number }[]
}

export interface Reach {
  requirements: number
  procedures: number
  annual_volume: number
}

export interface Opportunities {
  sources: (Reach & { source: Source })[]
  without_source: Reach
}
