export const SOURCE_LEVELS = ['municipal', 'provincial', 'national', 'other'] as const
export const AUDIENCES = ['both', 'people', 'organizations'] as const
export const CHANNELS = ['in_person', 'online', 'both'] as const
export const FORMATS = ['paper', 'digital'] as const
export type SourceLevel = (typeof SOURCE_LEVELS)[number]
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
  average_requirements: number | null
  requirements: number
  sources: number
  by_area: { name: string; count: number }[]
  by_channel: { channel: Channel; count: number }[]
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
