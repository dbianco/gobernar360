import { expect, it } from 'vitest'

import {
  boundsOf,
  boundsOfZones,
  editableCorners,
  formatPosition,
  formatPositions,
  parsePosition,
  parsePositions,
  polygonOf,
  positionsOf,
} from './geometry'
import type { Boundary, Position } from './types'

it.each([
  ['-32.3655, -62.3105', [-62.3105, -32.3655]],
  ['-32.3655,-62.3105', [-62.3105, -32.3655]],
  ['  -32.3655   -62.3105 ', [-62.3105, -32.3655]],
  ['-32.3655;-62.3105', [-62.3105, -32.3655]],
  // With the comma as decimal mark.
  ['-32,3655; -62,3105', [-62.3105, -32.3655]],
  ['-32,3655 -62,3105', [-62.3105, -32.3655]],
  ['-32,3655, -62,3105', [-62.3105, -32.3655]],
  ['(-32.3655, -62.3105)', [-62.3105, -32.3655]],
  ['-32, -62', [-62, -32]],
  ['90 180', [180, 90]],
  ['-90 -180', [-180, -90]],
])('reads "%s" as latitude and longitude', (text, position) => {
  expect(parsePosition(text)).toEqual(position)
})

it.each(['', '-32.3655', 'San Martín 245', '-32.3 -62.3 5', '90.1, 0', '0, 180.1', '-32.3, x'])(
  'does not take "%s" for coordinates',
  (text) => {
    expect(parsePosition(text)).toBeNull()
  },
)

it('reads one position per line, and none if any is wrong', () => {
  expect(parsePositions('1, 2\n\n 3, 4 \n')).toEqual([
    [2, 1],
    [4, 3],
  ])
  expect(parsePositions('1, 2\nx')).toBeNull()
  expect(parsePositions('')).toEqual([])
})

it('writes positions so that they can be read back', () => {
  expect(formatPosition([-62.31, -32.3655004])).toBe('-32.365500, -62.310000')
  const positions: Position[] = [
    [-62.31, -32.36],
    [-62.3, -32.35],
  ]
  expect(parsePositions(formatPositions(positions))).toEqual(positions)
})

it('lists the positions of a location', () => {
  expect(positionsOf(null)).toEqual([])
  expect(positionsOf({ type: 'Point', coordinates: [1, 2] })).toEqual([[1, 2]])
  expect(positionsOf({ type: 'LineString', coordinates: [[1, 2], [3, 4]] })).toEqual([
    [1, 2],
    [3, 4],
  ])
})

const SQUARE: Position[] = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
]

it('finds what surrounds everything', () => {
  expect(boundsOf([])).toBeNull()
  expect(boundsOf([[3, 1], [-2, 5], [0, 0]])).toEqual([-2, 0, 3, 5])
  const far = SQUARE.map(([x, y]): Position => [x + 5, y + 5])
  const boundary = (ring: Position[]): Boundary => ({ type: 'MultiPolygon', coordinates: [[ring]] })
  expect(boundsOfZones([{ boundary: boundary(SQUARE) }, { boundary: boundary(far) }])).toEqual([
    0, 0, 6, 6,
  ])
  expect(boundsOfZones([])).toBeNull()
})

it('edits by hand only boundaries of one piece', () => {
  const parts = (...coordinates: Position[][][]): Boundary => ({ type: 'MultiPolygon', coordinates })

  expect(editableCorners(parts([SQUARE]))).toEqual(SQUARE.slice(0, -1))
  expect(editableCorners(parts([SQUARE], [SQUARE]))).toBeNull()
  // A hole.
  expect(editableCorners(parts([SQUARE, SQUARE]))).toBeNull()
})

it('closes the polygon it draws', () => {
  expect(polygonOf(SQUARE.slice(0, -1))).toEqual({ type: 'Polygon', coordinates: [SQUARE] })
})
