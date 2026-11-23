import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { OverviewPage } from './OverviewPage'

it('renders indicators returned by the overview endpoint', async () => {
  mockApi('get', '/overview', [
    {
      dashboard_key: 'projects',
      indicators: [
        { key: 'projects.active', value: 7, unit: null },
        { key: 'projects.average_progress', value: 42, unit: 'percent' },
        { key: 'projects.budget_executed_ratio', value: 0.256, unit: 'ratio' },
        { key: 'projects.milestones_in_alert', value: null, unit: null },
      ],
      status: [],
    },
  ])
  renderApp(<OverviewPage />, {
    me: makeMe({ dashboards: { projects: 'viewer' } }),
  })

  const card = (key: string) =>
    within(screen.getByText(t(`overview.indicators.${key}`)).closest('[data-indicator]')!)

  expect(await screen.findByRole('heading', { name: t('projects.title') })).toBeInTheDocument()
  expect(card('projects.active').getByText('7')).toBeInTheDocument()
  expect(card('projects.average_progress').getByText('42 %')).toBeInTheDocument()
  expect(card('projects.budget_executed_ratio').getByText('25,6 %')).toBeInTheDocument()
  expect(card('projects.milestones_in_alert').getByText('—')).toBeInTheDocument()
})

it('says so when a dashboard has no data yet', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [], status: [] }])
  renderApp(<OverviewPage />, {
    me: makeMe({ dashboards: { projects: 'viewer' } }),
  })

  expect(await screen.findByText(t('overview.noData'))).toBeInTheDocument()
})

it('shows an empty state when the user has no dashboards', async () => {
  mockApi('get', '/overview', [])
  renderApp(<OverviewPage />, { me: makeMe() })

  expect(await screen.findByText(t('overview.emptyTitle'))).toBeInTheDocument()
})

it('renders the environment indicators with their own labels', async () => {
  mockApi('get', '/overview', [
    {
      dashboard_key: 'environment',
      indicators: [
        { key: 'environment.variables', value: 12, unit: null },
        { key: 'environment.load_completion', value: 0.24, unit: 'ratio' },
        { key: 'environment.targets_met', value: 3, unit: null },
        { key: 'environment.targets_missed', value: 1, unit: null },
      ],
      status: [],
    },
  ])
  renderApp(<OverviewPage />, {
    me: makeMe({ dashboards: { environment: 'viewer' } }),
  })

  expect(await screen.findByRole('heading', { name: t('environment.title') })).toBeInTheDocument()
  const cards = document.querySelectorAll('[data-indicator]')
  expect([...cards].map((card) => card.textContent)).toEqual([
    'Variables ambientales12',
    'Cargas del año realizadas24 %',
    'Metas ambientales cumplidas3',
    'Metas ambientales no cumplidas1',
  ])
})

const INDICATOR = { key: 'projects.active', value: 7, unit: null }
const monthState = (month: number, color: string) =>
  t('status.monthLabel', {
    month: t(`status.months.${month}`),
    state: t(`status.states.${color}`),
  })
const lightCard = (labelKey: string) => within(screen.getByRole('group', { name: t(labelKey) }))
const renderOverview = () =>
  renderApp(<OverviewPage />, {
    me: makeMe({ dashboards: { projects: 'viewer', environment: 'viewer' } }),
  })

it("shows each dashboard's latest light with its month and state, and the earlier ones", async () => {
  mockApi('get', '/overview', [
    {
      dashboard_key: 'projects',
      indicators: [INDICATOR],
      status: [
        { year: 2025, month: 1, color: 'red' },
        { year: 2024, month: 12, color: 'yellow' },
        { year: 2024, month: 10, color: 'green' },
      ],
    },
  ])
  renderOverview()

  await screen.findByRole('heading', { name: t('projects.title') })
  const card = lightCard('projects.title')
  expect(card.getByText('Enero 2025')).toBeInTheDocument()
  expect(card.getByText(t('status.states.red'))).toBeInTheDocument()
  // Earlier months read left to right, oldest first.
  expect(card.getAllByRole('img').map((light) => light.getAttribute('aria-label'))).toEqual([
    monthState(10, 'green'),
    monthState(12, 'yellow'),
  ])
})

it('says so when a dashboard has no light yet', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [INDICATOR], status: [] }])
  renderOverview()

  await screen.findByRole('heading', { name: t('projects.title') })
  const card = lightCard('projects.title')
  expect(card.getByText(t('status.states.none'))).toBeInTheDocument()
  expect(card.queryByRole('img')).not.toBeInTheDocument()
})

it('puts the lights before the indicator sections', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [INDICATOR], status: [] }])
  renderOverview()

  const heading = await screen.findByRole('heading', {
    name: t('projects.title'),
  })
  const lights = screen.getByRole('region', { name: t('overview.lights') })
  expect(lights.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

it('collapses and expands a section from its heading', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [INDICATOR], status: [] }])
  renderOverview()
  const toggle = await screen.findByRole('button', {
    name: t('projects.title'),
  })
  const label = t('overview.indicators.projects.active')
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByText(label)).toBeInTheDocument()

  await userEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByText(label)).not.toBeInTheDocument()

  await userEvent.click(toggle)

  expect(screen.getByText(label)).toBeInTheDocument()
})

it('remembers which sections were collapsed', async () => {
  const sections = ['projects', 'environment'].map((key) => ({
    dashboard_key: key,
    indicators: [],
    status: [],
  }))
  mockApi('get', '/overview', sections)
  const first = renderOverview()
  await userEvent.click(await screen.findByRole('button', { name: t('environment.title') }))
  first.unmount()

  renderOverview()

  expect(await screen.findByRole('button', { name: t('environment.title') })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  expect(screen.getByRole('button', { name: t('projects.title') })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
})

it('still works when the browser refuses to store which sections were collapsed', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [], status: [] }])
  const refuse = () => {
    throw new Error('storage is blocked')
  }
  const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(refuse)
  const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(refuse)
  renderOverview()

  const toggle = await screen.findByRole('button', {
    name: t('projects.title'),
  })
  await userEvent.click(toggle)

  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  get.mockRestore()
  set.mockRestore()
})

it('shows earlier lights in browsers without Array.prototype.toReversed', async () => {
  const original = Array.prototype.toReversed
  // @ts-expect-error simulating a browser older than ES2023
  delete Array.prototype.toReversed
  mockApi('get', '/overview', [
    {
      dashboard_key: 'projects',
      indicators: [],
      status: [
        { year: 2025, month: 2, color: 'red' },
        { year: 2025, month: 1, color: 'green' },
      ],
    },
  ])
  try {
    renderOverview()
    await screen.findByRole('heading', { name: t('projects.title') })
    expect(lightCard('projects.title').getByRole('img')).toHaveAccessibleName(monthState(1, 'green'))
  } finally {
    Array.prototype.toReversed = original
  }
})

it('ignores a stored list of collapsed sections that makes no sense', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [], status: [] }])
  window.localStorage.setItem('overview.collapsed', JSON.stringify({ projects: true }))
  renderOverview()

  expect(await screen.findByRole('button', { name: t('projects.title') })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
})

it('keeps only the names in a stored list of collapsed sections', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [], status: [] }])
  window.localStorage.setItem('overview.collapsed', JSON.stringify([7, 'projects']))
  renderOverview()

  expect(await screen.findByRole('button', { name: t('projects.title') })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
})

it('leaves out a dashboard this version does not know', async () => {
  mockApi('get', '/overview', [
    { dashboard_key: 'retired', indicators: [], status: [] },
    { dashboard_key: 'projects', indicators: [], status: [] },
  ])
  renderOverview()

  expect(await screen.findByRole('button', { name: t('projects.title') })).toBeInTheDocument()
  expect(screen.getAllByRole('button', { expanded: true })).toHaveLength(1)
})

it('says why the overview cannot be loaded', async () => {
  mockApiError('get', '/overview', 500, 'boom')
  renderOverview()

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
