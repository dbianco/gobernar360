import { STANDARD_MAP } from '../../test/server'
import type { MapBackground } from '../geo/types'

const background = (overrides: Partial<MapBackground>): MapBackground => ({
  ...STANDARD_MAP.background,
  ...overrides,
})
const tiles = (name: string, query = '') => `https://${name}.test/{z}/{x}/{y}.png${query}`
const keyed = '?key={apiKey}'

/** The backgrounds the API offers, with addresses of their own. */
export const BACKGROUNDS: MapBackground[] = [
  STANDARD_MAP.background,
  ...['humanitarian', 'cyclosm', 'germany', 'france', 'topographic', 'public_transport'].map((key) =>
    background({ key, url: tiles(key.replace('_', '-')) }),
  ),
  background({ key: 'cycle', url: tiles('cycle', keyed), provider: 'Thunderforest' }),
  background({ key: 'transport', url: tiles('transport', keyed), provider: 'Thunderforest' }),
  background({ key: 'tracestrack', url: tiles('tracestrack', keyed), provider: 'Tracestrack' }),
  background({
    key: 'maptiler',
    url: tiles('maptiler', keyed),
    provider: 'MapTiler',
    tile_size: 512,
    zoom_offset: -1,
  }),
]

/** Offered only where the operator said which layer is the municipality's. */
export const SATELLITE = background({
  key: 'satellite',
  url: tiles('satellite'),
  attribution: 'Imagen: CONAE – Pleiades Neo 2023',
})

export const MAP_SETTINGS = {
  small_zone_threshold: 5,
  map_background: 'standard',
  map_api_key: null,
  map_backgrounds: BACKGROUNDS,
  idecor_key: null,
  conae_layer: null,
}
