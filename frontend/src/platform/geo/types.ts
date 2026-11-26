import type { AccessLevel } from '../types'

/** Longitude and latitude, as GeoJSON orders them. */
export type Position = [number, number]

export interface PointGeometry {
  type: 'Point'
  coordinates: Position
}

export interface LineGeometry {
  type: 'LineString'
  coordinates: Position[]
}

export type LocationGeometry = PointGeometry | LineGeometry
export type LocationKind = LocationGeometry['type']

export interface Boundary {
  type: 'MultiPolygon'
  coordinates: Position[][][]
}

export interface PolygonGeometry {
  type: 'Polygon'
  coordinates: Position[][]
}

export interface ZoneRef {
  id: string
  name: string
}

export interface Zone extends ZoneRef {
  version: number
  valid_from: string
  /** Where an official boundary comes from, e.g. the law that approves it; empty for the rest. */
  source: string
  boundary: Boundary
}

export interface ZoneVersion {
  version: number
  valid_from: string
  valid_to: string | null
  source: string
  boundary: Boundary
}

export interface Overlap {
  zone: ZoneRef
  other: ZoneRef
  area_m2: number
}

export interface ZoneSaved {
  zone: Zone
  overlaps: Overlap[]
}

export interface ZoneImport {
  created: number
  moved: number
  unchanged: number
  overlaps: Overlap[]
}

/** Null: hidden from the member. Amounts come as text, counts as numbers. */
export type FigureValue = number | string | null

export interface Figures {
  values: Record<string, FigureValue>
  groups: { name: string | null; count: number }[]
  suppressed: boolean
}

export interface Metric {
  key: string
  unit: string | null
}

export interface Breakdown {
  boundaries_as_of: string | null
  metrics: Metric[]
  grouping: string | null
  zones: (Figures & { zone: ZoneRef })[]
  outside: Figures
  unlocated: Figures
  total: Figures
  threshold: number | null
}

export interface ProfileSection extends Figures {
  dashboard_key: string
  record_key: string
  metrics: Metric[]
  grouping: string | null
  threshold: number | null
}

export interface ZoneProfile {
  zone: ZoneRef
  sections: ProfileSection[]
}

export interface MapFeature {
  id: string
  title: string
  geometry: LocationGeometry
}

export interface Cluster {
  count: number
  center: Position
  /** West, south, east and north of its records. */
  bounds: [number, number, number, number]
}

export interface Features {
  restricted: boolean
  total: number
  features: MapFeature[]
  clusters: Cluster[]
  truncated: boolean
}

export interface RecordLocation {
  location: LocationGeometry | null
  kinds: LocationKind[]
  zones: ZoneRef[]
}

export interface RecordRef {
  id: string
  title: string
}

/** Where the images behind a map come from. */
export interface MapBackground {
  key: string
  /** Leaflet template; `{apiKey}` is the municipality's key, for those that need one. */
  url: string
  /** HTML, as the licence of the data asks. Comes from the API's own list. */
  attribution: string
  max_zoom: number
  provider: string | null
  tile_size: number
  zoom_offset: number
}

export interface ChosenBackground {
  background: MapBackground
  api_key: string | null
}

export type ReferenceLayerKey = 'health' | 'schools'

/** A layer of public facilities the municipality has imported. */
export interface ReferenceLayerInfo {
  layer: ReferenceLayerKey
  features: number
  imported_at: string
}

/** A public facility, from an official source. */
export interface ReferenceFeature {
  id: string
  name: string
  properties: Partial<Record<'type' | 'level' | 'sector' | 'address', string>>
  geometry: PointGeometry
}

export interface ReferenceFeatures {
  features: ReferenceFeature[]
  truncated: boolean
}

/** A kind of record with a place, as its dashboard declares it in `dashboards/registry.ts`. */
export interface LocatedKind {
  /** Key of the dashboard, and of the record within it, in the API. */
  dashboard: string
  record: string
  /** Least level that sees the records one by one. */
  individualLevel: AccessLevel
  /** Screen of one record. */
  path: (id: string) => string
}
