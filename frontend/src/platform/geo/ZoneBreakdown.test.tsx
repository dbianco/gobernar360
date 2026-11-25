import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { boundariesOf } from './asOf'
import { SHADES } from './shading'
import { CENTRO, HOMES, makeBreakdown, mapFrame, NORTE, SHOPS, SHOPS_API, WORKS, WORKS_API } from './testData'
import type { Breakdown } from './types'
import { ZoneBreakdown } from './ZoneBreakdown'

const label = (key: string, options = {}) => t(`geo.breakdown.${key}`, options)

function renderBreakdown(breakdown: Breakdown = makeBreakdown(), asOf?: string) {
  const zones = mockApi('get', '/zones', [CENTRO, NORTE])
  const requests = mockApi('get', `${SHOPS_API}/zones`, breakdown as never)
  renderApp(<ZoneBreakdown kind={SHOPS} filters={{ q: 'pan' }} asOf={asOf} />, { me: makeMe() })
  return { zones, requests }
}

const cells = async (name: string) =>
  within(await screen.findByRole('row', { name: new RegExp(`^${name}`) }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent)

it('shows the figures of every zone, of what has none, and the total', async () => {
  const { requests } = renderBreakdown()

  expect(await cells('Centro')).toEqual(['Centro', '3', 'Alimentos 2 · Sin sector 1'])
  expect(await cells('Norte')).toEqual(['Norte', '0', ''])
  expect(await cells(label('outside'))).toEqual([label('outside'), '1', ''])
  expect(await cells(label('unlocated'))).toEqual([label('unlocated'), '2', ''])
  expect(await cells(label('total'))).toEqual([label('total'), '6', ''])
  expect(screen.getByText(label('boundariesToday'))).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('q')).toBe('pan')
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    '/api/dashboards/economic/geo/actors/zones.csv?q=pan',
  )
  // With one figure there is nothing to choose.
  expect(screen.queryByRole('combobox')).toBeNull()
})

it('shades the zones and writes each figure on its zone', async () => {
  renderBreakdown()
  const frame = await mapFrame(label('mapLabel', { metric: t('geo.metrics.economic.actors.actors.label') }))

  await waitFor(() => expect(within(frame).getByText(/Centro\s+3/)).toBeInTheDocument())
  expect(within(frame).getByText(/Norte\s+0/)).toBeInTheDocument()
  const fills = [...frame.querySelectorAll('path')].map((path) => path.getAttribute('fill'))
  // Zero is not shaded.
  expect(fills).toEqual([SHADES[3], 'none'])
  const legend = screen.getByRole('list', { name: label('legend') })
  expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['3'])
})

it('neither shades nor tells what is hidden', async () => {
  const breakdown = makeBreakdown({ grouping: null, threshold: 5 })
  breakdown.zones[0] = { ...breakdown.zones[0], values: { actors: null }, groups: [] }
  breakdown.zones[1] = { ...breakdown.zones[1], values: { actors: 8 } }
  renderBreakdown(breakdown)

  expect(await cells('Centro')).toEqual(['Centro', label('hidden')])
  expect(screen.getByText(label('hiddenNote', { count: 5 }))).toBeInTheDocument()
  const frame = await mapFrame(label('mapLabel', { metric: t('geo.metrics.economic.actors.actors.label') }))
  await waitFor(() =>
    expect(within(frame).getByText(new RegExp(`Centro\\s+${label('hidden')}`))).toBeInTheDocument(),
  )
  const paths = [...frame.querySelectorAll('path')]
  expect(paths.map((path) => path.getAttribute('fill'))).toEqual(['none', SHADES[3]])
  expect(paths[0]).toHaveAttribute('stroke-dasharray')
})

it('uses and draws the boundaries of a past period, and says so', async () => {
  const { zones, requests } = renderBreakdown(
    makeBreakdown({ boundaries_as_of: '2025-12-31' }),
    '2025-12-31',
  )

  expect(
    await screen.findByText(label('boundariesAsOf', { date: '31/12/2025' })),
  ).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('as_of')).toBe('2025-12-31')
  expect(zones[0].url.searchParams.get('as_of')).toBe('2025-12-31')
  expect(screen.getByRole('link', { name: label('download') }).getAttribute('href')).toContain(
    'as_of=2025-12-31',
  )
})

it('takes the boundaries of the end of past years only', () => {
  // Tests run in 2026.
  expect(boundariesOf(2025)).toBe('2025-12-31')
  expect(boundariesOf('2024')).toBe('2024-12-31')
  expect(boundariesOf(2026)).toBeUndefined()
  expect(boundariesOf(2027)).toBeUndefined()
  expect(boundariesOf(undefined)).toBeUndefined()
})

it('shades by the figure chosen, amounts included', async () => {
  const values = (active: number, planned: string) => ({ active, planned_budget: planned })
  const row = (active: number, planned: string) => ({
    values: values(active, planned),
    groups: [],
    suppressed: false,
  })
  mockApi('get', '/zones', [CENTRO, NORTE])
  mockApi('get', `${WORKS_API}/zones`, makeBreakdown({
    metrics: [
      { key: 'active', unit: null },
      { key: 'planned_budget', unit: 'money' },
    ],
    grouping: null,
    zones: [
      { zone: { id: CENTRO.id, name: CENTRO.name }, ...row(1, '900000.00') },
      { zone: { id: NORTE.id, name: NORTE.name }, ...row(4, '1500.00') },
    ],
    outside: row(0, '0.00'),
    unlocated: row(0, '0.00'),
    total: row(5, '901500.00'),
  }) as never)
  renderApp(<ZoneBreakdown kind={WORKS} filters={{}} />, { me: makeMe() })
  const user = userEvent.setup()
  const metric = (key: string) => t(`geo.metrics.projects.projects.${key}.label`)
  const fills = async (key: string) => {
    const frame = await mapFrame(label('mapLabel', { metric: metric(key) }))
    return [...frame.querySelectorAll('path')].map((path) => path.getAttribute('fill'))
  }

  await waitFor(async () => expect(await fills('active')).toEqual([SHADES[2], SHADES[3]]))
  await user.selectOptions(screen.getByRole('combobox', { name: label('shadeBy') }), metric('planned_budget'))

  await waitFor(async () => expect(await fills('planned_budget')).toEqual([SHADES[3], SHADES[2]]))
  expect((await cells('Centro')).map((text) => text?.replace(/\s/g, ' '))).toEqual([
    'Centro',
    '1',
    '$ 900.000',
  ])
})

it('tells only administrators that there are no zones yet', async () => {
  const { unmount } = renderApp(<ZoneBreakdown kind={HOMES} filters={{}} />, {
    me: makeMe({ isAdmin: true }),
  })
  expect(await screen.findByRole('link', { name: label('goToZones') })).toHaveAttribute(
    'href',
    '/admin/zones',
  )
  unmount()

  renderApp(<ZoneBreakdown kind={HOMES} filters={{}} />, { me: makeMe() })
  await waitFor(() => expect(screen.queryByLabelText(t('app.loading'))).toBeNull())
  expect(screen.queryByText(label('noZones'), { exact: false })).toBeNull()
})

it('says why the figures cannot be shown', async () => {
  mockApiError('get', `${SHOPS_API}/zones`, 403, 'forbidden')
  renderApp(<ZoneBreakdown kind={SHOPS} filters={{}} />, { me: makeMe() })

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})

it('says the range of each shade when several zones share one', async () => {
  const zones = Array.from({ length: 8 }, (_, index) => ({
    ...CENTRO,
    id: `z-${index}`,
    name: `Zona ${index}`,
  }))
  mockApi('get', '/zones', zones as never)
  mockApi('get', `${SHOPS_API}/zones`, makeBreakdown({
    zones: zones.map(({ id, name }, index) => ({
      zone: { id, name },
      values: { actors: (index + 1) * 10 },
      groups: [],
      suppressed: false,
    })),
  }) as never)
  renderApp(<ZoneBreakdown kind={SHOPS} filters={{}} />, { me: makeMe() })

  const legend = await screen.findByRole('list', { name: label('legend') })
  expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    '10 a 20',
    '30 a 40',
    '50 a 60',
    '70 a 80',
  ])
})
