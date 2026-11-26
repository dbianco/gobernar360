import 'leaflet/dist/leaflet.css'

import { Stack, Switch, Text } from '@mantine/core'
import L from 'leaflet'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Bounds } from './geometry'
import classes from './GeoMap.module.css'
import { useMapBackground, useReferenceLayers, type View } from './api'
import { toLatLngBounds } from './latLng'
import { ViewWatcher } from './layers'
import { MapContext } from './mapContext'
import { ReferenceLayer } from './ReferenceLayer'
import type { ChosenBackground, ReferenceLayerInfo } from './types'

const MAX_ZOOM = 19
/** Covers one town: further out, and around it, there are no images and nothing is wrong. */
const SATELLITE = 'satellite'
const NO_BACKGROUND = { background: null, api_key: null }
// All of Argentina, for a municipality that has drawn nothing yet.
const WHOLE_COUNTRY: Bounds = [-73.6, -55.1, -53.6, -21.8]
// A single point has no extent to fit: close enough to see its block.
const CLOSEST_FIT = 16

/** The images behind the map: the municipality's choice, or the one being tried. */
function BackgroundLayer(props: {
  map: L.Map
  preview?: ChosenBackground
  onLoaded: (loaded: boolean) => void
}) {
  const { map, preview, onLoaded } = props
  const chosen = useMapBackground(preview === undefined)
  const { background, api_key: apiKey } = preview ?? chosen.data ?? NO_BACKGROUND
  const failed = !preview && chosen.isError

  useEffect(() => {
    if (failed) onLoaded(false)
    if (!background) return
    const layer = L.tileLayer(background.url, {
      maxZoom: MAX_ZOOM,
      // Further in than its images go, they are enlarged.
      maxNativeZoom: Math.min(background.max_zoom, MAX_ZOOM),
      tileSize: background.tile_size,
      zoomOffset: background.zoom_offset,
      attribution: background.attribution,
      apiKey: encodeURIComponent(apiKey ?? ''),
    } as L.TileLayerOptions)
      .on('tileerror', () => onLoaded(false))
      .on('tileload', () => onLoaded(true))
      .addTo(map)
    return () => {
      layer.remove()
      onLoaded(true)
    }
  }, [map, background, apiKey, failed, onLoaded])

  return null
}

/** The public facilities in the visible area, for those who ask to see them. */
function Facilities({ map, layers }: { map: L.Map; layers: ReferenceLayerInfo[] }) {
  const { t } = useTranslation()
  const [view, setView] = useState<View | null>(null)
  const credit = t('geo.reference.credit')

  useEffect(() => {
    map.attributionControl.addAttribution(credit)
    return () => {
      map.attributionControl.removeAttribution(credit)
    }
  }, [map, credit])

  return (
    <>
      <ViewWatcher onChange={setView} />
      {view &&
        layers.map(({ layer }) => <ReferenceLayer key={layer} layer={layer} bbox={view.bbox} />)}
    </>
  )
}

/**
 * A map people can move and zoom; its layers are its children. Without the background
 * (offline, or its server down) everything else is still drawn.
 */
export function GeoMap(props: {
  /** Says what the map shows to those who cannot see it. */
  label: string
  /** What to show at first; null for the whole country. Later changes do not move the map. */
  bounds: Bounds | null
  height?: number
  /** Whether a click marks a place rather than moving the map. */
  drawing?: boolean
  /** Tries a background instead of the municipality's own. */
  background?: ChosenBackground
  /** Shown over a corner of the map. */
  card?: ReactNode
  children?: ReactNode
}) {
  const { t } = useTranslation()
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<L.Map | null>(null)
  const [loaded, setLoaded] = useState(true)
  const [facilities, setFacilities] = useState(false)
  // Whoever only tries a background may not be a member, as the platform operator.
  const trying = props.background !== undefined
  const imported = useReferenceLayers(!trying).data
  const layers = trying || imported === undefined ? [] : imported
  const chosen = useMapBackground(!trying).data
  const background = (props.background ?? chosen)?.background
  // Read once, when the map is created.
  const start = useRef({ bounds: props.bounds ?? WHOLE_COUNTRY, drawing: props.drawing, t })

  useEffect(() => {
    const element = container.current
    if (!element) return
    const { bounds, drawing, t: text } = start.current
    const created = L.map(element, {
      zoomControl: false,
      maxZoom: MAX_ZOOM,
      worldCopyJump: true,
      // While drawing, two quick clicks are two places.
      doubleClickZoom: !drawing,
      // Fading leaves the labels of a redrawn zone on screen along with the new ones.
      fadeAnimation: false,
    })
    L.control
      .zoom({ zoomInTitle: text('geo.map.zoomIn'), zoomOutTitle: text('geo.map.zoomOut') })
      .addTo(created)
    created.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>')
    L.control.scale({ imperial: false }).addTo(created)
    created.fitBounds(toLatLngBounds(bounds), { maxZoom: CLOSEST_FIT, padding: [20, 20] })
    // The map measures itself only when told to.
    // While hidden (in a tab left for another) it has no size, and would lose its place.
    const observer = new ResizeObserver(() => {
      if (element.clientWidth > 0) created.invalidateSize()
    })
    observer.observe(element)
    setMap(created)
    return () => {
      observer.disconnect()
      created.remove()
      setMap(null)
    }
  }, [])

  return (
    <Stack gap={4}>
      {map && <BackgroundLayer map={map} preview={props.background} onLoaded={setLoaded} />}
      <div
        className={props.drawing ? `${classes.frame} ${classes.drawing}` : classes.frame}
        style={{ height: props.height ?? 420 }}
      >
        <div ref={container} className={classes.map} role="region" aria-label={props.label} />
        {props.card && <div className={classes.card}>{props.card}</div>}
        {map && (
          <MapContext.Provider value={map}>
            {props.children}
            {facilities && <Facilities map={map} layers={layers} />}
          </MapContext.Provider>
        )}
      </div>
      {!loaded && (
        <Text size="xs" c="dimmed" role="status">
          {t(background?.key === SATELLITE ? 'geo.map.noSatellite' : 'geo.map.noBackground')}
        </Text>
      )}
      {layers.length > 0 && (
        <Switch
          size="xs"
          label={t('geo.reference.show')}
          description={t('geo.reference.hint')}
          checked={facilities}
          onChange={(event) => setFacilities(event.currentTarget.checked)}
        />
      )}
    </Stack>
  )
}
