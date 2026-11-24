import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it } from 'vitest'

import App from '../App'
import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { AccountPage } from './AccountPage'

// Tests that care about the notification settings answer this themselves.
beforeEach(() => {
  mockApi('get', '/auth/notifications', [])
})

const ME = makeMe()
// The form's fields by the text key of their label; `next` is the new password.
const field = (key: string) =>
  screen.getByLabelText(t(`account.${key === 'next' ? 'new' : key}`), { exact: false })
const updated = (user: Partial<typeof ME.user>) => ({ ...ME, user: { ...ME.user, ...user } })

async function fill(values: {
  fullName?: string
  phone?: string
  next?: string
  current?: string
}) {
  const user = userEvent.setup()
  await screen.findByLabelText(t('account.fullName'), { exact: false })
  for (const [key, value] of Object.entries(values)) {
    await user.clear(field(key))
    if (value) await user.type(field(key), value)
  }
  await user.click(screen.getByRole('button', { name: t('account.submit') }))
}

it("starts from the user's own name and phone", async () => {
  renderApp(<AccountPage />, { me: updated({ phone: '3472 123456' }) })

  expect(await screen.findByLabelText(t('account.fullName'), { exact: false })).toHaveValue(
    'Ana Gómez',
  )
  expect(field('phone')).toHaveValue('3472 123456')
  expect(field('email')).toHaveValue('ana@noetinger.test')
  expect(field('email')).toHaveAttribute('readonly')
  expect(field('new')).toHaveValue('')
})

it('saves the name and phone with the current password, keeping the password', async () => {
  const requests = mockApi('put', '/auth/account', updated({ full_name: 'Ana María Gómez' }))
  renderApp(<AccountPage />, { me: ME })

  await fill({
    fullName: 'Ana María Gómez',
    phone: '+54 9 3472 15-123456',
    current: 'secret-pass-1',
  })

  expect(await screen.findByText(t('account.done'))).toBeInTheDocument()
  expect(requests[0].body).toEqual({
    current_password: 'secret-pass-1',
    full_name: 'Ana María Gómez',
    phone: '+54 9 3472 15-123456',
    new_password: null,
  })
  expect(field('current')).toHaveValue('')
})

it('changes the password along with the rest of the account', async () => {
  const requests = mockApi('put', '/auth/account', ME)
  renderApp(<AccountPage />, { me: ME })

  await fill({ next: 'a-brand-new-password', current: 'secret-pass-1' })

  expect(await screen.findByText(t('account.donePassword'))).toBeInTheDocument()
  expect(requests[0].body).toMatchObject({
    current_password: 'secret-pass-1',
    new_password: 'a-brand-new-password',
  })
  expect(field('new')).toHaveValue('')
})

it('asks for the current password before saving anything', async () => {
  const requests = mockApi('put', '/auth/account', ME)
  renderApp(<AccountPage />, { me: ME })

  await fill({ fullName: 'Otra' })

  expect(field('current')).toBeRequired()
  expect(field('current')).toBeInvalid()
  await new Promise((resolve) => setTimeout(resolve, 50))
  expect(requests).toHaveLength(0)
})

it('says so when the current password is wrong', async () => {
  mockApiError('put', '/auth/account', 403, 'invalid_credentials')
  renderApp(<AccountPage />, { me: ME })

  await fill({ fullName: 'Otra', current: 'wrong' })

  expect(await screen.findByText(t('account.wrongCurrent'))).toBeInTheDocument()
})

it('rejects a new password shorter than ten characters without calling the server', async () => {
  const requests = mockApi('put', '/auth/account', ME)
  renderApp(<AccountPage />, { me: ME })

  await fill({ next: 'short', current: 'secret-pass-1' })

  expect(await screen.findByText(t('users.passwordTooShort'))).toBeInTheDocument()
  await waitFor(() => expect(requests).toHaveLength(0))
})

it('rejects a phone with letters without calling the server', async () => {
  const requests = mockApi('put', '/auth/account', ME)
  renderApp(<AccountPage />, { me: ME })

  await fill({ phone: 'llamar a la tarde', current: 'secret-pass-1' })

  expect(await screen.findByText(t('account.phoneInvalid'))).toBeInTheDocument()
  await waitFor(() => expect(requests).toHaveLength(0))
})

it('shows the new name in the header once saved', async () => {
  mockApi('put', '/auth/account', updated({ full_name: 'Ana María Gómez' }))
  renderApp(<App />, { me: ME, route: '/account' })
  expect(await screen.findByRole('link', { name: 'Ana Gómez' })).toBeInTheDocument()

  await fill({ fullName: 'Ana María Gómez', current: 'secret-pass-1' })

  expect(await screen.findByRole('link', { name: 'Ana María Gómez' })).toBeInTheDocument()
})

it('says why the account could not be saved, and clears the passwords once it is', async () => {
  mockApiError('put', '/auth/account', 429, 'too_many_requests')
  renderApp(<AccountPage />, { me: ME })

  await fill({ next: 'a-brand-new-password', current: 'secret-pass-1' })
  expect(await screen.findByText(t('errors.too_many_requests'))).toBeInTheDocument()

  mockApi('put', '/auth/account', ME)
  await userEvent.setup().click(screen.getByRole('button', { name: t('account.submit') }))
  expect(await screen.findByText(t('account.donePassword'))).toBeInTheDocument()
  expect(screen.queryByText(t('errors.too_many_requests'))).toBeNull()
  expect(field('current')).toHaveValue('')
  expect(field('next')).toHaveValue('')
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
