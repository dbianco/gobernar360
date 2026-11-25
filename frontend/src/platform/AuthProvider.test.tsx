import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { api } from '../api/client'
import { makeMe, NOETINGER, SAIRA } from '../test/fixtures'
import { mockApi, mockApiError } from '../test/server'
import { useAuth } from './authContext'
import { AuthProvider } from './AuthProvider'

function Screen() {
  const { me, isLoading, login, logout, setActiveMunicipality } = useAuth()
  return (
    <>
      <p>{isLoading ? 'loading' : (me?.user.full_name ?? 'nobody')}</p>
      <p>{`in ${me?.active_municipality_id ?? 'none'}`}</p>
      <button onClick={() => void login('a@b.test', 'secret')}>login</button>
      <button onClick={() => void logout()}>logout</button>
      <button onClick={() => void setActiveMunicipality('m-2')}>switch</button>
      <button onClick={() => void api('/zones').catch(() => undefined)}>ask</button>
    </>
  )
}

/** Something another screen asked for. */
function Data() {
  const data = useQuery({ queryKey: ['zones'], queryFn: () => api<string>('/zones') })
  return <p>{`data: ${data.data ?? 'none'}`}</p>
}

function show(ui = <Screen />) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>,
  )
  return { client, user: userEvent.setup() }
}

const press = (name: string) => screen.getByRole('button', { name })

it('knows who is signed in', async () => {
  mockApi('get', '/auth/me', makeMe())
  show()

  expect(screen.getByText('loading')).toBeInTheDocument()
  expect(await screen.findByText('Ana Gómez')).toBeInTheDocument()
})

it('takes a 401 for nobody being signed in, and only a 401', async () => {
  mockApiError('get', '/auth/me', 401, 'not_authenticated')
  const { client } = show()
  expect(await screen.findByText('nobody')).toBeInTheDocument()
  expect(client.getQueryState(['me'])?.status).toBe('success')
})

it('does not take a failure of the server for being signed out', async () => {
  mockApiError('get', '/auth/me', 500, 'boom')
  const { client } = show()

  await waitFor(() => expect(client.getQueryState(['me'])?.status).toBe('error'))
  expect(client.getQueryData(['me'])).toBeUndefined()
})

it('signs in, forgetting what the one before had asked for', async () => {
  mockApiError('get', '/auth/me', 401, 'not_authenticated')
  const requests = mockApi('post', '/auth/login', makeMe())
  const { client, user } = show()
  await screen.findByText('nobody')
  client.setQueryData(['zones'], 'of somebody else')

  await user.click(press('login'))

  expect(await screen.findByText('Ana Gómez')).toBeInTheDocument()
  expect(requests[0].body).toEqual({ email: 'a@b.test', password: 'secret' })
  expect(client.getQueryData(['zones'])).toBeUndefined()
})

it.each([[204], [500]])('signs out whatever the server answers (%s)', async (status) => {
  mockApi('get', '/auth/me', makeMe())
  if (status === 204) mockApi('post', '/auth/logout', null, 204)
  else mockApiError('post', '/auth/logout', status, 'boom')
  const { client, user } = show()
  await screen.findByText('Ana Gómez')
  client.setQueryData(['zones'], 'private')

  await user.click(press('logout'))

  expect(await screen.findByText('nobody')).toBeInTheDocument()
  expect(client.getQueryData(['zones'])).toBeUndefined()
})

it('changes municipality, asking again for everything', async () => {
  const me = makeMe({ municipalities: [NOETINGER, SAIRA] })
  mockApi('get', '/auth/me', me)
  const requests = mockApi('post', '/auth/active-municipality', {
    ...me,
    active_municipality_id: 'm-2',
  })
  const { client, user } = show()
  await screen.findByText('in m-1')
  client.setQueryData(['zones'], 'of Noetinger')

  await user.click(press('switch'))

  expect(await screen.findByText('in m-2')).toBeInTheDocument()
  expect(requests[0].body).toEqual({ municipality_id: 'm-2' })
  expect(client.getQueryData(['zones'])).toBeUndefined()
})

it('sends whoever lost the session back to the start', async () => {
  mockApi('get', '/auth/me', makeMe())
  mockApiError('get', '/zones', 401, 'not_authenticated')
  const { user } = show()
  await screen.findByText('Ana Gómez')

  await user.click(press('ask'))

  expect(await screen.findByText('nobody')).toBeInTheDocument()
})

it('does not restore who was signed in when their profile arrives late', async () => {
  let calls = 0
  mockApi('get', '/auth/me', () => {
    calls += 1
    return makeMe()
  })
  mockApi('post', '/auth/logout', null, 204)
  const { client, user } = show()
  await screen.findByText('Ana Gómez')
  // As when coming back to the tab.
  void client.refetchQueries({ queryKey: ['me'] })

  await user.click(press('logout'))

  expect(await screen.findByText('nobody')).toBeInTheDocument()
  await waitFor(() => expect(calls).toBeGreaterThan(0))
  expect(screen.getByText('nobody')).toBeInTheDocument()
})

it('shows what other screens asked for', async () => {
  mockApi('get', '/auth/me', makeMe())
  mockApi('get', '/zones', 'fresh' as never)
  show(<Data />)

  expect(await screen.findByText('data: fresh')).toBeInTheDocument()
})
