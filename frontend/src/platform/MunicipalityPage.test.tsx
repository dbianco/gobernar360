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
  mockApi('get', `${BASE}/users`, [ADMIN, CARLA])
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

it('adds an administrator', async () => {
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
  await user.type(
    within(dialog).getByLabelText(t('users.password'), { exact: false }),
    'long-password-1',
  )
  await user.click(within(dialog).getByRole('checkbox', { name: t('users.admin') }))
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    email: 'ines@noetinger.test',
    full_name: 'Inés Intendenta',
    password: 'long-password-1',
    is_admin: true,
    grants: {},
  })
})

async function submitExistingAccount(user: ReturnType<typeof userEvent.setup>) {
  mockApiError('post', `${BASE}/users`, 409, 'account_exists')
  renderPage()
  await user.click(await screen.findByRole('button', { name: t('users.add') }))
  const dialog = await screen.findByRole('dialog')
  await user.type(within(dialog).getByRole('textbox', { name: t('users.name') }), 'Otra Persona')
  await user.type(
    within(dialog).getByRole('textbox', { name: t('users.email') }),
    'otra@saira.test',
  )
  await user.type(
    within(dialog).getByLabelText(t('users.password'), { exact: false }),
    'long-password-1',
  )
  await user.click(within(dialog).getByRole('button', { name: t('app.save') }))
  await within(dialog).findByText(t('users.accountExists'))
  return dialog
}

it.each([
  ['keepPassword', 'keep_password'],
  ['replacePassword', 'replace_password'],
])('asks what to do with an account that already exists: %s', async (button, choice) => {
  const user = userEvent.setup()
  const dialog = await submitExistingAccount(user)
  const requests = mockApi('post', `${BASE}/users`, CARLA, 201)

  await user.click(within(dialog).getByRole('button', { name: t(`users.${button}`) }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    email: 'otra@saira.test',
    full_name: 'Otra Persona',
    password: 'long-password-1',
    is_admin: false,
    grants: {},
    existing_account: choice,
  })
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
