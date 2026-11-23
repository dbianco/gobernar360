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

it('offers single sign-on only when the server has it configured', async () => {
  mockApi('get', '/auth/sso', { enabled: true })
  renderApp(<App />, { me: null, route: '/login' })

  const button = await screen.findByRole('link', { name: t('login.sso') })

  expect(button).toHaveAttribute('href', '/api/auth/sso/start')
})

it('does not offer single sign-on when it is off', async () => {
  renderApp(<App />, { me: null, route: '/login' })

  await screen.findByRole('heading', { name: t('login.title') })

  expect(screen.queryByRole('link', { name: t('login.sso') })).toBeNull()
})

it.each(['no_account', 'unverified_email', 'failed'])(
  'explains why single sign-on did not sign the person in: %s',
  async (code) => {
    renderApp(<App />, { me: null, route: `/login?sso_error=${code}` })

    expect(await screen.findByText(t(`login.ssoErrors.${code}`))).toBeInTheDocument()
  },
)

it('leads to password recovery, keeping the email typed so far', async () => {
  renderApp(<App />, { me: null, route: '/login' })
  const user = userEvent.setup()

  await user.type(await screen.findByLabelText(t('login.email')), 'ana@noetinger.test')
  await user.click(screen.getByRole('link', { name: t('login.forgot') }))

  expect(await screen.findByRole('heading', { name: t('passwordReset.title') })).toBeInTheDocument()
  expect(screen.getByLabelText(t('passwordReset.email'))).toHaveValue('ana@noetinger.test')
})

it('explains any other single sign-on failure in general terms', async () => {
  renderApp(<App />, { me: null, route: '/login?sso_error=something_new' })

  expect(await screen.findByText(t('login.ssoErrors.failed'))).toBeInTheDocument()
})

it('treats a profile check the server could not answer as signed out', async () => {
  mockApiError('get', '/auth/me', 500, 'generic')
  renderApp(<App />)

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
})
