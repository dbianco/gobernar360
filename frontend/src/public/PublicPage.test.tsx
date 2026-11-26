import { screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import App from '../App'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import type { PublicIndicator, PublicSite } from './types'

const point = (month: number, value: number | null, below: number | null = null) => ({
  year: 2026,
  month,
  value,
  below,
  target: 4,
})

const DELAYED: PublicIndicator = {
  key: 'projects.delayed',
  name: 'Proyectos retrasados',
  dashboard_key: 'projects',
  unit: null,
  higher_is_better: false,
  value: null,
  value_below: 5,
  previous_value: 6,
  previous_below: null,
  change_previous_month: null,
  last_year_value: null,
  last_year_below: null,
  change_last_year: null,
  target: 4,
  on_track: null,
  series: [point(10, 6), point(11, null, 5)],
}

const RATIO: PublicIndicator = {
  ...DELAYED,
  key: 'projects.budget_executed_ratio',
  name: 'Presupuesto ejecutado',
  unit: 'ratio',
  higher_is_better: true,
  value: 0.465,
  value_below: null,
  change_previous_month: -0.008,
  target: 0.5,
  on_track: false,
  series: [point(10, 0.47), point(11, 0.465)],
}

const SITE: PublicSite = {
  slug: 'noetinger',
  name: 'Noetinger',
  kind: 'municipality',
  small_count_threshold: 5,
  dashboards: [
    {
      key: 'projects',
      name: 'Proyectos',
      lights: [
        { year: 2026, month: 10, color: 'green' },
        { year: 2026, month: 11, color: 'yellow' },
      ],
    },
  ],
  indicators: [DELAYED, RATIO],
  reports: [{ year: 2026, month: 10, version: 2, closed_at: '2026-11-03T12:00:00Z' }],
}

function renderPublic(slug = 'noetinger') {
  // Nobody is signed in.
  renderApp(<App />, { me: null, route: `/p/${slug}` })
}

it('shows what the municipality published to anyone', async () => {
  const requests = mockApi('get', '/public/noetinger', SITE)
  renderPublic()

  expect(await screen.findByRole('heading', { name: 'Noetinger', level: 1 })).toBeInTheDocument()
  const lights = screen.getByRole('region', { name: t('public.lights') })
  expect(within(lights).getByRole('group', { name: t('projects.title') })).toHaveTextContent(
    t('status.states.yellow'),
  )
  const cards = [...document.querySelectorAll('[data-indicator]')]
  expect(cards.map((card) => card.getAttribute('data-indicator'))).toEqual([
    'projects.delayed',
    'projects.budget_executed_ratio',
  ])
  expect(requests).toHaveLength(1)
})

it('shows a small count as fewer than the threshold, never the number', async () => {
  mockApi('get', '/public/noetinger', SITE)
  renderPublic()

  const card = within(
    (await screen.findByText(t('overview.indicators.projects.delayed'))).closest(
      '[data-indicator]',
    ) as HTMLElement,
  )

  expect(card.getByText(t('public.below', { count: 5 }))).toBeInTheDocument()
  expect(card.queryByText(/respecto del mes anterior/)).not.toBeInTheDocument()
  expect(card.queryByText(t('indicators.onTrack'))).not.toBeInTheDocument()
  expect(
    screen.getByText(t('public.note', { count: 5, last: 4 })),
  ).toBeInTheDocument()
})

it('shows ratios with their change and target', async () => {
  mockApi('get', '/public/noetinger', SITE)
  renderPublic()

  const card = within(
    (await screen.findByText(t('overview.indicators.projects.budget_executed_ratio'))).closest(
      '[data-indicator]',
    ) as HTMLElement,
  )

  expect(card.getByText('46,5 %')).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.vsPreviousMonth', { change: '\u22120,8 p.p.' })),
  ).toBeInTheDocument()
  expect(card.getByText(t('indicators.offTrack'))).toBeInTheDocument()
})

it('lists the published reports to download', async () => {
  mockApi('get', '/public/noetinger', SITE)
  renderPublic()

  const reports = await screen.findByRole('region', { name: t('public.reports') })

  expect(reports).toHaveTextContent(t('public.report', { month: 'octubre 2026' }))
  expect(within(reports).getByRole('link', { name: t('public.download') })).toHaveAttribute(
    'href',
    '/api/public/noetinger/reports/2026/10',
  )
})

it('says the page does not exist for an unknown or unpublished address', async () => {
  mockApiError('get', '/public/comuna-demo', 404, 'not_found')
  renderPublic('comuna-demo')

  expect(
    await screen.findByRole('heading', { name: t('public.notFoundTitle') }),
  ).toBeInTheDocument()
})

it('says when a target is met', async () => {
  mockApi('get', '/public/noetinger', {
    ...SITE,
    indicators: [{ ...RATIO, value: 0.6, on_track: true }],
  })
  renderPublic()

  expect(await screen.findByText(t('indicators.onTrack'))).toBeInTheDocument()
  expect(screen.queryByText(t('indicators.offTrack'))).not.toBeInTheDocument()
})

it('shows by its published name a dashboard this version does not have', async () => {
  const lights = SITE.dashboards[0].lights
  mockApi('get', '/public/noetinger', {
    ...SITE,
    dashboards: [{ key: 'retired', name: 'Tablero retirado', lights }],
  })
  renderPublic()

  expect(await screen.findByRole('group', { name: 'Tablero retirado' })).toHaveTextContent(
    t('status.states.yellow'),
  )
})

it('says so while no report has been published, and shows no empty section', async () => {
  mockApi('get', '/public/noetinger', {
    ...SITE,
    small_count_threshold: 1,
    dashboards: [],
    indicators: [],
    reports: [],
  })
  renderPublic()

  expect(await screen.findByText(t('public.noReports'))).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: t('public.lights') })).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: t('public.indicators') })).not.toBeInTheDocument()
  // Nothing is hidden, so there is nothing to explain.
  expect(screen.queryByText(t('public.note', { count: 1, last: 0 }))).not.toBeInTheDocument()
})

it('says why the page cannot be shown when it fails', async () => {
  mockApiError('get', '/public/noetinger', 403, 'forbidden')
  renderPublic()

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: t('public.notFoundTitle') }),
  ).not.toBeInTheDocument()
})
