import { useMemo } from 'react'

import { GeoMap } from './GeoMap'
import { boundsOfZones } from './geometry'
import { ZonesLayer } from './layers'
import type { ChosenBackground, Zone } from './types'

/** How the maps would look with a background, over the municipality's own zones. */
export default function BackgroundPreview(props: {
  label: string
  background: ChosenBackground
  zones: Zone[]
}) {
  const { zones } = props
  const drawn = useMemo(
    () => zones.map(({ id, name, boundary }) => ({ id, boundary, label: name })),
    [zones],
  )
  return (
    <GeoMap
      label={props.label}
      bounds={boundsOfZones(zones)}
      height={280}
      background={props.background}
    >
      <ZonesLayer zones={drawn} />
    </GeoMap>
  )
}
