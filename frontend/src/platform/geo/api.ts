import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, downloadUrl, type Query } from '../../api/client'
import type { Page } from '../types'
import type {
  Breakdown,
  ChosenBackground,
  Features,
  LocatedKind,
  LocationGeometry,
  Overlap,
  PolygonGeometry,
  RecordLocation,
  RecordRef,
  ReferenceFeatures,
  ReferenceLayerInfo,
  ReferenceLayerKey,
  Boundary,
  Zone,
  ZoneImport,
  ZoneProfile,
  ZoneSaved,
  ZoneVersion,
} from './types'

const base = (kind: LocatedKind) => `/dashboards/${kind.dashboard}/geo/${kind.record}`
// Under the dashboard's own key, so its changes refresh its maps too.
const keyOf = (kind: LocatedKind, ...rest: unknown[]) => [
  kind.dashboard,
  'geo',
  kind.record,
  ...rest,
]

/** The background the municipality chose in Configuración. */
export function useMapBackground(enabled = true) {
  return useQuery({
    queryKey: ['map-background'],
    queryFn: () => api<ChosenBackground>('/map-background'),
    // Changes only when somebody saves it: the maps of a screen need not each ask.
    staleTime: Infinity,
    enabled,
  })
}

/** The layers of public facilities that have something to show. */
export function useReferenceLayers(enabled = true) {
  return useQuery({
    queryKey: ['reference-layers'],
    queryFn: () => api<ReferenceLayerInfo[]>('/geo/reference-layers'),
    // They change only when somebody imports them.
    staleTime: Infinity,
    enabled,
  })
}

export function useReferenceFeatures(layer: ReferenceLayerKey, bbox: string) {
  return useQuery({
    queryKey: ['reference-layers', layer, bbox],
    queryFn: ({ signal }) =>
      api<ReferenceFeatures>(`/geo/reference-layers/${layer}`, { query: { bbox }, signal }),
    staleTime: Infinity,
    // What was on the map stays while the next area loads.
    placeholderData: keepPreviousData,
  })
}

/** The zones in use; with a day, those in use then, with the boundaries they had. */
export function useZones(asOf?: string, enabled = true) {
  return useQuery({
    queryKey: ['zones', 'list', asOf ?? null],
    queryFn: () => api<Zone[]>('/zones', { query: { as_of: asOf } }),
    enabled,
  })
}

export function useOverlaps() {
  return useQuery({
    queryKey: ['zones', 'overlaps'],
    queryFn: () => api<Overlap[]>('/admin/zones/overlaps'),
  })
}

export function useZoneVersions(zoneId: string) {
  return useQuery({
    queryKey: ['zones', 'versions', zoneId],
    queryFn: () => api<ZoneVersion[]>(`/admin/zones/${zoneId}/versions`),
  })
}

export function useZoneProfile(zoneId: string | null) {
  return useQuery({
    queryKey: ['overview', 'zones', zoneId],
    queryFn: () => api<ZoneProfile>(`/overview/zones/${zoneId}`),
    enabled: zoneId !== null,
  })
}

/** The visible part of a map. */
export interface View {
  bbox: string
  zoom: number
}

export function useFeatures(kind: LocatedKind, view: View | null, filters: Query) {
  return useQuery({
    queryKey: keyOf(kind, 'features', view, filters),
    queryFn: ({ signal }) => api<Features>(`${base(kind)}/features`, { query: { ...filters, ...view }, signal }),
    enabled: view !== null,
    // What was on the map stays while the next area loads.
    placeholderData: keepPreviousData,
  })
}

export function useBreakdown(kind: LocatedKind, filters: Query, asOf?: string) {
  return useQuery({
    queryKey: keyOf(kind, 'zones', filters, asOf ?? null),
    queryFn: () =>
      api<Breakdown>(`${base(kind)}/zones`, { query: { ...filters, as_of: asOf } }),
    placeholderData: keepPreviousData,
  })
}

export const breakdownCsv = (kind: LocatedKind, filters: Query, asOf?: string) =>
  downloadUrl(`${base(kind)}/zones.csv`, { ...filters, as_of: asOf })

export type UnzonedReason = 'outside' | 'unlocated'

export function useUnzoned(
  kind: LocatedKind,
  query: { reason: UnzonedReason; q: string; limit: number; offset: number },
) {
  return useQuery({
    queryKey: keyOf(kind, 'unzoned', query),
    queryFn: () => api<Page<RecordRef>>(`${base(kind)}/unzoned`, { query }),
    placeholderData: keepPreviousData,
  })
}

export function useLocationOf(kind: LocatedKind, recordId: string) {
  return useQuery({
    queryKey: keyOf(kind, 'location', recordId),
    queryFn: () => api<RecordLocation>(`${base(kind)}/${recordId}/location`),
  })
}

export const saveLocation = (
  kind: LocatedKind,
  recordId: string,
  location: LocationGeometry | null,
) => api<RecordLocation>(`${base(kind)}/${recordId}/location`, { method: 'PUT', body: { location } })

export const createZone = (name: string, boundary: PolygonGeometry) =>
  api<ZoneSaved>('/admin/zones', { method: 'POST', body: { name, boundary } })

export const updateZone = (
  zoneId: string,
  changes: { name?: string; boundary?: PolygonGeometry | Boundary; base_version: number },
) => api<ZoneSaved>(`/admin/zones/${zoneId}`, { method: 'PATCH', body: changes })

export const retireZone = (zoneId: string) => api(`/admin/zones/${zoneId}`, { method: 'DELETE' })

export const importZones = (geojson: unknown) =>
  api<ZoneImport>('/admin/zones/import', { method: 'POST', body: { geojson } })

/** A zone may hold records of any dashboard, so a change to one refreshes everything. */
export function useRefreshEverything() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries()
}
