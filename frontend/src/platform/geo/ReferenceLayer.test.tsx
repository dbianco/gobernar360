import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError, STANDARD_MAP } from '../../test/server'
import { GeoMap } from './GeoMap'
import { mapFrame, mark } from './testData'
import type { ReferenceFeature, ReferenceLayerKey } from './types'

const label = (key: string, options = {}) => t(`geo.reference.${key}`, options)
const IMPORTED = '2026-11-20T12:00:00Z'

const facility = (overrides: Partial<ReferenceFeature> = {}): ReferenceFeature => ({
  id: 'f-1',
  name: 'Hospital <b>Municipal</b>',
  properties: { type: 'Con internación', sector: 'MUNICIPAL', address: 'San Martín 100' },
  geometry: { type: 'Point', coordinates: [-61.5, -31.5] },
  ...overrides,
})
const ALEM = facility({
  id: 'f-2',
  name: 'Escuela Alem',
  properties: { level: 'Primario' },
  geometry: { type: 'Point', coordinates: [-61.4, -31.4] },
})

function renderMap(
  layers: ReferenceLayerKey[] = ['health'],
  features: Partial<Record<ReferenceLayerKey, ReferenceFeature[]>> = { health: [facility()] },
) {
  mockApi(
    'get',
    '/geo/reference-layers',
    layers.map((layer) => ({ layer, features: 1, imported_at: IMPORTED })),
  )
  const requests = layers.map((layer) =>
    mockApi('get', `/geo/reference-layers/${layer}`, {
      features: features[layer] ?? [],
      truncated: false,
    } as never),
  )
  renderApp(<GeoMap label="Mapa" bounds={[-62, -32, -61, -31]} />, { me: makeMe() })
  return { user: userEvent.setup(), requests }
}

const toggle = () =>
  screen.findByRole('switch', { name: (name) => name.startsWith(label('show')) })
const markName = (layer: ReferenceLayerKey, name: string) => label(`layers.${layer}`, { name })

it('shows the facilities of the visible area when asked to, and not before', async () => {
  const { user, requests } = renderMap()
  const frame = await mapFrame('Mapa')
  await toggle()
  expect(requests[0]).toHaveLength(0)
  expect(within(frame).queryByText(/IDECOR/)).toBeNull()

  await user.click(await toggle())

  expect(await mark(markName('health', 'Hospital <b>Municipal</b>'))).toHaveTextContent(
    label('marks.health'),
  )
  const bbox = requests[0][0].url.searchParams.get('bbox')!.split(',').map(Number)
  expect(bbox[0]).toBeLessThan(-61.5)
  expect(bbox[3]).toBeGreaterThan(-31.5)
  expect(within(frame).getByText(new RegExp(label('credit')))).toBeInTheDocument()

  await user.click(await toggle())
  expect(screen.queryByRole('button', { name: /Hospital/ })).toBeNull()
  expect(within(frame).queryByText(new RegExp(label('credit')))).toBeNull()
})

it('says what a facility is when it is pressed, as its source wrote it', async () => {
  const { user } = renderMap()
  await user.click(await toggle())

  await user.click(await mark(markName('health', 'Hospital <b>Municipal</b>')))

  const lines = [...document.querySelectorAll('.leaflet-popup-content > div > *')]
  expect(lines.map((element) => element.textContent)).toEqual([
    'Hospital <b>Municipal</b>',
    label('properties.type', { value: 'Con internación' }),
    label('properties.sector', { value: 'MUNICIPAL' }),
    label('properties.address', { value: 'San Martín 100' }),
    label('source'),
  ])
})

it('says it with the keyboard too', async () => {
  const { user } = renderMap()
  await user.click(await toggle())
  const pin = await mark(markName('health', 'Hospital <b>Municipal</b>'))

  pin.focus()
  await user.keyboard('x')
  expect(document.querySelector('.leaflet-popup')).toBeNull()
  await user.keyboard('{Enter}')

  expect(document.querySelector('.leaflet-popup')).not.toBeNull()
})

it('gives one mark to the schools of a building, and tells them apart', async () => {
  const night = { ...ALEM, id: 'f-3', name: 'Escuela nocturna', properties: { level: 'Adultos' } }
  const { user, requests } = renderMap(['health', 'schools'], { schools: [ALEM, night] })
  await user.click(await toggle())

  await user.click(await mark(markName('schools', 'Escuela Alem, Escuela nocturna')))

  expect(screen.getByText(label('properties.level', { value: 'Primario' }))).toBeInTheDocument()
  expect(screen.getByText(label('properties.level', { value: 'Adultos' }))).toBeInTheDocument()
  expect(requests.map((asked) => asked.length)).toEqual([1, 1])
})

it('asks again when the map moves', async () => {
  const { user, requests } = renderMap()
  await user.click(await toggle())
  await waitFor(() => expect(requests[0]).toHaveLength(1))

  await user.click(screen.getByRole('button', { name: t('geo.map.zoomIn') }))

  await waitFor(() => expect(requests[0]).toHaveLength(2))
  const [before, after] = requests[0].map((request) => request.url.searchParams.get('bbox'))
  expect(after).not.toBe(before)
})

it('offers nothing where nothing was imported', async () => {
  renderMap([])

  await mapFrame('Mapa')
  await waitFor(() => expect(screen.queryByRole('switch')).toBeNull())
})

it('does not offer them while a background is only being tried', async () => {
  const asked = mockApi('get', '/geo/reference-layers', [])
  renderApp(
    <GeoMap label="Mapa" bounds={[-62, -32, -61, -31]} background={STANDARD_MAP as never} />,
    { me: makeMe() },
  )

  expect(await mapFrame('Mapa')).toBeInTheDocument()
  expect(screen.queryByRole('switch')).toBeNull()
  expect(asked).toHaveLength(0)
})

it('keeps the map when it cannot know what was imported', async () => {
  mockApiError('get', '/geo/reference-layers', 500, 'boom')
  renderApp(<GeoMap label="Mapa" bounds={[-62, -32, -61, -31]} />, { me: makeMe() })

  expect(await mapFrame('Mapa')).toBeInTheDocument()
  expect(screen.queryByRole('switch')).toBeNull()
})

it('keeps the map when the facilities cannot be read', async () => {
  const { user } = renderMap()
  mockApiError('get', '/geo/reference-layers/health', 500, 'boom')

  await user.click(await toggle())

  expect(await mapFrame('Mapa')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Hospital/ })).toBeNull()
})
