import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { AccountPage } from './AccountPage'

// Tests that care about the notification settings answer this themselves.
beforeEach(() => {
  mockApi('get', '/auth/notifications', [])
})

async function submit(current: string, next: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(t('account.current'), { exact: false }), current)
  await user.type(screen.getByLabelText(t('account.new'), { exact: false }), next)
  await user.click(screen.getByRole('button', { name: t('account.submit') }))
}

it('changes the password', async () => {
  const requests = mockApi('post', '/auth/password', null, 204)
  renderApp(<AccountPage />, { me: makeMe() })

  await submit('secret-pass-1', 'a-brand-new-password')

  expect(await screen.findByText(t('account.done'))).toBeInTheDocument()
  expect(requests[0].body).toEqual({
    current_password: 'secret-pass-1',
    new_password: 'a-brand-new-password',
  })
})

it('says so when the current password is wrong', async () => {
  mockApiError('post', '/auth/password', 403, 'invalid_credentials')
  renderApp(<AccountPage />, { me: makeMe() })

  await submit('wrong', 'a-brand-new-password')

  expect(await screen.findByText(t('account.wrongCurrent'))).toBeInTheDocument()
})

it('rejects a new password shorter than ten characters without calling the server', async () => {
  const requests = mockApi('post', '/auth/password', null, 204)
  renderApp(<AccountPage />, { me: makeMe() })

  await submit('secret-pass-1', 'short')

  expect(await screen.findByText(t('users.passwordTooShort'))).toBeInTheDocument()
  await waitFor(() => expect(requests).toHaveLength(0))
})

// The label, whether or not the description is read out with it.
const switchNamed = (kind: string) => {
  const label = t(`account.notifications.kinds.${kind}.label`)
  return screen.findByRole('switch', { name: (name) => name.startsWith(label) })
}

const SETTINGS = [
  { kind: 'status_light_missing', enabled: true },
  { kind: 'milestone_overdue', enabled: false },
]

it('shows each kind of email notification and whether it is on', async () => {
  mockApi('get', '/auth/notifications', SETTINGS)
  renderApp(<AccountPage />, { me: makeMe() })

  const missing = await switchNamed('status_light_missing')
  const overdue = await switchNamed('milestone_overdue')

  expect(missing).toBeChecked()
  expect(overdue).not.toBeChecked()
  expect(
    screen.getByText(t('account.notifications.hint', { email: 'ana@noetinger.test' })),
  ).toBeInTheDocument()
})

it('turns a kind of notification off', async () => {
  mockApi('get', '/auth/notifications', SETTINGS)
  const requests = mockApi('put', '/auth/notifications/status_light_missing', {
    kind: 'status_light_missing',
    enabled: false,
  })
  renderApp(<AccountPage />, { me: makeMe() })
  const user = userEvent.setup()

  await user.click(await switchNamed('status_light_missing'))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ enabled: false })
})

it('says why the password could not be changed, and clears the fields once it is', async () => {
  mockApiError('post', '/auth/password', 429, 'too_many_requests')
  renderApp(<AccountPage />, { me: makeMe() })

  await submit('secret-pass-1', 'a-brand-new-password')
  expect(await screen.findByText(t('errors.too_many_requests'))).toBeInTheDocument()

  mockApi('post', '/auth/password', null, 204)
  await userEvent.setup().click(screen.getByRole('button', { name: t('account.submit') }))
  expect(await screen.findByText(t('account.done'))).toBeInTheDocument()
  expect(screen.queryByText(t('errors.too_many_requests'))).toBeNull()
  expect(screen.getByLabelText(t('account.current'), { exact: false })).toHaveValue('')
  expect(screen.getByLabelText(t('account.new'), { exact: false })).toHaveValue('')
})

it('says why a notification could not be changed, and lets the message be closed', async () => {
  mockApi('get', '/auth/notifications', SETTINGS)
  mockApiError('put', '/auth/notifications/milestone_overdue', 500, 'generic')
  renderApp(<AccountPage />, { me: makeMe() })
  const user = userEvent.setup()

  await user.click(await switchNamed('milestone_overdue'))
  const message = await screen.findByText(t('errors.generic'))
  await user.click(
    within(message.closest('[role="alert"]') as HTMLElement).getByRole('button'),
  )

  expect(screen.queryByText(t('errors.generic'))).toBeNull()
})

it('says why the notifications cannot be loaded', async () => {
  mockApiError('get', '/auth/notifications', 500, 'generic')
  renderApp(<AccountPage />, { me: makeMe() })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('names a kind of notification it has no words for by its key', async () => {
  mockApi('get', '/auth/notifications', [{ kind: 'weekly_digest', enabled: true }])
  renderApp(<AccountPage />, { me: makeMe() })

  expect(await screen.findByRole('switch', { name: 'weekly_digest' })).toBeChecked()
})
