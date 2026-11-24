import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER, SAIRA } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { OperatorPage } from './OperatorPage'

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })

function renderOperator() {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: [] }])
  mockApi('get', '/platform/dashboards', ['projects'])
  return renderApp(<OperatorPage />, { me: OPERATOR })
}

it('creates a municipality', async () => {
  const requests = mockApi(
    'post',
    '/platform/municipalities',
    { ...NOETINGER, dashboards: [] },
    201,
  )
  renderOperator()
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: t('platform.name') }), 'Villa María')
  await user.type(screen.getByRole('textbox', { name: t('platform.slug') }), 'villa-maria')
  await user.selectOptions(
    screen.getByRole('combobox', { name: t('platform.kind') }),
    t('platform.kinds.commune'),
  )
  await user.click(screen.getByRole('button', { name: t('platform.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Villa María',
    slug: 'villa-maria',
    kind: 'commune',
  })
})

it('links each municipality to its configuration', async () => {
  renderOperator()

  const link = await screen.findByRole('link', {
    name: t('platform.configureNamed', { name: NOETINGER.name }),
  })
  expect(link).toHaveAttribute('href', `/platform/municipalities/${NOETINGER.id}`)
})

it('lands operators without a municipality on the platform page', async () => {
  mockApi('get', '/platform/municipalities', [])
  mockApi('get', '/platform/dashboards', ['projects'])
  renderApp(<App />, { me: OPERATOR })

  expect(await screen.findByRole('heading', { name: t('platform.title') })).toBeInTheDocument()
  expect(await screen.findByText(t('platform.empty'))).toBeInTheDocument()
})

it('keeps the platform page away from non-operators', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe(), route: '/platform' })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  // Let the overview finish loading, so no request of this test outlives it.
  expect(await screen.findByText(t('overview.emptyTitle'))).toBeInTheDocument()
})

it('lists the dashboards each municipality has, by name', async () => {
  mockApi('get', '/platform/municipalities', [
    { ...NOETINGER, dashboards: ['projects', 'retired-dashboard'], suspension: null },
  ])
  renderApp(<OperatorPage />, { me: OPERATOR })

  expect(await screen.findByText(`${t('projects.title')}, retired-dashboard`)).toBeInTheDocument()
})

it('shows why a municipality could not be created and lets the message go', async () => {
  mockApiError('post', '/platform/municipalities', 409, 'conflict')
  renderOperator()
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: t('platform.name') }), 'Noetinger')
  await user.type(screen.getByRole('textbox', { name: t('platform.slug') }), 'noetinger')
  await user.click(screen.getByRole('button', { name: t('platform.add') }))
  const message = await screen.findByText(t('errors.conflict'))
  expect(screen.getByRole('textbox', { name: t('platform.name') })).toHaveValue('Noetinger')
  await user.click(within(message.closest('[role="alert"]') as HTMLElement).getByRole('button'))

  await waitFor(() => expect(screen.queryByText(t('errors.conflict'))).not.toBeInTheDocument())
})

it('reports municipalities that cannot be loaded, and an empty platform', async () => {
  mockApiError('get', '/platform/municipalities', 500, 'generic')
  const view = renderApp(<OperatorPage />, { me: OPERATOR })
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  view.unmount()

  mockApi('get', '/platform/municipalities', [])
  renderApp(<OperatorPage />, { me: OPERATOR })
  expect(await screen.findByText(t('platform.empty'))).toBeInTheDocument()
})

it('clears the form once created, and keeps it when the server refuses', async () => {
  renderOperator()
  const user = userEvent.setup()
  const name = await screen.findByRole('textbox', { name: t('platform.name') })
  const slug = screen.getByRole('textbox', { name: t('platform.slug') })
  const create = screen.getByRole('button', { name: t('platform.add') })

  mockApiError('post', '/platform/municipalities', 409, 'conflict')
  await user.type(name, 'Villa María')
  await user.type(slug, 'villa-maria')
  await user.click(create)
  const error = await screen.findByText(t('errors.conflict'))
  expect(name).toHaveValue('Villa María')
  await user.click(within(error.closest('[role="alert"]') as HTMLElement).getByRole('button'))
  expect(screen.queryByText(t('errors.conflict'))).toBeNull()

  mockApi('post', '/platform/municipalities', { ...NOETINGER, dashboards: [] }, 201)
  await user.click(create)
  await waitFor(() => expect(name).toHaveValue(''))
  expect(slug).toHaveValue('')
})

it('lists the dashboards each municipality has, and searches them', async () => {
  mockApi('get', '/platform/municipalities', [
    { ...NOETINGER, dashboards: ['projects', 'social', 'mystery'] },
    { ...SAIRA, dashboards: [] },
  ])
  mockApi('get', '/platform/dashboards', ['projects'])
  renderApp(<OperatorPage />, { me: OPERATOR })
  const user = userEvent.setup()

  const noetinger = within(await screen.findByRole('row', { name: /Noetinger/ }))
  expect(
    noetinger.getByText(`${t('projects.title')}, ${t('social.title')}, mystery`),
  ).toBeInTheDocument()
  expect(
    within(screen.getByRole('row', { name: /Saira/ })).getByText(t('platform.noDashboards')),
  ).toBeInTheDocument()

  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'sai')
  expect(screen.queryByRole('row', { name: /Noetinger/ })).toBeNull()
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'zzz')
  expect(screen.getByText(t('app.noMatches'))).toBeInTheDocument()
})

it('shows an error when the municipalities cannot be loaded', async () => {
  mockApiError('get', '/platform/municipalities', 500, 'generic')
  renderApp(<OperatorPage />, { me: OPERATOR })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
