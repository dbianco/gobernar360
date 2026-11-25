import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError, STANDARD_MAP } from '../../test/server'
import RecordsMap from './RecordsMap'
import { CENTRO, mapFrame, mark, SHOPS, SHOPS_API, shownInView, WORKS, WORKS_API } from './testData'
import type { Features, LocatedKind } from './types'

const LABEL = 'Mapa de actores'

const point = (id: string, title: string, x = -61.5, y = -31.5) => ({
  id,
  title,
  geometry: { type: 'Point' as const, coordinates: [x, y] as [number, number] },
})

const makeFeatures = (overrides: Partial<Features> = {}): Features => ({
  restricted: false,
  total: 0,
  features: [],
  clusters: [],
  truncated: false,
  ...overrides,
})

function renderMap(
  options: { features?: Partial<Features>; filters?: Record<string, string>; kind?: LocatedKind } = {},
) {
  const kind = options.kind ?? SHOPS
  mockApi('get', '/zones', [CENTRO])
  const requests = mockApi(
    'get',
    `${kind === WORKS ? WORKS_API : SHOPS_API}/features`,
    makeFeatures(options.features) as never,
  )
  const map = <RecordsMap kind={kind} label={LABEL} filters={options.filters ?? {}} />
  renderApp(
    <Routes>
      <Route path="/" element={map} />
      <Route path="/d/economic/actors/:id" element={<p>the shop</p>} />
    </Routes>,
    { me: makeMe() },
  )
  return requests
}

it('asks only for what is inside the visible area, with the filters', async () => {
  const requests = renderMap({ filters: { q: 'pan', sector_id: '' }, features: { total: 3 } })

  expect(await screen.findByText(shownInView(3))).toBeInTheDocument()
  const query = requests[0].url.searchParams
  const [west, south, east, north] = query.get('bbox')!.split(',').map(Number)
  // The map opens on the zones, with some room around.
  expect(west).toBeLessThan(-62)
  expect(east).toBeGreaterThan(-61)
  expect(east - west).toBeLessThan(10)
  expect(south).toBeLessThan(-32)
  expect(north).toBeGreaterThan(-31)
  expect(Number(query.get('zoom'))).toBeGreaterThan(4)
  expect([query.get('q'), query.has('sector_id')]).toEqual(['pan', false])
})

it('asks again when the map moves', async () => {
  const requests = renderMap()
  const user = userEvent.setup()
  await screen.findByText(shownInView(0))

  await user.click(screen.getByRole('button', { name: t('geo.map.zoomIn') }))

  await waitFor(() => expect(requests).toHaveLength(2))
  const [before, after] = requests.map((request) => Number(request.url.searchParams.get('zoom')))
  expect(after).toBe(before + 1)
})

it('opens a record from its mark', async () => {
  renderMap({ features: { total: 1, features: [point('a-1', 'Panadería <b>La Espiga</b>')] } })
  const user = userEvent.setup()

  // As typed, never as markup.
  await user.click(await mark('Panadería <b>La Espiga</b>'))
  await user.click(screen.getByRole('link', { name: 'Panadería <b>La Espiga</b>' }))

  expect(await screen.findByText('the shop')).toBeInTheDocument()
})

it('opens a record with the keyboard too, and closes what it selected', async () => {
  renderMap({ features: { total: 1, features: [point('a-1', 'Panadería')] } })
  const user = userEvent.setup()
  const pin = await mark('Panadería')

  pin.focus()
  await user.keyboard('x')
  expect(screen.queryByRole('link', { name: 'Panadería' })).toBeNull()
  await user.keyboard('{Enter}')
  expect(await screen.findByRole('link', { name: 'Panadería' })).toHaveAttribute(
    'href',
    '/d/economic/actors/a-1',
  )

  await user.click(screen.getByRole('button', { name: t('geo.map.closeSelection') }))
  expect(screen.queryByRole('link', { name: 'Panadería' })).toBeNull()
})

it('offers every record of a place that several share', async () => {
  renderMap({ features: { total: 2, features: [point('a-1', 'Local 1'), point('a-2', 'Local 2')] } })
  const user = userEvent.setup()

  const pin = await mark('Local 1, Local 2')
  expect(pin).toHaveTextContent('2')
  await user.click(pin)

  expect(screen.getByRole('link', { name: 'Local 1' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Local 2' })).toBeInTheDocument()
})

it('goes to the records of a cluster', async () => {
  const requests = renderMap({
    features: {
      total: 12,
      clusters: [{ count: 12, center: [-61.5, -31.5], bounds: [-61.51, -31.51, -61.49, -31.49] }],
    },
  })
  const user = userEvent.setup()

  const cluster = await mark(t('geo.map.cluster', { count: 12 }))
  expect(cluster).toHaveTextContent('12')
  await user.click(cluster)

  await waitFor(() => expect(requests.length).toBeGreaterThan(1))
  const query = requests[requests.length - 1].url.searchParams
  const [west, , east] = query.get('bbox')!.split(',').map(Number)
  expect(west).toBeGreaterThan(-61.7)
  expect(east).toBeLessThan(-61.3)
})

it('draws lines, which open their record as well', async () => {
  renderMap({
    kind: WORKS,
    features: {
      total: 1,
      features: [
        {
          id: 'p-1',
          title: 'Pavimento',
          geometry: {
            type: 'LineString',
            coordinates: [
              [-61.8, -31.5],
              [-61.5, -31.5],
              [-61.2, -31.5],
            ],
          },
        },
      ],
    },
  })
  await mark('Pavimento')
  const frame = await mapFrame(LABEL)

  fireEvent.click(frame.querySelector('path.leaflet-interactive')!)

  expect(await screen.findByRole('link', { name: 'Pavimento' })).toHaveAttribute(
    'href',
    '/d/projects/projects/p-1',
  )
})

it('says when there is more than it shows', async () => {
  renderMap({ features: { total: 1500, truncated: true, features: [point('a-1', 'Uno')] } })

  const note = await screen.findByText(new RegExp(shownInView(1500)))
  expect(note).toHaveTextContent(t('geo.map.truncated', { count: 1 }))
})

it('keeps zones and records when the background cannot be loaded', async () => {
  renderMap({ features: { total: 1, features: [point('a-1', 'Panadería')] } })
  await mark('Panadería')
  const frame = await mapFrame(LABEL)
  const tile = frame.querySelector('img.leaflet-tile')!
  expect(tile.getAttribute('src')).toMatch(/^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png/)
  expect(within(frame).getByRole('link', { name: 'OpenStreetMap' })).toBeInTheDocument()

  fireEvent.error(tile)

  expect(await screen.findByText(t('geo.map.noBackground'))).toBeInTheDocument()
  expect(await mark('Panadería')).toBeInTheDocument()
  expect(within(frame).getByText('Centro')).toBeInTheDocument()

  fireEvent.load(frame.querySelectorAll('img.leaflet-tile')[1])
  await waitFor(() => expect(screen.queryByText(t('geo.map.noBackground'))).toBeNull())
})

it('says why the records cannot be shown, and keeps the map', async () => {
  mockApi('get', '/zones', [CENTRO])
  mockApiError('get', `${SHOPS_API}/features`, 422, 'invalid_area')
  renderApp(<RecordsMap kind={SHOPS} label={LABEL} filters={{}} />, { me: makeMe() })

  expect(await screen.findByText(t('errors.invalid_area'))).toBeInTheDocument()
  expect(await mapFrame(LABEL)).toBeInTheDocument()
})

it('says why the zones cannot be shown', async () => {
  mockApiError('get', '/zones', 500, 'boom')
  renderApp(<RecordsMap kind={SHOPS} label={LABEL} filters={{}} />, { me: makeMe() })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('opens on the whole country while there are no zones', async () => {
  mockApi('get', '/zones', [])
  const requests = mockApi('get', `${SHOPS_API}/features`, makeFeatures() as never)
  renderApp(<RecordsMap kind={SHOPS} label={LABEL} filters={{}} />, { me: makeMe() })

  await screen.findByText(shownInView(0))
  const [west, south, east, north] = requests[0].url.searchParams.get('bbox')!.split(',').map(Number)
  expect([west <= -73.6, south <= -55, east >= -53.6, north >= -21.8]).toEqual([
    true,
    true,
    true,
    true,
  ])
  // Within the world, as the API asks.
  expect([west >= -180, south >= -90, east <= 180, north <= 90]).toEqual([true, true, true, true])
})

it('draws the background the municipality chose, with its key', async () => {
  mockApi('get', '/map-background', {
    background: {
      ...STANDARD_MAP.background,
      key: 'maptiler',
      url: 'https://maps.test/{z}/{x}/{y}.jpg?key={apiKey}',
      attribution: 'Map by <a href="https://maps.test">Maps</a>',
      provider: 'MapTiler',
      tile_size: 512,
      zoom_offset: -1,
    },
    api_key: 'abc123',
  })
  const requests = renderMap()
  const frame = await mapFrame(LABEL)
  expect(await within(frame).findByRole('link', { name: 'Maps' })).toBeInTheDocument()

  const tile = frame.querySelector<HTMLElement>('img.leaflet-tile')!
  const zoom = Number(requests[0].url.searchParams.get('zoom'))
  // Large images are those of one zoom further out.
  expect(tile.getAttribute('src')).toMatch(
    new RegExp(`^https://maps.test/${zoom - 1}/\\d+/\\d+.jpg\\?key=abc123$`),
  )
  expect(tile.style.width).toBe('512px')
})

it('shows zones and records when the choice of background cannot be read', async () => {
  mockApiError('get', '/map-background', 500, 'boom')
  renderMap({ features: { total: 1, features: [point('a-1', 'Panadería')] } })

  expect(await mark('Panadería')).toBeInTheDocument()
  expect(await screen.findByText(t('geo.map.noBackground'))).toBeInTheDocument()
})
