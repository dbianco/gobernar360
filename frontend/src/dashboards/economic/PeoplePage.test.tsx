import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { PeoplePage } from './PeoplePage'
import { LUIS, makePerson, makeRegistryPerson, page } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string, options = {}) => t(`economic.people.${key}`, options)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists the people of the dashboard', async () => {
  mockApi('get', `${BASE}/people`, page([LUIS, makePerson()]))
  renderEconomic(<PeoplePage />)

  const row = within(await screen.findByRole('row', { name: /Pérez, Juana/ }))
  expect(row.getByText('12.345.678')).toBeInTheDocument()
  expect(row.getByText(t('economic.employmentStatuses.self_employed'))).toBeInTheDocument()
  expect(row.getByText('Costurera')).toBeInTheDocument()
  expect(row.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/economic/people/ep-1',
  )
})

it('searches and filters on the server, and hides creation from viewers', async () => {
  const requests = mockApi('get', `${BASE}/people`, page([makePerson()]))
  renderEconomic(<PeoplePage />, { level: 'viewer' })
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Pérez, Juana/ })
  await user.type(screen.getByRole('textbox', { name: t('app.search') }), 'pe')
  await user.selectOptions(screen.getByLabelText(label('employmentStatus')), 'unemployed')

  await waitFor(() => {
    expect(last(requests).url.searchParams.get('q')).toBe('pe')
    expect(last(requests).url.searchParams.get('employment_status')).toBe('unemployed')
  })
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})

async function openForm() {
  mockApi('get', `${BASE}/people`, page([]))
  renderEconomic(<PeoplePage />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('create') }))
  return { user, form: within(await screen.findByRole('dialog')) }
}

it('registers a new person', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: label('dni') }), '30.111.222')
  await user.type(form.getByRole('textbox', { name: label('firstName') }), 'Elena')
  await waitFor(() => expect(lookups).toHaveLength(1))
  expect(lookups[0].url.searchParams.get('dni')).toBe('30111222')
  await user.type(form.getByRole('textbox', { name: label('lastName') }), 'Paz')
  await user.type(form.getByRole('textbox', { name: label('neighborhood') }), 'Sur')
  await user.selectOptions(form.getByLabelText(label('employmentStatus')), 'employed')
  await user.type(form.getByRole('textbox', { name: label('occupation') }), 'Cuidadora')
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
      neighborhood: 'Sur',
    },
    employment_status: 'employed',
    occupation: 'Cuidadora',
  })
})

it('fills the form with the registry data of a known document', async () => {
  const known = makeRegistryPerson({ id: 'p-9', first_name: 'Mirta', last_name: 'Domínguez' })
  mockApi('get', `${BASE}/people/lookup`, { person: known, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: label('dni') }), '12345678')
  await user.tab()

  expect(
    await form.findByText(label('inRegistry', { name: 'Domínguez, Mirta' })),
  ).toBeInTheDocument()
  expect(form.getByRole('textbox', { name: label('firstName') })).toHaveValue('Mirta')
  expect(form.getByRole('textbox', { name: label('address') })).toHaveValue('Belgrano 45')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({
    person: { first_name: 'Mirta', last_name: 'Domínguez', dni: '12345678', birth_date: '1990-05-01' },
  })
})

it('looks the document up before saving when the field never lost focus', async () => {
  const known = makeRegistryPerson({ first_name: 'Mirta', last_name: 'Domínguez' })
  mockApi('get', `${BASE}/people/lookup`, { person: known, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: label('firstName') }), 'M')
  await user.type(form.getByRole('textbox', { name: label('lastName') }), 'D')
  await user.type(form.getByRole('textbox', { name: label('dni') }), '12345678{Enter}')

  expect(
    await form.findByText(label('inRegistry', { name: 'Domínguez, Mirta' })),
  ).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})

it('points to the existing record when the person is already in the dashboard', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: makeRegistryPerson(), registered_id: 'ep-1' })
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: label('dni') }), '12345678')
  await user.tab()

  expect(
    await form.findByText(label('alreadyRegistered', { name: 'Pérez, Juana' })),
  ).toBeInTheDocument()
  expect(form.getByRole('link', { name: label('openExisting') })).toHaveAttribute(
    'href',
    '/d/economic/people/ep-1',
  )
  expect(form.getByRole('button', { name: t('app.save') })).toBeDisabled()
})

it('rejects a malformed document without calling the server', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: label('firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: label('lastName') }), 'Paz')
  await user.type(form.getByRole('textbox', { name: label('dni') }), '12{Enter}')

  expect(await form.findByText(label('dniInvalid'))).toBeInTheDocument()
  expect(lookups).toHaveLength(0)
  expect(requests).toHaveLength(0)
})
