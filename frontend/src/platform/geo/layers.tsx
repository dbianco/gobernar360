import L from 'leaflet'
import { useEffect, useLayoutEffect, useRef } from 'react'

import type { View } from './api'
import classes from './GeoMap.module.css'
import type { Bounds } from './geometry'
import { rounded, toLatLng, toLatLngBounds, toPosition } from './latLng'
import { useLeafletMap } from './mapContext'
import type { Boundary, LocationGeometry, Position } from './types'

/** Leaflet would take a string for HTML, and names are typed by people. */
function textElement(text: string): HTMLElement {
  const element = document.createElement('div')
  element.textContent = text
  return element
}

/** The latest value of a callback, so that layers are not redrawn when it changes. */
function useLatest<T>(value: T) {
  const latest = useRef(value)
  useEffect(() => {
    latest.current = value
  })
  return latest
}

export interface DrawnZone {
  id: string
  boundary: Boundary
  /** Written on the zone. */
  label?: string
  /** Null: only its border is drawn. */
  fill?: string | null
  dashed?: boolean
  selected?: boolean
}

const LABELS_PANE = 'zoneLabels'

/** Zones, each with its label, and shaded when they have a fill. */
export function ZonesLayer(props: { zones: DrawnZone[]; onSelect?: (id: string) => void }) {
  const map = useLeafletMap()
  const onSelect = useLatest(props.onSelect)
  const selectable = props.onSelect !== undefined
  const zones = props.zones

  useEffect(() => {
    // Over the zones and under the marks, which must stay readable and clickable.
    const labels = map.getPane(LABELS_PANE) ?? map.createPane(LABELS_PANE)
    labels.style.zIndex = '590'
    labels.style.pointerEvents = 'none'
    const group = L.featureGroup()
    for (const zone of zones) {
      const layer = L.geoJSON(zone.boundary, {
        interactive: selectable,
        style: {
          color: zone.selected ? '#c2255c' : '#343a40',
          weight: zone.selected ? 4 : 1.5,
          dashArray: zone.dashed ? '6 5' : undefined,
          fill: selectable || Boolean(zone.fill),
          fillColor: zone.fill ?? '#868e96',
          fillOpacity: zone.fill ? 0.7 : 0,
        },
      })
      if (zone.label) {
        layer.bindTooltip(textElement(zone.label), {
          pane: LABELS_PANE,
          permanent: true,
          direction: 'center',
          className: classes.zoneLabel,
        })
      }
      layer.on('click', () => onSelect.current?.(zone.id))
      group.addLayer(layer)
    }
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, zones, selectable, onSelect])

  return null
}

export interface DrawnMarker {
  key: string
  position: Position
  /** Its accessible name, also shown on hover. */
  name: string
  kind: 'pin' | 'cluster' | 'corner' | 'middle'
  text?: string
  onClick?: () => void
  onDrag?: (position: Position) => void
}

const SIZES = { pin: 20, cluster: 36, corner: 18, middle: 14 }

/** Round marks that work with the mouse and, when they do something, with the keyboard. */
export function MarkersLayer({ markers }: { markers: DrawnMarker[] }) {
  const map = useLeafletMap()

  // Along with the rest of the screen: a mark of a moment ago would act on what it was.
  useLayoutEffect(() => {
    const group = L.featureGroup()
    for (const mark of markers) {
      const size = SIZES[mark.kind]
      const active = mark.onClick !== undefined || mark.onDrag !== undefined
      const marker = L.marker(toLatLng(mark.position), {
        icon: L.divIcon({
          className: classes[mark.kind],
          html: textElement(mark.text ?? ''),
          iconSize: [size, size],
        }),
        title: mark.name,
        keyboard: active,
        interactive: active,
        draggable: mark.onDrag !== undefined,
        // Corners over the middles of the sides, and both over everything else.
        zIndexOffset: mark.kind === 'corner' ? 2000 : mark.kind === 'middle' ? 1000 : 0,
      })
      marker.on('add', () => {
        const element = marker.getElement()
        element?.setAttribute('aria-label', mark.name)
        // Leaflet makes marks focusable buttons, but nothing happens when they are pressed.
        element?.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return
          event.preventDefault()
          mark.onClick?.()
        })
      })
      if (mark.onClick) marker.on('click', mark.onClick)
      if (mark.onDrag) marker.on('dragend', () => mark.onDrag?.(toPosition(marker.getLatLng())))
      group.addLayer(marker)
    }
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, markers])

  return null
}

export interface DrawnLine {
  key: string
  geometry: LocationGeometry
  onClick?: () => void
}

/** The lines among the geometries; points are markers. */
export function LinesLayer({ lines }: { lines: DrawnLine[] }) {
  const map = useLeafletMap()

  useEffect(() => {
    const group = L.featureGroup()
    for (const line of lines) {
      if (line.geometry.type !== 'LineString') continue
      const layer = L.polyline(line.geometry.coordinates.map(toLatLng), {
        color: '#c2255c',
        weight: 5,
        opacity: 0.85,
        interactive: line.onClick !== undefined,
      })
      if (line.onClick) layer.on('click', line.onClick)
      group.addLayer(layer)
    }
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, lines])

  return null
}

/** What is being drawn: a line, or an outline that closes from three corners on. */
export function OutlineLayer({ corners, open = false }: { corners: Position[]; open?: boolean }) {
  const map = useLeafletMap()

  useEffect(() => {
    const points = corners.map(toLatLng)
    const style = { color: '#e8590c', weight: 3, fillOpacity: 0.15, interactive: false }
    const closed = !open && points.length > 2
    const layer = closed ? L.polygon(points, style) : L.polyline(points, { ...style, fill: false })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, corners, open])

  return null
}

/** Tells where the map is clicked, outside its marks. */
export function ClickCatcher({ onClick }: { onClick: (position: Position) => void }) {
  const map = useLeafletMap()
  const latest = useLatest(onClick)

  useEffect(() => {
    const handle = (event: L.LeafletMouseEvent) => latest.current(toPosition(event.latlng))
    map.on('click', handle)
    return () => {
      map.off('click', handle)
    }
  }, [map, latest])

  return null
}

/** Keeps the area within the world: the map can be moved past its edges. */
function viewOf(map: L.Map): View {
  const bounds = map.getBounds()
  const limit = (value: number, most: number) => Math.max(-most, Math.min(most, value))
  const bbox = [
    limit(bounds.getWest(), 180),
    limit(bounds.getSouth(), 90),
    limit(bounds.getEast(), 180),
    limit(bounds.getNorth(), 90),
  ]
  return { bbox: bbox.map(rounded).join(','), zoom: map.getZoom() }
}

/** Tells what part of the world is visible, at first and after every move. */
export function ViewWatcher({ onChange }: { onChange: (view: View) => void }) {
  const map = useLeafletMap()
  const latest = useLatest(onChange)

  useEffect(() => {
    const report = () => latest.current(viewOf(map))
    report()
    // Also fired at the end of a zoom, and when the frame changes size.
    map.on('moveend', report)
    return () => {
      map.off('moveend', report)
    }
  }, [map, latest])

  return null
}

/** Moves the map to `bounds` whenever a new one is asked for. */
export function GoTo({ bounds }: { bounds: Bounds | null }) {
  const map = useLeafletMap()

  useEffect(() => {
    if (bounds) map.fitBounds(toLatLngBounds(bounds), { padding: [40, 40], maxZoom: 18 })
  }, [map, bounds])

  return null
}
