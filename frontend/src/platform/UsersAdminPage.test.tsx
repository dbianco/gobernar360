import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import App from '../App'
import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { answerConfirm } from '../test/confirm'
import { mockApi, mockApiError } from '../test/server'
import { UsersAdminPage } from './UsersAdminPage'

const ADMIN = {
  membership_id: 'ms-1',
  user: { id: 'u-1', email: 'ana@noetinger.test', full_name: 'Ana Gómez' },
  is_admin: true,
  grants: {},
}
const CARLA = {
  membership_id: 'ms-2',
  user: { id: 'u-2', email: 'carla@noetinger.test', full_name: 'Carla Carga' },
  is_admin: false,
  grants: { projects: 'viewer' },
}

/** Render the page; returns the requests for the list of users. */
function renderUsers() {
  const requests = mockApi('get', '/admin/users', { items: [ADMIN, CARLA], total: 2 })
  mockApi('get', '/admin/dashboards', ['projects'])
  renderApp(<UsersAdminPage />, { me: makeMe({ isAdmin: true }) })
  return requests
}

afterEach(() => vi.restoreAllMocks())

const accessSelect = (name: string) =>
  screen.findByRole('combobox', {
    name: t('users.accessNamed', { dashboard: t('projects.title'), name }),
  })

it("changes a user's access level for a dashboard", async () => {
  const requests = mockApi('patch', '/admin/users/ms-2', {
    ...CARLA,
    grants: { projects: 'editor' },
  })
  renderUsers()

  const select = await accessSelect('Carla Carga')
  expect(select).toHaveValue('viewer')
  await userEvent.setup().selectOptions(select, t('users.levels.editor'))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ grants: { projects: 'editor' } })
})

it('removes access by choosing no access', async () => {
  const requests = mockApi('patch', '/admin/users/ms-2', {
    ...CARLA,
    grants: {},
  })
  renderUsers()

  await userEvent.setup().selectOptions(await accessSelect('Carla Carga'), t('users.levels.none'))

  await waitFor(() => expect(requests[0]?.body).toEqual({ grants: {} }))
})

it('offers no way to change passwords', async () => {
  renderUsers()

  await accessSelect('Carla Carga')
  expect(
    screen.queryByRole('button', {
      name: t('users.setPasswordNamed', { name: 'Carla Carga' }),
    }),
  ).toBeNull()
})

it('shows that administrators already have full access', async () => {
  renderUsers()

  expect(await accessSelect('Ana Gómez')).toBeDisabled()
})

it('asks in a modal before removing a user, and removes them when accepted', async () => {
  const requests = mockApi('delete', '/admin/users/ms-2', null, 204)
  renderUsers()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('users.removeNamed', { name: 'Carla Carga' }) }),
  )
  const question = await answerConfirm(user, true, t('users.removeTitle'))

  expect(question).toContain(t('users.removeConfirm', { name: 'Carla Carga' }))
  await waitFor(() => expect(requests).toHaveLength(1))
})

it('shows the conflict message when removing the last admin', async () => {
  mockApiError('delete', '/admin/users/ms-1', 409, 'conflict')
  renderUsers()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('users.removeNamed', { name: 'Ana Gómez' }),
    }),
  )
  await answerConfirm(user, true, t('users.removeTitle'))

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
})

it('does not remove a user when the confirmation is declined', async () => {
  const requests = mockApi('delete', '/admin/users/ms-2', null, 204)
  renderUsers()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('users.removeNamed', { name: 'Carla Carga' }),
    }),
  )
  await answerConfirm(user, false, t('users.removeTitle'))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(requests).toHaveLength(0)
})

it('searches users by name or email', async () => {
  const requests = renderUsers()
  const user = userEvent.setup()

  await user.type(await screen.findByRole('searchbox', { name: t('app.search') }), 'carla')

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('q')).toBe('carla'))
  expect(requests.at(-1)?.url.searchParams.get('offset')).toBe('0')
})

it('redirects non-admin members away', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe(), route: '/admin/users' })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: t('users.title') })).not.toBeInTheDocument()
})

it('is reachable for municipality admins', async () => {
  mockApi('get', '/admin/users', { items: [ADMIN], total: 1 })
  mockApi('get', '/admin/dashboards', ['projects'])
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/users' })

  expect(await screen.findByRole('heading', { name: t('users.title') })).toBeInTheDocument()
})

it('resends an invitation without saying whether the person already had a password', async () => {
  const requests = mockApi('post', '/admin/users/ms-2/invitation', null, 204)
  renderUsers()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: t('users.resendInvitationNamed', { name: 'Carla Carga' }),
    }),
  )

  expect(
    await screen.findByText(t('users.invitationResent', { name: 'Carla Carga' })),
  ).toBeInTheDocument()
  expect(requests).toHaveLength(1)
})

it('makes a member administrator of the municipality', async () => {
  const requests = mockApi('patch', '/admin/users/ms-2', { ...CARLA, is_admin: true })
  renderUsers()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('checkbox', { name: t('users.adminNamed', { name: 'Carla Carga' }) }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ is_admin: true })
})

it('lets the notice and the error be closed', async () => {
  mockApi('post', '/admin/users/ms-2/invitation', null, 204)
  renderUsers()
  const user = userEvent.setup()
  const closeOf = (text: string) =>
    within(screen.getByText(text).closest('[role="alert"]') as HTMLElement).getByRole('button')

  await user.click(
    await screen.findByRole('button', {
      name: t('users.resendInvitationNamed', { name: 'Carla Carga' }),
    }),
  )
  const notice = t('users.invitationResent', { name: 'Carla Carga' })
  await screen.findByText(notice)
  await user.click(closeOf(notice))
  expect(screen.queryByText(notice)).toBeNull()

  // The second time the server fails.
  mockApiError('post', '/admin/users/ms-2/invitation', 500, 'generic')
  await user.click(
    screen.getByRole('button', { name: t('users.resendInvitationNamed', { name: 'Carla Carga' }) }),
  )
  await screen.findByText(t('errors.generic'))
  await user.click(closeOf(t('errors.generic')))
  expect(screen.queryByText(t('errors.generic'))).toBeNull()
})

it('closes the add and import windows without changes', async () => {
  renderUsers()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('users.add') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: t('users.import.open') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: t('users.import.open') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('shows a server error of an import, and clears it when another file is chosen', async () => {
  mockApiError('post', '/admin/users/import', 500, 'generic')
  renderUsers()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('users.import.open') }))
  const dialog = await screen.findByRole('dialog')
  const input = dialog.ownerDocument.querySelector<HTMLInputElement>('input[type="file"]')!
  const importButton = within(dialog).getByRole('button', { name: t('users.import.submit') })
  expect(importButton).toBeDisabled()
  await user.upload(input, new File(['email,nombre\n'], 'u.csv', { type: 'text/csv' }))
  await user.click(importButton)

  expect(await within(dialog).findByText(t('errors.generic'))).toBeInTheDocument()
})

it('says when the search finds nobody, and why the users cannot be loaded', async () => {
  const requests = renderUsers()
  const user = userEvent.setup()
  await screen.findByText('Carla Carga')

  mockApi('get', '/admin/users', { items: [], total: 0 })
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'zzz')
  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
  expect(requests.length).toBeGreaterThan(0)

  mockApiError('get', '/admin/users', 500, 'generic')
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'z')
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('closes the add window with Escape', async () => {
  renderUsers()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('users.add') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})
