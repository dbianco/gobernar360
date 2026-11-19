import { screen } from '@testing-library/react'
import { expect, it } from 'vitest'

import App from '../../App'
import type { AccessLevel } from '../../platform/types'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { makeSummary } from './testData'
import { BASE, mockParameters } from './testRender'

function renderDashboard(level: AccessLevel, route = '/d/economic') {
  mockParameters()
  mockApi('get', `${BASE}/summary`, makeSummary())
  return renderApp(<App />, { me: makeMe({ dashboards: { economic: level } }), route })
}

const tab = (key: string) => screen.queryByRole('tab', { name: t(`economic.tabs.${key}`) })

it('shows a viewer every section except the parameters', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('heading', { name: t('economic.title') })).toBeInTheDocument()
  for (const key of ['summary', 'actors', 'people', 'assignments', 'reports']) {
    expect(tab(key)).toBeInTheDocument()
  }
  expect(tab('parameters')).toBeNull()
})

it('keeps the parameters from an editor', async () => {
  renderDashboard('editor')

  await screen.findByRole('heading', { name: t('economic.title') })
  expect(tab('parameters')).toBeNull()
})

it('shows a dashboard admin the parameters', async () => {
  renderDashboard('admin')

  await screen.findByRole('heading', { name: t('economic.title') })
  expect(tab('parameters')).toBeInTheDocument()
})

it('does not open the parameters to an editor who types the address', async () => {
  renderDashboard('editor', '/d/economic/parameters')

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
})

it('lists the dashboard in the navigation', async () => {
  renderDashboard('viewer')

  expect(await screen.findByRole('link', { name: t('economic.title') })).toBeInTheDocument()
})
