import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

const INVITATION = { purpose: 'invitation', email: 'carla@noetinger.test', full_name: 'Carla' }

async function choose(password: string, confirmation = password) {
  const user = userEvent.setup()
  const first = await screen.findByLabelText(t('setPassword.password'), { exact: false })
  const second = screen.getByLabelText(t('setPassword.confirm'), { exact: false })
  await user.clear(first)
  await user.type(first, password)
  await user.clear(second)
  await user.type(second, confirmation)
  await user.click(screen.getByRole('button', { name: t('setPassword.submit') }))
}

it('welcomes an invited person and, once they choose a password, sends them to sign in', async () => {
  const inspected = mockApi('post', '/auth/tokens/inspect', INVITATION)
  const redeemed = mockApi('post', '/auth/tokens/redeem', null, 204)
  renderApp(<App />, { me: null, route: '/set-password#the-token' })

  expect(
    await screen.findByRole('heading', { name: t('setPassword.invitationTitle') }),
  ).toBeInTheDocument()
  expect(
    screen.getByText(t('setPassword.invitationIntro', { name: 'Carla', email: INVITATION.email })),
  ).toBeInTheDocument()
  await choose('a-good-password')

  expect(await screen.findByText(t('login.passwordSet'))).toBeInTheDocument()
  expect(screen.getByLabelText(t('login.email'))).toHaveValue('carla@noetinger.test')
  expect(inspected[0].body).toEqual({ token: 'the-token' })
  expect(redeemed[0].body).toEqual({ token: 'the-token', password: 'a-good-password' })
})

it('tells a person recovering their password that other sessions will close', async () => {
  mockApi('post', '/auth/tokens/inspect', { ...INVITATION, purpose: 'password_reset' })
  renderApp(<App />, { me: null, route: '/set-password#the-token' })

  expect(
    await screen.findByRole('heading', { name: t('setPassword.resetTitle') }),
  ).toBeInTheDocument()
  expect(
    screen.getByText(t('setPassword.resetIntro', { email: INVITATION.email })),
  ).toBeInTheDocument()
})

it('says a used or expired link is no longer valid and offers a new one', async () => {
  mockApiError('post', '/auth/tokens/inspect', 410, 'invalid_token')
  renderApp(<App />, { me: null, route: '/set-password#used-token' })

  expect(
    await screen.findByRole('heading', { name: t('setPassword.invalidTitle') }),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('setPassword.requestNew') })).toHaveAttribute(
    'href',
    '/forgot-password',
  )
  expect(screen.queryByLabelText(t('setPassword.password'), { exact: false })).toBeNull()
})

it('treats a link without a token as not valid', async () => {
  renderApp(<App />, { me: null, route: '/set-password' })

  expect(
    await screen.findByRole('heading', { name: t('setPassword.invalidTitle') }),
  ).toBeInTheDocument()
})

it('checks the password length and the confirmation before sending', async () => {
  mockApi('post', '/auth/tokens/inspect', INVITATION)
  const redeemed = mockApi('post', '/auth/tokens/redeem', null, 204)
  renderApp(<App />, { me: null, route: '/set-password#the-token' })

  await choose('short')
  expect(await screen.findByText(t('users.passwordTooShort'))).toBeInTheDocument()

  await choose('a-good-password', 'another-password')
  expect(await screen.findByText(t('setPassword.mismatch'))).toBeInTheDocument()
  await waitFor(() => expect(redeemed).toHaveLength(0))
})

it('shows the link as not valid when it was used in the meantime', async () => {
  mockApi('post', '/auth/tokens/inspect', INVITATION)
  mockApiError('post', '/auth/tokens/redeem', 410, 'invalid_token')
  renderApp(<App />, { me: null, route: '/set-password#the-token' })
  await screen.findByRole('heading', { name: t('setPassword.invitationTitle') })
  mockApiError('post', '/auth/tokens/inspect', 410, 'invalid_token')

  await choose('a-good-password')

  expect(
    await screen.findByRole('heading', { name: t('setPassword.invalidTitle') }),
  ).toBeInTheDocument()
})

it('says why the password could not be set, keeping the form', async () => {
  mockApi('post', '/auth/tokens/inspect', INVITATION)
  mockApiError('post', '/auth/tokens/redeem', 429, 'too_many_requests')
  renderApp(<App />, { me: null, route: '/set-password#the-token' })

  await choose('a-good-password')

  expect(await screen.findByText(t('errors.too_many_requests'))).toBeInTheDocument()
  expect(screen.getByRole('button', { name: t('setPassword.submit') })).toBeEnabled()
})

it('says why the link could not be checked', async () => {
  mockApiError('post', '/auth/tokens/inspect', 500, 'generic')
  renderApp(<App />, { me: null, route: '/set-password#the-token' })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: t('setPassword.invalidTitle') })).toBeNull()
})
