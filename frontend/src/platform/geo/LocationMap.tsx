import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { GeoMap } from './GeoMap'
import { boundsOf, boundsOfZones } from './geometry'
import {
  ClickCatcher,
  type DrawnMarker,
  LinesLayer,
  MarkersLayer,
  OutlineLayer,
  ZonesLayer,
} from './layers'
import type { LocationKind, Position, Zone } from './types'

/** One record's place. With `onChange` it is being set: clicking the map marks it. */
export default function LocationMap(props: {
  zones: Zone[]
  kind: LocationKind
  positions: Position[]
  onChange?: (positions: Position[]) => void
}) {
  const { t } = useTranslation()
  const { zones, kind, positions, onChange } = props
  const drawnZones = useMemo(
    () => zones.map(({ id, name, boundary }) => ({ id, boundary, label: name })),
    [zones],
  )
  const markers = useMemo(
    () =>
      // A line that is not being changed needs no marks.
      (kind === 'LineString' && !onChange ? [] : positions).map(
        (position, index): DrawnMarker => ({
          key: String(index),
          position,
          name: t('geo.location.mark', { number: index + 1 }),
          kind: kind === 'Point' ? 'pin' : 'corner',
          onDrag:
            onChange && ((moved) => onChange(positions.map((p, i) => (i === index ? moved : p)))),
        }),
      ),
    [kind, positions, onChange, t],
  )
  const lines = useMemo(
    () =>
      kind === 'LineString' && !onChange
        ? [{ key: 'line', geometry: { type: 'LineString' as const, coordinates: positions } }]
        : [],
    [kind, positions, onChange],
  )

  return (
    <GeoMap
      label={t('geo.location.mapLabel')}
      bounds={boundsOf(positions) ?? boundsOfZones(zones)}
      height={onChange ? 420 : 260}
      drawing={onChange !== undefined}
    >
      <ZonesLayer zones={drawnZones} />
      <LinesLayer lines={lines} />
      {onChange && kind === 'LineString' && <OutlineLayer corners={positions} open />}
      <MarkersLayer markers={markers} />
      {onChange && (
        <ClickCatcher
          onClick={(position) =>
            onChange(kind === 'Point' ? [position] : [...positions, position])
          }
        />
      )}
    </GeoMap>
  )
}
