import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../../App'
import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { makeSummary } from './testData'
import { BASE, mockParameters } from './testRender'

function renderDashboard(level: AccessLevel, route = '/d/environment') {
  mockParameters()
  mockApi('get', `${BASE}/summary`, makeSummary())
  return renderApp(<App />, { me: makeMe({ dashboards: { environment: level } }), route })
}

const tab = (key: string) => screen.queryByRole('tab', { name: t(`environment.tabs.${key}`) })

it('shows a viewer only the read-only sections', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('heading', { name: t('environment.title') })).toBeInTheDocument()
  expect(tab('summary')).toBeInTheDocument()
  expect(tab('tracking')).toBeInTheDocument()
  expect(tab('entry')).toBeNull()
  expect(tab('parameters')).toBeNull()
})

it('shows an editor the data entry section but not the parameters', async () => {
  renderDashboard('editor')

  await screen.findByRole('heading', { name: t('environment.title') })
  expect(tab('entry')).toBeInTheDocument()
  expect(tab('parameters')).toBeNull()
})

it('shows a dashboard admin every section', async () => {
  renderDashboard('admin')

  await screen.findByRole('heading', { name: t('environment.title') })
  expect(tab('entry')).toBeInTheDocument()
  expect(tab('parameters')).toBeInTheDocument()
})

it('does not open the parameters to an editor who types the address', async () => {
  renderDashboard('editor', '/d/environment/parameters')

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
})

it('lists the dashboard in the navigation', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('link', { name: t('environment.title') })).toBeInTheDocument()
})

it('moves between the sections with the tabs', async () => {
  renderDashboard('admin')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('tab', { name: t('environment.tabs.parameters') }))
  await waitFor(() => expect(tab('parameters')).toHaveAttribute('aria-selected', 'true'))
  await user.click(tab('summary')!)

  await waitFor(() => expect(tab('summary')).toHaveAttribute('aria-selected', 'true'))
})
