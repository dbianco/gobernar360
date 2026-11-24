import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import App from '../App'
import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
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

function renderUsers() {
  mockApi('get', '/admin/users', [ADMIN, CARLA])
  mockApi('get', '/admin/dashboards', ['projects'])
  return renderApp(<UsersAdminPage />, { me: makeMe({ isAdmin: true }) })
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

it('shows the conflict message when removing the last admin', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  mockApiError('delete', '/admin/users/ms-1', 409, 'conflict')
  renderUsers()

  await userEvent.setup().click(
    await screen.findByRole('button', {
      name: t('users.removeNamed', { name: 'Ana Gómez' }),
    }),
  )

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
})

it('does not remove a user when the confirmation is declined', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  const requests = mockApi('delete', '/admin/users/ms-2', null, 204)
  renderUsers()

  await userEvent.setup().click(
    await screen.findByRole('button', {
      name: t('users.removeNamed', { name: 'Carla Carga' }),
    }),
  )

  expect(requests).toHaveLength(0)
})

it('redirects non-admin members away', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe(), route: '/admin/users' })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: t('users.title') })).not.toBeInTheDocument()
  // Let the overview finish loading, so no request of this test outlives it.
  expect(await screen.findByText(t('overview.emptyTitle'))).toBeInTheDocument()
})

it('is reachable for municipality admins', async () => {
  mockApi('get', '/admin/users', [ADMIN])
  mockApi('get', '/admin/dashboards', ['projects'])
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/users' })

  expect(await screen.findByRole('heading', { name: t('users.title') })).toBeInTheDocument()
})
