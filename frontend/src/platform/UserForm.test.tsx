import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi } from '../test/server'
import { UserForm } from './UserForm'

async function fill(user: ReturnType<typeof userEvent.setup>, password: string) {
  await user.type(screen.getByRole('textbox', { name: t('users.name') }), 'Carla Carga')
  await user.type(screen.getByRole('textbox', { name: t('users.email') }), 'carla@noetinger.test')
  await user.type(screen.getByLabelText(t('users.password'), { exact: false }), password)
}

it('rejects passwords shorter than ten characters', async () => {
  const requests = mockApi('post', '/admin/users', {}, 201)
  renderApp(<UserForm base="/admin" dashboards={['projects']} onDone={vi.fn()} />, { me: makeMe() })
  const user = userEvent.setup()

  await fill(user, 'short')
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  expect(await screen.findByText(t('users.passwordTooShort'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})

it('creates a user with the chosen access', async () => {
  const requests = mockApi('post', '/admin/users', {}, 201)
  const onDone = vi.fn()
  renderApp(<UserForm base="/admin" dashboards={['projects']} onDone={onDone} />, { me: makeMe() })
  const user = userEvent.setup()

  await fill(user, 'long-password-1')
  await user.selectOptions(
    screen.getByRole('combobox', {
      name: t('users.accessTo', { dashboard: t('projects.title') }),
    }),
    t('users.levels.editor'),
  )
  await user.click(screen.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(onDone).toHaveBeenCalled())
  expect(requests[0].body).toEqual({
    email: 'carla@noetinger.test',
    full_name: 'Carla Carga',
    password: 'long-password-1',
    is_admin: false,
    grants: { projects: 'editor' },
  })
})
