import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import App from '../../App'
import { answerConfirm } from '../../test/confirm'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { boundary, CENTRO, drag, makeZone, mapFrame, NORTE, square } from './testData'
import type { Position, Zone } from './types'
import { ZonesPage } from './ZonesPage'

const label = (key: string, options = {}) => t(`geo.zones.${key}`, options)
const OVERLAP = { zone: CENTRO, other: NORTE, area_m2: 12_345 }

function renderPage(zones: Zone[] = [CENTRO, NORTE], overlaps: unknown[] = []) {
  const current = { zones }
  mockApi('get', '/zones', () => current.zones as never)
  mockApi('get', '/admin/zones/overlaps', overlaps as never)
  renderApp(<ZonesPage />, { me: makeMe({ isAdmin: true, dashboards: { economic: 'admin' } }) })
  return { user: userEvent.setup(), current }
}

const clickMap = async (x: number, y: number) =>
  fireEvent.click(await mapFrame(label('drawingLabel')), { clientX: x, clientY: y })
const corners = () => screen.getByRole<HTMLTextAreaElement>('textbox', { name: label('corners') })
const cornerCount = () => corners().value.split('\n').filter(Boolean).length
const name = () => screen.getByRole('textbox', { name: label('name') })
const save = () => screen.getByRole('button', { name: t('app.save') })

it('lists the zones with their version, and draws them', async () => {
  renderPage([makeZone({ version: 3 }), NORTE])

  const row = within(await screen.findByRole('row', { name: /^Centro/ }))
  expect(row.getAllByRole('cell').slice(0, 3).map((cell) => cell.textContent)).toEqual([
    'Centro',
    '3',
    '10/03/2025',
  ])
  const frame = await mapFrame(label('mapLabel'))
  expect(await within(frame).findByText('Norte')).toBeInTheDocument()
  expect(screen.queryByText(label('overlapsTitle'))).toBeNull()
  // Only of the dashboards the administrator can see.
  expect(
    screen.getByRole('region', { name: t('geo.unzoned.titles.economic.actors') }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('region', { name: t('geo.unzoned.titles.projects.projects') }),
  ).toBeNull()
})

it('reports the zones that overlap', async () => {
  renderPage([CENTRO, NORTE], [OVERLAP])

  expect(await screen.findByText(label('overlapsTitle'))).toBeInTheDocument()
  expect(
    screen.getByText(label('overlap', { zone: 'Centro', other: 'Norte', area: '1,23' })),
  ).toBeInTheDocument()
})

it('searches the zones', async () => {
  const { user } = renderPage()
  await screen.findByRole('row', { name: /^Centro/ })

  await user.type(screen.getAllByRole('searchbox')[0], 'nor')
  expect(screen.queryByRole('row', { name: /^Centro/ })).toBeNull()
  await user.type(screen.getAllByRole('searchbox')[0], 'x')
  expect(screen.getByText(t('app.noMatches'))).toBeInTheDocument()
})

it('draws a new zone on the map', async () => {
  const { user, current } = renderPage()
  const created = mockApi('post', '/admin/zones', () => {
    const zone = makeZone({ id: 'z-3', name: 'Sur' })
    current.zones = [...current.zones, zone]
    return { zone, overlaps: [] } as never
  }, 201)
  await user.click(await screen.findByRole('button', { name: label('draw') }))
  expect(save()).toBeDisabled()

  await user.type(name(), ' Sur ')
  for (const [x, y] of [[300, 200], [400, 200], [400, 300]]) await clickMap(x, y)
  expect(save()).toBeEnabled()
  await clickMap(300, 300)
  expect(cornerCount()).toBe(4)
  await user.click(save())

  expect(await screen.findByText(label('saved', { name: 'Sur' }))).toBeInTheDocument()
  const body = created[0].body as { name: string; boundary: { type: string; coordinates: Position[][] } }
  expect(body.name).toBe('Sur')
  expect(body.boundary.type).toBe('Polygon')
  const [ring] = body.boundary.coordinates
  // Closed, as the API asks.
  expect(ring).toHaveLength(5)
  expect(ring[4]).toEqual(ring[0])
  expect(await screen.findByRole('row', { name: /^Sur/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('closeNotice') }))
  expect(screen.queryByText(label('saved', { name: 'Sur' }))).toBeNull()
})

it('moves, adds and removes corners, and undoes it', async () => {
  const { user } = renderPage()
  await user.click(await screen.findByRole('button', { name: label('draw') }))
  fireEvent.change(corners(), { target: { value: '-31, -62\n-31, -61\n-30, -61' } })
  const corner = (number: number) =>
    screen.findByRole('button', { name: label('corner', { number }) })
  const side = (number: number) => screen.findByRole('button', { name: label('side', { number }) })

  drag(await corner(1), [-62.5, -31.5])
  await waitFor(() => expect(corners().value.split('\n')[0]).toBe('-31.500000, -62.500000'))
  await user.click(await side(2))
  expect(corners().value.split('\n')[2]).toBe('-30.500000, -61.000000')
  drag(await side(4), [-63, -30])
  await waitFor(() => expect(cornerCount()).toBe(5))
  expect(corners().value.split('\n')[4]).toBe('-30.000000, -63.000000')
  await user.click(await corner(5))
  expect(cornerCount()).toBe(4)

  const undo = screen.getByRole('button', { name: label('undo') })
  await user.click(undo)
  expect(cornerCount()).toBe(5)
  await user.click(undo)
  expect(cornerCount()).toBe(4)
  await user.click(screen.getByRole('button', { name: label('clear') }))
  expect(corners()).toHaveValue('')
  await user.click(undo)
  expect(cornerCount()).toBe(4)
})

it('does not save what is not coordinates', async () => {
  const { user } = renderPage()
  await user.click(await screen.findByRole('button', { name: label('draw') }))
  await user.type(name(), 'Sur')

  fireEvent.change(corners(), { target: { value: '-31, -62\n-31, -61\n-30, -61' } })
  expect(save()).toBeEnabled()
  fireEvent.change(corners(), { target: { value: '-31, -62\n-31, -61\n-30, -61\nx' } })

  expect(screen.getByText(t('geo.location.invalidCoordinates'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.click(screen.getByRole('button', { name: t('app.cancel') }))
  expect(await screen.findByRole('heading', { name: label('title') })).toBeInTheDocument()
})

it('says where an official boundary comes from, and only of those', async () => {
  renderPage([makeZone({ name: 'Radio urbano', source: 'Ley 10796/2022' }), NORTE])

  const cell = await screen.findByRole('cell', { name: /^Radio urbano/ })
  expect(cell).toHaveTextContent(label('official', { source: 'Ley 10796/2022' }))
  expect(screen.getByRole('cell', { name: 'Norte' })).toBeInTheDocument()
})

it('says why a boundary was refused and keeps the drawing', async () => {
  const { user } = renderPage()
  mockApiError('post', '/admin/zones', 422, 'zone_self_intersects')
  await user.click(await screen.findByRole('button', { name: label('draw') }))
  await user.type(name(), 'Sur')
  fireEvent.change(corners(), { target: { value: '0, 0\n1, 1\n1, 0\n0, 1' } })

  await user.click(save())

  expect(await screen.findByText(t('errors.zone_self_intersects'))).toBeInTheDocument()
  expect(cornerCount()).toBe(4)
})

it('renames a zone without touching its boundary', async () => {
  const { user } = renderPage()
  const saved = mockApi('patch', '/admin/zones/z-1', { zone: makeZone({ name: 'Microcentro' }), overlaps: [] } as never)
  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'Centro' }) }))

  expect(screen.queryByText(label('versionNote'))).toBeNull()
  await user.clear(name())
  expect(save()).toBeDisabled()
  await user.type(name(), 'Microcentro')
  await user.click(save())

  expect(await screen.findByText(label('saved', { name: 'Microcentro' }))).toBeInTheDocument()
  expect(saved[0].body).toEqual({ name: 'Microcentro', base_version: 1 })
})

it('moves a boundary from the version it was opened with', async () => {
  const { user } = renderPage([makeZone({ version: 4 }), NORTE])
  const saved = mockApi('patch', '/admin/zones/z-1', { zone: CENTRO, overlaps: [] } as never)
  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'Centro' }) }))

  await clickMap(50, 50)
  expect(screen.getByText(label('versionNote'))).toBeInTheDocument()
  await user.click(save())

  await waitFor(() => expect(saved).toHaveLength(1))
  const body = saved[0].body as { base_version: number; boundary: { coordinates: Position[][] } }
  expect(body.base_version).toBe(4)
  expect(body.boundary.coordinates[0]).toHaveLength(6)
})

it('says when somebody else moved the boundary in the meantime', async () => {
  const { user } = renderPage()
  mockApiError('patch', '/admin/zones/z-1', 409, 'zone_changed')
  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'Centro' }) }))
  await clickMap(50, 50)

  await user.click(save())

  expect(await screen.findByText(t('errors.zone_changed'))).toBeInTheDocument()
})

it('leaves boundaries with holes to files, but renames them', async () => {
  const hole = makeZone({ boundary: boundary(square(-62, -32), square(-61.6, -31.6, 0.2)) })
  const { user } = renderPage([hole])
  const saved = mockApi('patch', '/admin/zones/z-1', { zone: hole, overlaps: [] } as never)
  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'Centro' }) }))

  expect(screen.getByText(label('notEditable'))).toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: label('corners') })).toBeNull()
  await user.type(name(), ' viejo')
  await user.click(save())

  await waitFor(() => expect(saved[0]?.body).toEqual({ name: 'Centro viejo', base_version: 1 }))
})

it('shows every boundary a zone has had', async () => {
  const { user } = renderPage()
  mockApi('get', '/admin/zones/z-1/versions', [
    {
      version: 2,
      valid_from: '2026-01-05T12:00:00Z',
      valid_to: null,
      source: '',
      boundary: CENTRO.boundary,
    },
    {
      version: 1,
      valid_from: '2024-01-01T12:00:00Z',
      valid_to: '2026-01-05T12:00:00Z',
      source: 'Ley 10796/2022',
      boundary: NORTE.boundary,
    },
  ] as never)
  await user.click(await screen.findByRole('button', { name: label('versionsNamed', { name: 'Centro' }) }))

  const dialog = within(await screen.findByRole('dialog'))
  const rows = await dialog.findAllByRole('row')
  expect(within(rows[1]).getAllByRole('cell').slice(0, 3).map((c) => c.textContent)).toEqual([
    '2',
    '05/01/2026',
    label('current'),
  ])
  expect(within(rows[2]).getAllByRole('cell').slice(0, 3).map((c) => c.textContent)).toEqual([
    `1${label('official', { source: 'Ley 10796/2022' })}`,
    '01/01/2024',
    '05/01/2026',
  ])
  await user.click(dialog.getByRole('button', { name: label('showVersion', { number: 1 }) }))
  expect(
    await mapFrame(label('versionMapLabel', { name: 'Centro', number: 1 })),
  ).toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says why the history cannot be shown', async () => {
  const { user } = renderPage()
  mockApiError('get', '/admin/zones/z-1/versions', 404, 'not_found')
  await user.click(await screen.findByRole('button', { name: label('versionsNamed', { name: 'Centro' }) }))

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})

it('retires a zone after asking', async () => {
  const { user, current } = renderPage()
  const retired = mockApi('delete', '/admin/zones/z-1', () => {
    current.zones = [NORTE]
    return null
  })
  const button = () => screen.findByRole('button', { name: label('retireNamed', { name: 'Centro' }) })

  await user.click(await button())
  expect(await answerConfirm(user, false)).toContain(label('retireConfirm', { name: 'Centro' }))
  expect(retired).toHaveLength(0)
  await user.click(await button())
  await answerConfirm(user, true)

  expect(await screen.findByText(label('retired', { name: 'Centro' }))).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByRole('row', { name: /^Centro/ })).toBeNull())
})

it('says why a zone was not retired', async () => {
  const { user } = renderPage()
  mockApiError('delete', '/admin/zones/z-1', 404, 'not_found')

  await user.click(await screen.findByRole('button', { name: label('retireNamed', { name: 'Centro' }) }))
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})

it('says when there are no zones, and why they cannot be shown', async () => {
  const { user } = renderPage([])
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(screen.queryByRole('table')).toBeNull()
  await user.click(screen.getByRole('button', { name: label('draw') }))
  expect(await mapFrame(label('drawingLabel'))).toBeInTheDocument()
})

it('says why the zones and their overlaps cannot be shown', async () => {
  mockApiError('get', '/zones', 500, 'boom')
  mockApiError('get', '/admin/zones/overlaps', 403, 'forbidden')
  renderApp(<ZonesPage />, { me: makeMe({ isAdmin: true }) })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(screen.getByRole('button', { name: label('draw') })).toBeDisabled()
})

// GeoJSON files

const GEOJSON = { type: 'FeatureCollection', features: [] }
const file = (content: string) => new File([content], 'zonas.geojson')

async function chooseFile(content: string) {
  const { user } = renderPage()
  await user.click(await screen.findByRole('button', { name: label('import.open') }))
  const dialog = within(await screen.findByRole('dialog', { name: label('import.title') }))
  expect(dialog.getByRole('button', { name: label('import.submit') })).toBeDisabled()
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
  fireEvent.change(input, { target: { files: [file(content)] } })
  const submit = dialog.getByRole('button', { name: label('import.submit') })
  await waitFor(() => expect(submit).toBeEnabled())
  return { user, dialog, submit }
}

it('imports the zones of a file', async () => {
  const imported = mockApi('post', '/admin/zones/import', {
    created: 2,
    moved: 1,
    unchanged: 0,
    overlaps: [],
  })
  const { user, submit } = await chooseFile(JSON.stringify(GEOJSON))

  await user.click(submit)

  expect(
    await screen.findByText(label('import.done', { created: 2, moved: 1, unchanged: 0 })),
  ).toBeInTheDocument()
  expect(imported[0].body).toEqual({ geojson: GEOJSON })
  expect(screen.queryByRole('dialog')).toBeNull()
})

it.each(['no es json', '7', 'null'])('refuses a file that is not GeoJSON: %s', async (content) => {
  const { user, submit, dialog } = await chooseFile(content)

  await user.click(submit)

  expect(await dialog.findByText(label('import.unreadable'))).toBeInTheDocument()
})

it('lists every problem of a file', async () => {
  mockApi(
    'post',
    '/admin/zones/import',
    {
      error: {
        code: 'zone_file_invalid',
        message: '',
        details: [
          { row: 2, name: 'Norte', code: 'zone_self_intersects' },
          { row: 3, name: null, code: 'no_name' },
        ],
      },
    },
    422,
  )
  const { user, submit, dialog } = await chooseFile(JSON.stringify(GEOJSON))

  await user.click(submit)

  const problem = (row: number, named: string, code: string) =>
    label('import.problem', { row, name: named, problem: label(`import.codes.${code}`) })
  expect(await dialog.findByText(problem(2, 'Norte', 'zone_self_intersects'))).toBeInTheDocument()
  expect(
    dialog.getByText(problem(3, label('import.unnamed'), 'no_name')),
  ).toBeInTheDocument()
})

it('says when the file as a whole is not right, or the import fails', async () => {
  mockApi(
    'post',
    '/admin/zones/import',
    {
      error: {
        code: 'zone_file_invalid',
        message: '',
        details: [{ row: 0, name: null, code: 'empty' }],
      },
    },
    422,
  )
  const { user, submit, dialog } = await chooseFile(JSON.stringify(GEOJSON))

  await user.click(submit)
  expect(await dialog.findByText(label('import.codes.empty'))).toBeInTheDocument()
  mockApiError('post', '/admin/zones/import', 403, 'forbidden')
  await user.click(submit)
  expect(await dialog.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(dialog.queryByText(label('import.codes.empty'))).toBeNull()

  await user.click(dialog.getByRole('button', { name: t('app.cancel') }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('is reached from the menu by administrators only', async () => {
  mockApi('get', '/zones', [CENTRO])
  mockApi('get', '/admin/zones/overlaps', [])
  const { unmount } = renderApp(<App />, { me: makeMe({ isAdmin: true }) })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('link', { name: t('nav.zones') }))
  expect(await screen.findByRole('row', { name: /^Centro/ })).toBeInTheDocument()
  unmount()

  renderApp(<App />, { me: makeMe({ isAdmin: false }), route: '/admin/zones' })
  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: t('nav.zones') })).toBeNull()
})

it('says when the file cannot even be read', async () => {
  const failing = vi.spyOn(FileReader.prototype, 'readAsText').mockImplementation(function (
    this: FileReader,
  ) {
    this.onerror?.(new ProgressEvent('error') as ProgressEvent<FileReader>)
  })
  const { user, submit, dialog } = await chooseFile('{}')

  await user.click(submit)

  expect(await dialog.findByText(label('import.unreadable'))).toBeInTheDocument()
  failing.mockRestore()
})
