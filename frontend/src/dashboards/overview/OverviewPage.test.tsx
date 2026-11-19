import { screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
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
    },
  ])
  renderApp(<OverviewPage />, { me: makeMe({ dashboards: { projects: 'viewer' } }) })

  const card = (key: string) =>
    within(screen.getByText(t(`overview.indicators.${key}`)).closest('[data-indicator]')!)

  expect(await screen.findByRole('heading', { name: t('projects.title') })).toBeInTheDocument()
  expect(card('projects.active').getByText('7')).toBeInTheDocument()
  expect(card('projects.average_progress').getByText('42 %')).toBeInTheDocument()
  expect(card('projects.budget_executed_ratio').getByText('25,6 %')).toBeInTheDocument()
  expect(card('projects.milestones_in_alert').getByText('—')).toBeInTheDocument()
})

it('says so when a dashboard has no data yet', async () => {
  mockApi('get', '/overview', [{ dashboard_key: 'projects', indicators: [] }])
  renderApp(<OverviewPage />, { me: makeMe({ dashboards: { projects: 'viewer' } }) })

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
    },
  ])
  renderApp(<OverviewPage />, { me: makeMe({ dashboards: { environment: 'viewer' } }) })

  expect(await screen.findByRole('heading', { name: t('environment.title') })).toBeInTheDocument()
  const cards = document.querySelectorAll('[data-indicator]')
  expect([...cards].map((card) => card.textContent)).toEqual([
    'Variables ambientales12',
    'Cargas del año realizadas24 %',
    'Metas ambientales cumplidas3',
    'Metas ambientales no cumplidas1',
  ])
})
