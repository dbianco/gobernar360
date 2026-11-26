import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { useReferenceFeatures } from './api'
import classes from './GeoMap.module.css'
import { toLatLng } from './latLng'
import { useLeafletMap } from './mapContext'
import type { ReferenceFeature, ReferenceLayerKey } from './types'

/** What a popup says of a facility, in order; those the source does not give are left out. */
const PROPERTIES = ['type', 'level', 'sector', 'address'] as const
const SIZE = 24

/** Facilities at the same place share a mark: two schools may use one building. */
function byPlace(features: ReferenceFeature[]): ReferenceFeature[][] {
  const places = new Map<string, ReferenceFeature[]>()
  for (const feature of features) {
    const key = feature.geometry.coordinates.join(',')
    places.set(key, [...(places.get(key) ?? []), feature])
  }
  return [...places.values()]
}

/** Leaflet takes strings for HTML, and these come from somebody else's service. */
function line(tag: string, text: string): HTMLElement {
  const element = document.createElement(tag)
  element.textContent = text
  return element
}

/** Public facilities of one layer, inside the visible area; each says what it is when pressed. */
export function ReferenceLayer({ layer, bbox }: { layer: ReferenceLayerKey; bbox: string }) {
  const { t } = useTranslation()
  const map = useLeafletMap()
  const { data } = useReferenceFeatures(layer, bbox)
  const places = useMemo(() => byPlace(data?.features ?? []), [data])

  useEffect(() => {
    const group = L.featureGroup()
    for (const here of places) {
      const popup = document.createElement('div')
      for (const feature of here) {
        popup.append(line('strong', feature.name))
        for (const key of PROPERTIES) {
          const value = feature.properties[key]
          if (value) popup.append(line('div', t(`geo.reference.properties.${key}`, { value })))
        }
      }
      popup.append(line('small', t('geo.reference.source')))
      const name = t(`geo.reference.layers.${layer}`, {
        name: here.map((feature) => feature.name).join(', '),
      })
      const marker = L.marker(toLatLng(here[0].geometry.coordinates), {
        icon: L.divIcon({
          className: `${classes.reference} ${classes[layer]}`,
          html: line('span', t(`geo.reference.marks.${layer}`)),
          iconSize: [SIZE, SIZE],
        }),
        title: name,
        // Under the records, which are what the map is about.
        zIndexOffset: -1000,
      })
      marker.bindPopup(popup, { className: classes.popup, closeButton: false })
      marker.on('add', () => {
        const element = marker.getElement()
        element?.setAttribute('aria-label', name)
        element?.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return
          event.preventDefault()
          marker.openPopup()
        })
      })
      group.addLayer(marker)
    }
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, places, layer, t])

  return null
}
