import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

async function signIn() {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(t('login.email')), 'ana@noetinger.test')
  await user.type(screen.getByLabelText(t('login.password')), 'secret-pass-1')
  await user.click(screen.getByRole('button', { name: t('login.submit') }))
}

it('sends signed-out visitors to the login page', async () => {
  renderApp(<App />, { me: null })

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
})

it('shows an error message when credentials are rejected', async () => {
  mockApiError('post', '/auth/login', 401, 'invalid_credentials')
  renderApp(<App />, { me: null, route: '/login' })

  await signIn()

  expect(await screen.findByText(t('errors.invalid_credentials'))).toBeInTheDocument()
})

it('redirects to the overview after a successful login', async () => {
  const me = makeMe()
  const requests = mockApi('post', '/auth/login', me)
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: null, route: '/login' })

  await signIn()

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(requests[0].body).toEqual({ email: 'ana@noetinger.test', password: 'secret-pass-1' })
})
