import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeEvolution, makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { OverviewPage } from './OverviewPage'

it('renders indicators returned by the overview endpoint', async () => {
  mockApi('get', '/overview', [
    {
      dashboard_key: 'projects',
      indicators: [
        makeEvolution('projects.active', 7),
        makeEvolution('projects.average_progress', 42, 'percent'),
        makeEvolution('projects.budget_executed_ratio', 0.256, 'ratio'),
        makeEvolution('projects.milestones_in_alert', null),
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
        makeEvolution('environment.variables', 12),
        makeEvolution('environment.load_completion', 0.24, 'ratio'),
        makeEvolution('environment.targets_met', 3),
        makeEvolution('environment.targets_missed', 1),
      ],
      status: [],
    },
  ])
  renderApp(<OverviewPage />, {
    me: makeMe({ dashboards: { environment: 'viewer' } }),
  })

  expect(await screen.findByRole('heading', { name: t('environment.title') })).toBeInTheDocument()
  // Each card starts with its label and its value.
  const cards = document.querySelectorAll('[data-indicator]')
  const headline = (card: Element) =>
    [...card.querySelectorAll('p')]
      .slice(0, 2)
      .map((line) => line.textContent)
      .join('')
  expect([...cards].map(headline)).toEqual([
    'Variables ambientales12',
    'Cargas del año realizadas24 %',
    'Metas ambientales cumplidas3',
    'Metas ambientales no cumplidas1',
  ])
})

const INDICATOR = makeEvolution('projects.active', 7)
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

it('shows the indicators that combine dashboards after the lights', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [INDICATOR], status: [] }])
  mockApi('get', '/overview/combined', [
    {
      ...makeEvolution('combined.online_procedures_per_actor', 0.5, null, { previous_value: 0.4 }),
      dashboard_keys: ['procedures', 'economic'],
    },
  ])
  renderOverview()

  const combined = await screen.findByRole('region', { name: t('overview.combined.title') })
  const label = t('overview.indicators.combined.online_procedures_per_actor')
  expect(within(combined).getByText(label)).toBeInTheDocument()
  expect(within(combined).getByText('0,5')).toBeInTheDocument()
  expect(within(combined).queryByText(t('indicators.noTarget'))).not.toBeInTheDocument()
  // Like every card, it says what it measures.
  expect(
    within(combined).getByRole('button', { name: t('help.about', { column: label }) }),
  ).toBeInTheDocument()
  const lights = screen.getByRole('region', { name: t('overview.lights') })
  expect(lights.compareDocumentPosition(combined) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

it('leaves the combined indicators out when the member sees none', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [INDICATOR], status: [] }])
  const combined = mockApi('get', '/overview/combined', [])
  renderOverview()

  await screen.findByRole('heading', { name: t('projects.title') })
  await waitFor(() => expect(combined).toHaveLength(1))
  expect(
    screen.queryByRole('region', { name: t('overview.combined.title') }),
  ).not.toBeInTheDocument()
})

describe('choosing which dashboards to show', () => {
  const name = (key: string) => t(`${key}.title`)
  const hide = (key: string) => t('overview.hide', { name: name(key) })
  const show = (key: string) => t('overview.show', { name: name(key) })
  const combinedOf = (key: string, dashboardKeys: string[]) => ({
    ...makeEvolution(key, 1),
    dashboard_keys: dashboardKeys,
  })

  function renderThree() {
    mockApi(
      'get',
      '/overview',
      ['projects', 'environment', 'economic'].map((key) => ({
        dashboard_key: key,
        indicators: [INDICATOR],
        status: [],
      })),
    )
    mockApi('get', '/overview/combined', [
      combinedOf('combined.online_procedures_per_actor', ['procedures', 'economic']),
      combinedOf('combined.deliveries_per_active_project', ['social', 'projects']),
    ])
    renderApp(<OverviewPage />, {
      me: makeMe({ dashboards: { projects: 'viewer', environment: 'viewer', economic: 'viewer' } }),
    })
  }

  const lightCards = () =>
    within(screen.getByRole('region', { name: t('overview.lights') }))
      .getAllByRole('group')
      .map((card) => card.getAttribute('aria-label'))
  const sectionToggles = () =>
    ['projects', 'environment', 'economic'].filter((key) =>
      screen.queryByRole('button', { name: name(key), expanded: true }),
    )
  const combinedKeys = () =>
    [...document.querySelectorAll('[data-indicator^="combined."]')].map((card) =>
      card.getAttribute('data-indicator'),
    )

  it('offers one icon per dashboard next to the title, all shown at first', async () => {
    renderThree()

    const toggles = await screen.findByRole('group', { name: t('overview.toggles') })
    expect(
      within(toggles)
        .getAllByRole('button')
        .map((button) => [button.getAttribute('aria-label'), button.getAttribute('aria-pressed')]),
    ).toEqual([
      [hide('projects'), 'true'],
      [hide('environment'), 'true'],
      [hide('economic'), 'true'],
    ])
    expect(
      screen.getByRole('heading', { name: t('overview.title') }).parentElement,
    ).toContainElement(toggles)
  })

  it('names the dashboard and what a click does on hover', async () => {
    renderThree()

    await userEvent.hover(await screen.findByRole('button', { name: hide('economic') }))

    expect(await screen.findByRole('tooltip')).toHaveTextContent(hide('economic'))
  })

  it('hides a dashboard light, section and combined indicators, and shows them again', async () => {
    renderThree()
    await screen.findByRole('region', { name: t('overview.combined.title') })
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: hide('economic') }))

    expect(lightCards()).toEqual([name('projects'), name('environment')])
    expect(sectionToggles()).toEqual(['projects', 'environment'])
    expect(combinedKeys()).toEqual(['combined.deliveries_per_active_project'])
    const toggle = screen.getByRole('button', { name: show('economic') })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')

    await user.click(toggle)

    expect(lightCards()).toEqual([name('projects'), name('environment'), name('economic')])
    expect(sectionToggles()).toEqual(['projects', 'environment', 'economic'])
    expect(combinedKeys()).toEqual([
      'combined.online_procedures_per_actor',
      'combined.deliveries_per_active_project',
    ])
  })

  it('says so when every dashboard is hidden', async () => {
    renderThree()
    const user = userEvent.setup()

    for (const key of ['projects', 'environment', 'economic']) {
      await user.click(await screen.findByRole('button', { name: hide(key) }))
    }

    expect(screen.getByText(t('overview.noneShown'))).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: t('overview.lights') })).not.toBeInTheDocument()
    expect(sectionToggles()).toEqual([])
    expect(combinedKeys()).toEqual([])
  })

  it('shows every dashboard again the next time the page is opened', async () => {
    renderThree()
    await userEvent.click(await screen.findByRole('button', { name: hide('economic') }))
    cleanup()

    renderThree()

    expect(await screen.findByRole('button', { name: hide('economic') })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
