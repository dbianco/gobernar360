import { GeoMap } from './GeoMap'
import { boundsOfZones } from './geometry'
import { type DrawnZone, ZonesLayer } from './layers'

/** Zones alone; with `onSelect`, clicking one chooses it. */
export default function ZonesMap(props: {
  label: string
  zones: DrawnZone[]
  onSelect?: (id: string) => void
}) {
  return (
    <GeoMap label={props.label} bounds={boundsOfZones(props.zones)}>
      <ZonesLayer zones={props.zones} onSelect={props.onSelect} />
    </GeoMap>
  )
}
