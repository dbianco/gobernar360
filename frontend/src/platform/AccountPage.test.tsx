import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { AccountPage } from './AccountPage'

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
