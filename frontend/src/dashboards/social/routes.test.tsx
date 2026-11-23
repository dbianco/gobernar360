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

function renderDashboard(level: AccessLevel, route = '/d/social') {
  mockParameters()
  mockApi('get', `${BASE}/summary`, makeSummary())
  return renderApp(<App />, { me: makeMe({ dashboards: { social: level } }), route })
}

const tab = (key: string) => screen.queryByRole('tab', { name: t(`social.tabs.${key}`) })

it('shows a viewer every section except the parameters', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('heading', { name: t('social.title') })).toBeInTheDocument()
  for (const key of ['summary', 'people', 'households', 'deliveries', 'interventions', 'reports']) {
    expect(tab(key)).toBeInTheDocument()
  }
  expect(tab('parameters')).toBeNull()
})

it('keeps the parameters from an editor', async () => {
  renderDashboard('editor')

  await screen.findByRole('heading', { name: t('social.title') })
  expect(tab('parameters')).toBeNull()
})

it('shows a dashboard admin the parameters', async () => {
  renderDashboard('admin')

  await screen.findByRole('heading', { name: t('social.title') })
  expect(tab('parameters')).toBeInTheDocument()
})

it('does not open the parameters to an editor who types the address', async () => {
  renderDashboard('editor', '/d/social/parameters')

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
})

it('lists the dashboard in the navigation', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('link', { name: t('social.title') })).toBeInTheDocument()
})

it('moves between the sections with the tabs', async () => {
  renderDashboard('admin')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('tab', { name: t('social.tabs.parameters') }))
  await waitFor(() => expect(tab('parameters')).toHaveAttribute('aria-selected', 'true'))
  await user.click(tab('summary')!)

  await waitFor(() => expect(tab('summary')).toHaveAttribute('aria-selected', 'true'))
})
