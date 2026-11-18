import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi } from '../test/server'
import { OperatorPage } from './OperatorPage'

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })

function renderOperator() {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: [] }])
  mockApi('get', '/platform/dashboards', ['projects'])
  return renderApp(<OperatorPage />, { me: OPERATOR })
}

it('creates a municipality', async () => {
  const requests = mockApi('post', '/platform/municipalities', { ...NOETINGER, dashboards: [] }, 201)
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
  expect(requests[0].body).toEqual({ name: 'Villa María', slug: 'villa-maria', kind: 'commune' })
})

it('enables a dashboard for a municipality', async () => {
  const requests = mockApi('put', `/platform/municipalities/${NOETINGER.id}/dashboards`, {
    ...NOETINGER,
    dashboards: ['projects'],
  })
  renderOperator()

  const checkbox = await screen.findByRole('checkbox', {
    name: t('platform.dashboardIn', { dashboard: t('projects.title'), name: NOETINGER.name }),
  })
  expect(checkbox).not.toBeChecked()
  await userEvent.setup().click(checkbox)

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ keys: ['projects'] })
})

it('creates the first administrator of a municipality', async () => {
  const requests = mockApi(
    'post',
    `/platform/municipalities/${NOETINGER.id}/admins`,
    { id: 'u-9', email: 'admin@noetinger.test', full_name: 'Ana Admin', is_platform_operator: false },
    201,
  )
  renderOperator()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('platform.createAdminFor', { name: NOETINGER.name }),
    }),
  )
  await user.type(await screen.findByRole('textbox', { name: t('users.name') }), 'Ana Admin')
  await user.type(screen.getByRole('textbox', { name: t('users.email') }), 'admin@noetinger.test')
  await user.type(screen.getByLabelText(t('users.password'), { exact: false }), 'long-password-1')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    email: 'admin@noetinger.test',
    full_name: 'Ana Admin',
    password: 'long-password-1',
  })
  expect(
    await screen.findByText(t('platform.adminCreated', { email: 'admin@noetinger.test' })),
  ).toBeInTheDocument()
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
})
