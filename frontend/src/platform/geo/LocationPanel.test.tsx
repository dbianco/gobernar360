import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { answerConfirm } from '../../test/confirm'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { LocationPanel } from './LocationPanel'
import { CENTRO, drag, mapFrame, NORTE, SHOPS, SHOPS_API, WORKS, WORKS_API } from './testData'
import type { RecordLocation } from './types'

const label = (key: string, options = {}) => t(`geo.location.${key}`, options)
const button = (key: string) => screen.getByRole('button', { name: label(key) })
const PLACE: RecordLocation = {
  location: { type: 'Point', coordinates: [-61.5, -31.5] },
  kinds: ['Point'],
  zones: [{ id: 'z-1', name: 'Centro' }],
}
const NOWHERE: RecordLocation = { location: null, kinds: ['Point'], zones: [] }
const STREET: RecordLocation = { ...NOWHERE, kinds: ['Point', 'LineString'] }

function renderPanel(
  current: RecordLocation,
  options: { canEdit?: boolean; works?: boolean } = {},
) {
  const path = `${options.works ? WORKS_API : SHOPS_API}/r-1/location`
  mockApi('get', '/zones', [CENTRO, NORTE])
  mockApi('get', path, () => current as never)
  const saved = mockApi('put', path, (request) => {
    const { location } = request.body as Pick<RecordLocation, 'location'>
    current = { ...current, location, zones: location ? [{ id: 'z-2', name: 'Norte' }] : [] }
    return current as never
  })
  renderApp(
    <LocationPanel
      kind={options.works ? WORKS : SHOPS}
      recordId="r-1"
      canEdit={options.canEdit ?? true}
    />,
    { me: makeMe() },
  )
  return saved
}

const clickMap = async (x: number, y: number) =>
  fireEvent.click(await mapFrame(label('mapLabel')), { clientX: x, clientY: y })

it('shows where the record is and its zones', async () => {
  renderPanel(PLACE, { canEdit: false })

  expect(await screen.findByText('-31.500000, -61.500000')).toBeInTheDocument()
  expect(screen.getAllByText('Centro').length).toBeGreaterThan(0)
  expect(await mapFrame(label('mapLabel'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('change') })).toBeNull()
  expect(screen.queryByRole('button', { name: label('remove') })).toBeNull()
})

it('says when the record is outside every zone', async () => {
  renderPanel({ ...PLACE, zones: [] })

  expect(await screen.findByText(label('outside'))).toBeInTheDocument()
})

it('shows a line without its coordinates', async () => {
  renderPanel(
    {
      ...STREET,
      location: {
        type: 'LineString',
        coordinates: [
          [-61.5, -31.5],
          [-61.4, -31.5],
        ],
      },
    },
    { works: true },
  )

  const frame = await mapFrame(label('mapLabel'))
  expect(frame.querySelectorAll('path').length).toBeGreaterThan(0)
  expect(screen.queryByText(/-31\.5/)).toBeNull()
})

it('sets the location by clicking on the map', async () => {
  const saved = renderPanel(NOWHERE)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('set') }))
  expect(screen.getByRole('button', { name: t('app.save') })).toBeDisabled()
  await clickMap(400, 300)
  const written = screen.getByRole<HTMLInputElement>('textbox', { name: label('coordinates') }).value
  // A second click moves it rather than adding another.
  await clickMap(410, 300)
  expect(
    screen.getByRole<HTMLInputElement>('textbox', { name: label('coordinates') }).value,
  ).not.toBe(written)
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
  const { location } = saved[0].body as RecordLocation
  expect(location?.type).toBe('Point')
  const [longitude, latitude] = location!.coordinates as [number, number]
  expect(longitude).toBeGreaterThan(-62)
  expect(longitude).toBeLessThan(-61)
  expect(latitude).toBeGreaterThan(-32)
  expect(latitude).toBeLessThan(-30)
  // Back to showing it, with the zone the server worked out.
  expect(await screen.findByRole('button', { name: label('change') })).toBeInTheDocument()
  expect(screen.getAllByText('Norte').length).toBeGreaterThan(0)
})

it('sets the location by typing coordinates', async () => {
  const saved = renderPanel(NOWHERE)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('set') }))
  const field = screen.getByRole('textbox', { name: label('coordinates') })

  await user.type(field, '-31.5')
  expect(screen.getByText(label('invalidCoordinates'))).toBeInTheDocument()
  expect(screen.getByRole('button', { name: t('app.save') })).toBeDisabled()
  await user.clear(field)
  await user.type(field, '-31,5; -61,25')
  expect(screen.queryByText(label('invalidCoordinates'))).toBeNull()
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
  expect(saved[0].body).toEqual({ location: { type: 'Point', coordinates: [-61.25, -31.5] } })
})

it('moves the location by dragging its mark', async () => {
  renderPanel(PLACE)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('change') }))

  drag(await screen.findByRole('button', { name: label('mark', { number: 1 }) }), [-61.2, -31.2])

  await waitFor(() =>
    expect(screen.getByRole('textbox', { name: label('coordinates') })).toHaveValue(
      '-31.200000, -61.200000',
    ),
  )
})

it('draws a line point by point, and takes the last one back', async () => {
  const saved = renderPanel(STREET, { works: true })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('set') }))

  await clickMap(300, 300)
  await user.click(screen.getByRole('radio', { name: label('kinds.LineString') }))
  // The line starts at the point, which alone is not enough.
  expect(screen.getByRole('button', { name: t('app.save') })).toBeDisabled()
  await clickMap(400, 300)
  await clickMap(500, 300)
  await user.click(button('undo'))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
  const { location } = saved[0].body as RecordLocation
  expect(location?.type).toBe('LineString')
  const [first, second] = location!.coordinates as [number, number][]
  expect(location!.coordinates).toHaveLength(2)
  expect(second[0]).toBeGreaterThan(first[0])
})

it('takes the points of a line as text, and keeps the first when it becomes a point', async () => {
  const saved = renderPanel(STREET, { works: true })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('set') }))
  await user.click(screen.getByRole('radio', { name: label('kinds.LineString') }))
  const lines = screen.getByRole('textbox', { name: label('lineCoordinates') })

  await user.type(lines, '-31.5, -61.5{Enter}x')
  expect(screen.getByText(label('invalidCoordinates'))).toBeInTheDocument()
  await user.clear(lines)
  await user.type(lines, '-31.5, -61.5{Enter}-31.4, -61.4')
  drag(await screen.findByRole('button', { name: label('mark', { number: 2 }) }), [-61.3, -31.3])
  await waitFor(() => expect(lines).toHaveValue('-31.500000, -61.500000\n-31.300000, -61.300000'))
  await user.click(screen.getByRole('radio', { name: label('kinds.Point') }))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
  expect(saved[0].body).toEqual({ location: { type: 'Point', coordinates: [-61.5, -31.5] } })
})

it('changes nothing when the edition is cancelled', async () => {
  const saved = renderPanel(PLACE)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('change') }))
  const field = screen.getByRole('textbox', { name: label('coordinates') })
  await user.clear(field)
  await user.click(screen.getByRole('button', { name: t('app.cancel') }))

  expect(screen.getByText('-31.500000, -61.500000')).toBeInTheDocument()
  expect(saved).toHaveLength(0)
})

it('removes the location after asking', async () => {
  const saved = renderPanel(PLACE)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('remove') }))
  expect(await answerConfirm(user, false)).toContain(label('removeConfirm'))
  expect(saved).toHaveLength(0)
  await user.click(button('remove'))
  await answerConfirm(user, true)

  expect(await screen.findByText(label('none'))).toBeInTheDocument()
  expect(saved[0].body).toEqual({ location: null })
})

it('says why a location was not saved, and keeps it to try again', async () => {
  renderPanel(NOWHERE)
  mockApiError('put', `${SHOPS_API}/r-1/location`, 422, 'invalid_location')
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('set') }))
  await user.type(screen.getByRole('textbox', { name: label('coordinates') }), '-31.5, -61.5')

  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText(t('errors.invalid_location'))).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: label('coordinates') })).toHaveValue('-31.5, -61.5')
})

it('says why the location or the zones cannot be shown', async () => {
  mockApiError('get', `${SHOPS_API}/r-1/location`, 403, 'forbidden')
  mockApiError('get', '/zones', 500, 'boom')
  renderApp(<LocationPanel kind={SHOPS} recordId="r-1" canEdit />, { me: makeMe() })

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
