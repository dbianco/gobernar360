import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it } from 'vitest'

import App from '../App'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError, server } from '../test/server'

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

it('lets the person try again after a failure, without the notice of the one before', async () => {
  mockApiError('post', '/auth/password-reset', 429, 'too_many_requests')
  renderApp(<App />, { me: null, route: '/forgot-password' })
  await ask('ana@noetinger.test')
  expect(await screen.findByText(t('errors.too_many_requests'))).toBeInTheDocument()

  let answer = () => undefined as void
  mockApi('post', '/auth/password-reset', null, 204)
  const waiting = new Promise<void>((resolve) => {
    answer = resolve
  })
  server.use(
    http.post('*/api/auth/password-reset', async () => {
      await waiting
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const button = screen.getByRole('button', { name: t('passwordReset.submit') })
  expect(button).not.toHaveAttribute('data-loading')
  await userEvent.setup().click(button)

  await waitFor(() => expect(button).toHaveAttribute('data-loading', 'true'))
  expect(screen.queryByText(t('errors.too_many_requests'))).toBeNull()
  answer()
  expect(
    await screen.findByText(t('passwordReset.sent', { email: 'ana@noetinger.test' })),
  ).toBeInTheDocument()
})

it('does not leave the page when the form is sent', async () => {
  renderApp(<App />, { me: null, route: '/forgot-password' })
  mockApi('post', '/auth/password-reset', null, 204)
  const field = await screen.findByLabelText(t('passwordReset.email'))
  fireEvent.change(field, { target: { value: 'ana@noetinger.test' } })

  // False when the browser was told not to do it by itself.
  expect(fireEvent.submit(field.closest('form')!)).toBe(false)
  expect(await screen.findByText(/ana@noetinger.test/)).toBeInTheDocument()
})
