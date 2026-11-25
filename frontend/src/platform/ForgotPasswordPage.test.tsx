import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

async function ask(email: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(t('passwordReset.email')), email)
  await user.click(screen.getByRole('button', { name: t('passwordReset.submit') }))
}

it('asks for a recovery link and says the same thing whatever the email', async () => {
  const requests = mockApi('post', '/auth/password-reset', null, 204)
  renderApp(<App />, { me: null, route: '/forgot-password' })

  await ask(' ana@noetinger.test ')

  expect(
    await screen.findByText(t('passwordReset.sent', { email: 'ana@noetinger.test' })),
  ).toBeInTheDocument()
  expect(requests[0].body).toEqual({ email: 'ana@noetinger.test' })
  expect(screen.queryByRole('button', { name: t('passwordReset.submit') })).toBeNull()
})

it('asks the person to wait after too many requests', async () => {
  mockApiError('post', '/auth/password-reset', 429, 'too_many_requests')
  renderApp(<App />, { me: null, route: '/forgot-password' })

  await ask('ana@noetinger.test')

  expect(await screen.findByText(t('errors.too_many_requests'))).toBeInTheDocument()
})

it('leads back to the sign-in page', async () => {
  renderApp(<App />, { me: null, route: '/forgot-password' })
  const user = userEvent.setup()

  await user.click(await screen.findByRole('link', { name: t('passwordReset.backToLogin') }))

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
})

it('lets the person try again after a failure, and forgets the failure', async () => {
  mockApiError('post', '/auth/password-reset', 500, 'boom')
  renderApp(<App />, { me: null, route: '/forgot-password' })

  expect(await screen.findByLabelText(t('passwordReset.email'))).toHaveValue('')
  expect(screen.queryByRole('alert')).toBeNull()
  await ask('ana@noetinger.test')
  expect(await screen.findByRole('alert')).toHaveTextContent(t('errors.generic'))

  mockApi('post', '/auth/password-reset', null, 204)
  const button = screen.getByRole('button', { name: t('passwordReset.submit') })
  expect(button).not.toHaveAttribute('data-loading')
  await userEvent.click(button)

  const sent = t('passwordReset.sent', { email: 'ana@noetinger.test' })
  expect(await screen.findByText(sent)).toBeInTheDocument()
  expect(screen.queryByText(t('errors.generic'))).toBeNull()
})
