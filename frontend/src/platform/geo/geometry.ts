import type { Boundary, LocationGeometry, PolygonGeometry, Position } from './types'

const NUMBER = String.raw`[-+]?\d+(?:[.,]\d+)?`
// The comma may separate the two numbers or be the decimal mark, as people write it here.
const PAIR = new RegExp(String.raw`^\(?\s*(${NUMBER})\s*[,;\s]\s*(${NUMBER})\s*\)?$`)

/** "latitude, longitude", as maps on the web show it, to a GeoJSON position. */
export function parsePosition(text: string): Position | null {
  const match = PAIR.exec(text.trim())
  if (!match) return null
  const [latitude, longitude] = match.slice(1).map((number) => Number(number.replace(',', '.')))
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null
  return [longitude, latitude]
}

/** One position per line; null if any line is not one. Empty lines are skipped. */
export function parsePositions(text: string): Position[] | null {
  const positions = text
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map(parsePosition)
  return positions.includes(null) ? null : (positions as Position[])
}

/** Six decimals are about ten centimetres. */
export const formatPosition = ([longitude, latitude]: Position) =>
  `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`

export const formatPositions = (positions: Position[]) => positions.map(formatPosition).join('\n')

export const positionsOf = (location: LocationGeometry | null): Position[] => {
  if (!location) return []
  return location.type === 'Point' ? [location.coordinates] : location.coordinates
}

/** West, south, east and north of everything given; null when there is nothing. */
export type Bounds = [number, number, number, number]

export function boundsOf(positions: Position[]): Bounds | null {
  if (positions.length === 0) return null
  const longitudes = positions.map(([longitude]) => longitude)
  const latitudes = positions.map(([, latitude]) => latitude)
  return [
    Math.min(...longitudes),
    Math.min(...latitudes),
    Math.max(...longitudes),
    Math.max(...latitudes),
  ]
}

export const boundsOfZones = (zones: { boundary: Boundary }[]) =>
  boundsOf(zones.flatMap((zone) => zone.boundary.coordinates.flat(2)))

/** The corners of a boundary that can be edited by hand; null when it has parts or holes. */
export function editableCorners(boundary: Boundary): Position[] | null {
  const [polygon, ...otherParts] = boundary.coordinates
  if (otherParts.length > 0 || polygon.length !== 1) return null
  // The last corner repeats the first.
  return polygon[0].slice(0, -1)
}

/** A closed polygon through the corners. */
export const polygonOf = (corners: Position[]): PolygonGeometry => ({
  type: 'Polygon',
  coordinates: [[...corners, corners[0]]],
})
