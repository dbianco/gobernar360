import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { HouseholdsPage } from './HouseholdsPage'
import { makeHousehold, page } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.households.${key}`, options)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists the households with their head and size', async () => {
  const empty = makeHousehold({ id: 'h-2', name: 'Familia Gómez', member_count: 0, head: null })
  mockApi('get', `${BASE}/households`, page([empty, makeHousehold()]))
  renderSocial(<HouseholdsPage />)

  const row = within(await screen.findByRole('row', { name: /Familia Pérez/ }))
  expect(row.getByRole('link', { name: 'Familia Pérez' })).toHaveAttribute(
    'href',
    '/d/social/households/h-1',
  )
  expect(row.getByText('Belgrano 45')).toBeInTheDocument()
  expect(row.getByText('Pérez, Juana')).toBeInTheDocument()
  expect(row.getByText('2')).toBeInTheDocument()
  expect(
    within(screen.getByRole('row', { name: /Familia Gómez/ })).getByText(label('noHead')),
  ).toBeInTheDocument()
})

it('searches on the server and hides creation from viewers', async () => {
  const requests = mockApi('get', `${BASE}/households`, page([makeHousehold()]))
  renderSocial(<HouseholdsPage />, { level: 'viewer' })
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Familia Pérez/ })
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'belg')

  await waitFor(() => expect(last(requests).url.searchParams.get('q')).toBe('belg'))
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})

it('creates a household', async () => {
  mockApi('get', `${BASE}/households`, page([]))
  const requests = mockApi('post', `${BASE}/households`, makeHousehold(), 201)
  renderSocial(<HouseholdsPage />)
  const user = userEvent.setup()

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Familia Ledesma')
  await user.type(form.getByRole('textbox', { name: label('address') }), 'Calle 12')
  await user.type(form.getByRole('textbox', { name: label('neighborhood') }), 'Norte')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Familia Ledesma',
    address: 'Calle 12',
    neighborhood: 'Norte',
  })
})

it('shows a missing address as none and says why the list cannot be loaded', async () => {
  mockApi('get', `${BASE}/households`, page([makeHousehold({ address: '', neighborhood: '', zones: [{ id: 'z-1', name: 'Sur' }] })]))
  const { unmount } = renderSocial(<HouseholdsPage />)

  const row = within(await screen.findByRole('row', { name: /Familia Pérez/ }))
  expect(row.getAllByText(t('app.none'))).toHaveLength(2)
  expect(row.getByText('Sur')).toBeInTheDocument()
  unmount()

  mockApiError('get', `${BASE}/households`, 500, 'boom')
  renderSocial(<HouseholdsPage />)
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('keeps the create form open when saving fails, and closes it with Escape', async () => {
  mockApi('get', `${BASE}/households`, page([]))
  mockApiError('post', `${BASE}/households`, 409, 'conflict')
  renderSocial(<HouseholdsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Familia Ledesma')
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})
