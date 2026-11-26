import { screen } from '@testing-library/react'
import L from 'leaflet'

import { t } from '../../test/render'
import type { Boundary, Breakdown, LocatedKind, Position, Zone } from './types'

export const SHOPS: LocatedKind = {
  dashboard: 'economic',
  record: 'actors',
  individualLevel: 'viewer',
  path: (id) => `/d/economic/actors/${id}`,
}
export const SHOPS_API = '/dashboards/economic/geo/actors'
export const WORKS: LocatedKind = {
  dashboard: 'projects',
  record: 'projects',
  individualLevel: 'viewer',
  path: (id) => `/d/projects/projects/${id}`,
}
export const WORKS_API = '/dashboards/projects/geo/projects'
export const HOMES: LocatedKind = {
  dashboard: 'social',
  record: 'households',
  individualLevel: 'editor',
  path: (id) => `/d/social/households/${id}`,
}

export const square = (x: number, y: number, size = 1): Position[] => [
  [x, y],
  [x + size, y],
  [x + size, y + size],
  [x, y + size],
  [x, y],
]

export const boundary = (...rings: Position[][]): Boundary => ({
  type: 'MultiPolygon',
  coordinates: [rings],
})

export function makeZone(overrides: Partial<Zone> = {}): Zone {
  return {
    id: 'z-1',
    name: 'Centro',
    version: 1,
    // Noon, so that it is the same day in every time zone tests may run in.
    valid_from: '2025-03-10T12:00:00Z',
    source: '',
    boundary: boundary(square(-62, -32)),
    ...overrides,
  }
}
export const CENTRO = makeZone()
export const NORTE = makeZone({ id: 'z-2', name: 'Norte', boundary: boundary(square(-62, -31)) })

const figures = (actors: number | null, groups: Breakdown['total']['groups'] = []) => ({
  values: { actors },
  groups,
  suppressed: actors === null,
})

export function makeBreakdown(overrides: Partial<Breakdown> = {}): Breakdown {
  return {
    boundaries_as_of: null,
    metrics: [{ key: 'actors', unit: null }],
    grouping: 'sector',
    zones: [
      {
        zone: { id: CENTRO.id, name: CENTRO.name },
        ...figures(3, [
          { name: 'Alimentos', count: 2 },
          { name: null, count: 1 },
        ]),
      },
      { zone: { id: NORTE.id, name: NORTE.name }, ...figures(0) },
    ],
    outside: figures(1),
    unlocated: figures(2),
    total: figures(6),
    threshold: null,
    ...overrides,
  }
}

/** The frame Leaflet draws in. */
export const mapFrame = (label: string) => screen.findByRole('region', { name: label })

/** What a mark says; they are buttons when they do something. */
export const mark = (name: string) => screen.findByRole('button', { name })

/** Makes Leaflet take a mark as dragged there, which jsdom cannot do. */
export function drag(element: HTMLElement, to: Position) {
  const marker = markers.find((candidate) => candidate.getElement() === element)
  if (!marker) throw new Error('Not a marker.')
  marker.setLatLng(L.latLng(to[1], to[0]))
  marker.fire('dragend')
}

const markers: L.Marker[] = []
L.Marker.addInitHook(function remember(this: L.Marker) {
  markers.push(this)
})

export const shownInView = (count: number) => t('geo.map.inView', { count })
