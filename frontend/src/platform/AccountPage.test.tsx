import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import { AccountPage } from './AccountPage'

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
