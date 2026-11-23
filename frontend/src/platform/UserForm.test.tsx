import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { UserForm } from './UserForm'

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox', { name: t('users.name') }), 'Carla Carga')
  await user.type(screen.getByRole('textbox', { name: t('users.email') }), 'carla@noetinger.test')
}

it('asks for no password: the person is invited by email', async () => {
  renderApp(<UserForm base="/admin" dashboards={['projects']} onDone={vi.fn()} />, { me: makeMe() })

  expect(await screen.findByText(t('users.inviteHint'))).toBeInTheDocument()
  expect(document.querySelector('input[type="password"]')).toBeNull()
})

it('creates a user with the chosen access', async () => {
  const requests = mockApi('post', '/admin/users', {}, 201)
  const onDone = vi.fn()
  renderApp(<UserForm base="/admin" dashboards={['projects']} onDone={onDone} />, { me: makeMe() })
  const user = userEvent.setup()

  await fill(user)
  await user.selectOptions(
    screen.getByRole('combobox', {
      name: t('users.accessTo', { dashboard: t('projects.title') }),
    }),
    t('users.levels.editor'),
  )
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onDone).toHaveBeenCalledWith('carla@noetinger.test'))
  expect(requests[0].body).toEqual({
    email: 'carla@noetinger.test',
    full_name: 'Carla Carga',
    is_admin: false,
    grants: { projects: 'editor' },
  })
})

it('shows why a user could not be added', async () => {
  mockApiError('post', '/admin/users', 409, 'conflict')
  const onDone = vi.fn()
  renderApp(<UserForm base="/admin" dashboards={['projects']} onDone={onDone} />, { me: makeMe() })
  const user = userEvent.setup()

  await fill(user)
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(onDone).not.toHaveBeenCalled()
})

it('drops an access chosen and then taken back, and trims what was typed', async () => {
  const requests = mockApi('post', '/admin/users', {}, 201)
  const onDone = vi.fn()
  renderApp(<UserForm base="/admin" dashboards={['projects', 'social']} onDone={onDone} />, {
    me: makeMe(),
  })
  const user = userEvent.setup()
  const access = (dashboard: string) =>
    screen.getByRole('combobox', { name: t('users.accessTo', { dashboard: t(dashboard) }) })

  await user.type(screen.getByRole('textbox', { name: t('users.name') }), '  Carla Carga ')
  await user.type(screen.getByRole('textbox', { name: t('users.email') }), ' carla@noetinger.test ')
  await user.selectOptions(access('projects.title'), t('users.levels.editor'))
  await user.selectOptions(access('social.title'), t('users.levels.viewer'))
  await user.selectOptions(access('projects.title'), t('users.levels.none'))
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onDone).toHaveBeenCalledWith('carla@noetinger.test'))
  expect(requests[0].body).toEqual({
    email: 'carla@noetinger.test',
    full_name: 'Carla Carga',
    is_admin: false,
    grants: { social: 'viewer' },
  })
})

it('gives an administrator no separate access, sending none', async () => {
  const requests = mockApi('post', '/platform/municipalities/m-1/users', {}, 201)
  renderApp(
    <UserForm base="/platform/municipalities/m-1" dashboards={['projects']} onDone={vi.fn()} />,
    { me: makeMe() },
  )
  const user = userEvent.setup()

  await fill(user)
  await user.selectOptions(
    screen.getByRole('combobox', { name: t('users.accessTo', { dashboard: t('projects.title') }) }),
    t('users.levels.editor'),
  )
  await user.click(screen.getByRole('checkbox', { name: t('users.admin') }))
  expect(screen.queryByRole('combobox')).toBeNull()
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ is_admin: true, grants: {} })
})

it('names a dashboard it has no words for by its key, and can be cancelled', async () => {
  const onCancel = vi.fn()
  renderApp(
    <UserForm base="/admin" dashboards={['mystery']} onDone={vi.fn()} onCancel={onCancel} />,
    { me: makeMe() },
  )

  expect(
    screen.getByRole('combobox', { name: t('users.accessTo', { dashboard: 'mystery' }) }),
  ).toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: t('app.cancel') }))
  expect(onCancel).toHaveBeenCalled()
})

it('offers no cancel button when there is nowhere to go back to', () => {
  renderApp(<UserForm base="/admin" dashboards={[]} onDone={vi.fn()} />, { me: makeMe() })

  expect(screen.queryByRole('button', { name: t('app.cancel') })).toBeNull()
})
