import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { PeoplePage } from './PeoplePage'
import { LUIS, makePerson, makeRegistryPerson, page } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.people.${key}`, options)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists the people of the dashboard with their household', async () => {
  mockApi('get', `${BASE}/people`, page([LUIS, makePerson()]))
  renderSocial(<PeoplePage />)

  const row = within(await screen.findByRole('row', { name: /Pérez, Juana/ }))
  expect(row.getByText('12.345.678')).toBeInTheDocument()
  expect(row.getByText('Centro')).toBeInTheDocument()
  expect(row.getByText(t('social.relationships.head'))).toBeInTheDocument()
  expect(row.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/social/people/sp-1',
  )
  expect(row.getByRole('link', { name: 'Familia Pérez' })).toHaveAttribute(
    'href',
    '/d/social/households/h-1',
  )
  const alone = within(screen.getByRole('row', { name: /Gómez, Luis/ }))
  expect(alone.getByText(label('noHousehold'))).toBeInTheDocument()
})

it('searches and filters on the server, and hides creation from viewers', async () => {
  const requests = mockApi('get', `${BASE}/people`, page([makePerson()]))
  renderSocial(<PeoplePage />, { level: 'viewer' })
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Pérez, Juana/ })
  await user.type(screen.getByRole('textbox', { name: t('app.search') }), 'pe')
  await user.type(screen.getByRole('textbox', { name: label('neighborhoodFilter') }), 'sur')

  await waitFor(() => {
    expect(last(requests).url.searchParams.get('q')).toBe('pe')
    expect(last(requests).url.searchParams.get('neighborhood')).toBe('sur')
  })
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})

it('asks the server for the next page', async () => {
  const requests = mockApi('get', `${BASE}/people`, page([makePerson()], 120))
  renderSocial(<PeoplePage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Pérez, Juana/ })
  expect(screen.getByText(t('app.pager.range', { from: 1, to: 50, total: 120 }))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  await waitFor(() => expect(last(requests).url.searchParams.get('offset')).toBe('50'))
})

it('says so when nobody matches', async () => {
  mockApi('get', `${BASE}/people`, page([]))
  renderSocial(<PeoplePage />)

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
})

async function openForm() {
  mockApi('get', `${BASE}/people`, page([]))
  renderSocial(<PeoplePage />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('create') }))
  return { user, form: within(await screen.findByRole('dialog')) }
}

it('registers a new person after looking the document up', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '30.111.222')
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await waitFor(() => expect(lookups).toHaveLength(1))
  expect(lookups[0].url.searchParams.get('dni')).toBe('30111222')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    person: {
      first_name: 'Elena',
      last_name: 'Paz',
      dni: '30111222',
      birth_date: null,
      phone: '',
      email: '',
      address: '',
      neighborhood: '',
    },
  })
})

it('offers the data of a person another dashboard already loaded', async () => {
  const known = makeRegistryPerson({
    id: 'p-9',
    first_name: 'Diego',
    last_name: 'Sosa',
    full_name: 'Sosa, Diego',
  })
  mockApi('get', `${BASE}/people/lookup`, { person: known, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '12345678')
  await user.tab()

  expect(await form.findByText(t('people.inRegistry', { name: 'Sosa, Diego' }))).toBeInTheDocument()
  expect(form.getByRole('textbox', { name: t('people.firstName') })).toHaveValue('Diego')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ person: { last_name: 'Sosa', dni: '12345678' } })
})

it('points to the existing record when the person is already in the dashboard', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: makeRegistryPerson(), registered_id: 'sp-1' })
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '12345678')
  await user.tab()

  expect(
    await form.findByText(t('people.alreadyRegistered', { name: 'Pérez, Juana' })),
  ).toBeInTheDocument()
  expect(form.getByRole('link', { name: t('people.openExisting') })).toHaveAttribute(
    'href',
    '/d/social/people/sp-1',
  )
  expect(form.getByRole('button', { name: t('app.save') })).toBeDisabled()
})
