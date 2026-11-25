import L from 'leaflet'

import type { Bounds } from './geometry'
import type { Position } from './types'

// GeoJSON puts the longitude first and Leaflet the latitude: converted only here.

export const toLatLng = ([longitude, latitude]: Position) => L.latLng(latitude, longitude)

export const toLatLngBounds = ([west, south, east, north]: Bounds) =>
  L.latLngBounds([south, west], [north, east])

/** Six decimals, about ten centimetres: a click is not more exact than that. */
export const rounded = (value: number) => Number(value.toFixed(6))

export const toPosition = (point: L.LatLng): Position => {
  const wrapped = point.wrap()
  return [rounded(wrapped.lng), rounded(wrapped.lat)]
}
