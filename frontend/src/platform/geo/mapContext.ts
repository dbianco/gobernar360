import type { Map as LeafletMap } from 'leaflet'
import { createContext, useContext } from 'react'

/** The Leaflet map the layers inside <GeoMap> draw on. */
export const MapContext = createContext<LeafletMap | null>(null)

export function useLeafletMap(): LeafletMap {
  const map = useContext(MapContext)
  if (!map) throw new Error('Map layers must be inside <GeoMap>.')
  return map
}
