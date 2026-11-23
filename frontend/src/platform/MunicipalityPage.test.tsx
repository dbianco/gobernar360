import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })
const BASE = `/platform/municipalities/${NOETINGER.id}`
const ADMIN = {
  membership_id: 'ms-1',
  user: { id: 'u-5', email: 'admin@noetinger.test', full_name: 'Ana Admin' },
  is_admin: true,
  grants: {},
}
const CARLA = {
  membership_id: 'ms-2',
  user: { id: 'u-6', email: 'carla@noetinger.test', full_name: 'Carla Carga' },
  is_admin: false,
  grants: { projects: 'viewer' },
}

function renderPage(options: { me?: ReturnType<typeof makeMe>; id?: string } = {}) {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: ['projects'] }])
  mockApi('get', '/platform/dashboards', ['environment', 'projects'])
  mockApi('get', `${BASE}/users`, { items: [ADMIN, CARLA], total: 2 })
  mockApi('get', `${BASE}/dashboards`, ['projects'])
  return renderApp(<App />, {
    me: options.me ?? OPERATOR,
    route: `/platform/municipalities/${options.id ?? NOETINGER.id}`,
  })
}

it('renames the municipality', async () => {
  const requests = mockApi('patch', BASE, {
    ...NOETINGER,
    dashboards: ['projects'],
  })
  renderPage()
  const user = userEvent.setup()

  const name = await screen.findByRole('textbox', { name: t('platform.name') })
  expect(name).toHaveValue('Noetinger')
  await user.clear(name)
  await user.type(name, 'Noetinger Nuevo')
  await user.click(screen.getByRole('button', { name: t('platform.saveDetails') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Noetinger Nuevo',
    kind: 'municipality',
  })
  expect(await screen.findByText(t('platform.detailsSaved'))).toBeInTheDocument()
})

it('enables a dashboard', async () => {
  const requests = mockApi('put', `${BASE}/dashboards`, {
    ...NOETINGER,
    dashboards: ['environment', 'projects'],
  })
  renderPage()

  const checkbox = await screen.findByRole('checkbox', {
    name: t('environment.title'),
  })
  expect(checkbox).not.toBeChecked()
  expect(screen.getByRole('checkbox', { name: t('projects.title') })).toBeChecked()
  await userEvent.setup().click(checkbox)

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ keys: ['projects', 'environment'] })
})

it('lists the users of the municipality and changes a level', async () => {
  const requests = mockApi('patch', `${BASE}/users/ms-2`, CARLA)
  renderPage()

  const select = await screen.findByRole('combobox', {
    name: t('users.accessNamed', {
      dashboard: t('projects.title'),
      name: 'Carla Carga',
    }),
  })
  expect(select).toHaveValue('viewer')
  await userEvent.setup().selectOptions(select, t('users.levels.editor'))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ grants: { projects: 'editor' } })
})

it('adds an administrator, who is invited by email', async () => {
  const requests = mockApi('post', `${BASE}/users`, ADMIN, 201)
  renderPage()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('users.add') }))
  const dialog = await screen.findByRole('dialog')
  await user.type(within(dialog).getByRole('textbox', { name: t('users.name') }), 'Inés Intendenta')
  await user.type(
    within(dialog).getByRole('textbox', { name: t('users.email') }),
    'ines@noetinger.test',
  )
  await user.click(within(dialog).getByRole('checkbox', { name: t('users.admin') }))
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    email: 'ines@noetinger.test',
    full_name: 'Inés Intendenta',
    is_admin: true,
    grants: {},
  })
  expect(
    await screen.findByText(t('users.invited', { email: 'ines@noetinger.test' })),
  ).toBeInTheDocument()
})

async function openPasswordDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole('button', {
      name: t('users.setPasswordNamed', { name: 'Carla Carga' }),
    }),
  )
  return screen.findByRole('dialog')
}

it('sets a new password for a user', async () => {
  const requests = mockApi('put', `${BASE}/users/ms-2/password`, null, 204)
  renderPage()
  const user = userEvent.setup()

  const dialog = await openPasswordDialog(user)
  await user.type(
    within(dialog).getByLabelText(t('users.newPassword'), { exact: false }),
    'long-password-2',
  )
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ password: 'long-password-2' })
  expect(
    await screen.findByText(t('users.passwordChanged', { name: 'Carla Carga' })),
  ).toBeInTheDocument()
})

it('rejects a short new password without calling the server', async () => {
  const requests = mockApi('put', `${BASE}/users/ms-2/password`, null, 204)
  renderPage()
  const user = userEvent.setup()

  const dialog = await openPasswordDialog(user)
  await user.type(within(dialog).getByLabelText(t('users.newPassword'), { exact: false }), 'short')
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))

  expect(await within(dialog).findByText(t('users.passwordTooShort'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})

it('says so when the municipality does not exist', async () => {
  renderPage({ id: 'missing' })

  expect(await screen.findByText(t('platform.notFound'))).toBeInTheDocument()
})

it('keeps the page away from non-operators', async () => {
  mockApi('get', '/overview', [])
  renderPage({ me: makeMe({ isAdmin: true }) })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
})

it('changes the kind, and says the details were saved', async () => {
  const requests = mockApi('patch', BASE, { ...NOETINGER, kind: 'commune', dashboards: [] })
  renderPage()
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByRole('combobox', { name: t('platform.kind') }),
    t('platform.kinds.commune'),
  )
  await user.click(screen.getByRole('button', { name: t('platform.saveDetails') }))

  expect(await screen.findByText(t('platform.detailsSaved'))).toBeInTheDocument()
  expect(requests[0].body).toEqual({ name: 'Noetinger', kind: 'commune' })
})

it('does not save a blank name, and shows why a save failed', async () => {
  const requests = mockApiError('patch', BASE, 422, 'validation_error')
  renderPage()
  const user = userEvent.setup()
  const name = await screen.findByRole('textbox', { name: t('platform.name') })

  await user.clear(name)
  await user.type(name, '   ')
  await user.click(screen.getByRole('button', { name: t('platform.saveDetails') }))
  expect(requests).toHaveLength(0)

  await user.type(name, 'Noetinger Sur')
  await user.click(screen.getByRole('button', { name: t('platform.saveDetails') }))
  expect(await screen.findByText(t('errors.validation_error'))).toBeInTheDocument()
  expect(screen.queryByText(t('platform.detailsSaved'))).toBeNull()
})

it('turns a dashboard off, and shows why a change failed', async () => {
  const requests = mockApiError('put', `${BASE}/dashboards`, 422, 'validation_error')
  renderPage()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('checkbox', { name: t('projects.title') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ keys: [] })
  expect(await screen.findByText(t('errors.validation_error'))).toBeInTheDocument()
})

it('names a dashboard this version does not know by its key', async () => {
  mockApi('get', '/platform/dashboards', ['projects', 'mystery'])
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: ['projects'] }])
  mockApi('get', `${BASE}/users`, { items: [], total: 0 })
  mockApi('get', `${BASE}/dashboards`, ['projects'])
  renderApp(<App />, { me: OPERATOR, route: `/platform/municipalities/${NOETINGER.id}` })

  expect(await screen.findByRole('checkbox', { name: 'mystery' })).not.toBeChecked()
})

it('shows an error when the municipalities cannot be loaded', async () => {
  mockApiError('get', '/platform/municipalities', 500, 'generic')
  mockApi('get', '/platform/dashboards', [])
  renderApp(<App />, { me: OPERATOR, route: `/platform/municipalities/${NOETINGER.id}` })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('keeps the password form open when the server refuses, and closes it with Escape', async () => {
  mockApiError('put', `${BASE}/users/ms-2/password`, 422, 'validation_error')
  renderPage()
  const user = userEvent.setup()

  const dialog = await openPasswordDialog(user)
  await user.type(
    within(dialog).getByLabelText(t('users.newPassword'), { exact: false }),
    'long-password-2',
  )
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))
  expect(await within(dialog).findByText(t('errors.validation_error'))).toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('names the access column of a dashboard this version does not know by its key', async () => {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: ['projects'] }])
  mockApi('get', '/platform/dashboards', ['projects'])
  mockApi('get', `${BASE}/users`, { items: [CARLA], total: 1 })
  mockApi('get', `${BASE}/dashboards`, ['projects', 'mystery'])
  renderApp(<App />, { me: OPERATOR, route: `/platform/municipalities/${NOETINGER.id}` })

  expect(await screen.findByRole('columnheader', { name: 'mystery' })).toBeInTheDocument()
})

it('links to the configuration of the municipality', async () => {
  renderPage()

  expect(await screen.findByRole('link', { name: t('platform.settings') })).toHaveAttribute(
    'href',
    `/platform/municipalities/${NOETINGER.id}/settings`,
  )
})
