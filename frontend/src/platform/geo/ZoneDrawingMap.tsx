import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { GeoMap } from './GeoMap'
import { boundsOf, boundsOfZones } from './geometry'
import { ClickCatcher, type DrawnMarker, MarkersLayer, OutlineLayer, ZonesLayer } from './layers'
import type { Position, Zone } from './types'

const middle = ([x1, y1]: Position, [x2, y2]: Position): Position => [(x1 + x2) / 2, (y1 + y2) / 2]

const insert = (corners: Position[], index: number, corner: Position) => [
  ...corners.slice(0, index),
  corner,
  ...corners.slice(index),
]

/**
 * Draws a boundary: clicking the map adds a corner, dragging moves one, clicking a corner
 * removes it, and dragging (or clicking) the middle of a side adds one there.
 */
export default function ZoneDrawingMap(props: {
  /** The other zones, to draw next to them. */
  others: Zone[]
  corners: Position[]
  onChange: (corners: Position[]) => void
}) {
  const { t } = useTranslation()
  const { others, corners, onChange } = props
  const drawnOthers = useMemo(
    () => others.map(({ id, name, boundary }) => ({ id, boundary, label: name })),
    [others],
  )
  const markers = useMemo((): DrawnMarker[] => {
    const closed = corners.length > 2
    const ofCorners = corners.map(
      (position, index): DrawnMarker => ({
        key: `corner ${index}`,
        position,
        name: t('geo.zones.corner', { number: index + 1 }),
        kind: 'corner',
        onClick: () => onChange(corners.filter((_, i) => i !== index)),
        onDrag: (moved) => onChange(corners.map((corner, i) => (i === index ? moved : corner))),
      }),
    )
    const ofSides = !closed
      ? []
      : corners.map((corner, index): DrawnMarker => {
          const position = middle(corner, corners[(index + 1) % corners.length])
          return {
            key: `side ${index}`,
            position,
            name: t('geo.zones.side', { number: index + 1 }),
            kind: 'middle',
            onClick: () => onChange(insert(corners, index + 1, position)),
            onDrag: (moved) => onChange(insert(corners, index + 1, moved)),
          }
        })
    return [...ofSides, ...ofCorners]
  }, [corners, onChange, t])

  return (
    <GeoMap
      label={t('geo.zones.drawingLabel')}
      bounds={boundsOf(corners) ?? boundsOfZones(others)}
      height={520}
      drawing
    >
      <ZonesLayer zones={drawnOthers} />
      <OutlineLayer corners={corners} />
      <MarkersLayer markers={markers} />
      <ClickCatcher onClick={(position) => onChange([...corners, position])} />
    </GeoMap>
  )
}
