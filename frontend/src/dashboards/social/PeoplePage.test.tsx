import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { delay, http, HttpResponse } from 'msw'

import { mockApi, mockApiError, server } from '../../test/server'
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
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'pe')
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
  expect(screen.getByText(t('app.pager.range', { from: 1, to: 10, total: 120 }))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  await waitFor(() => expect(last(requests).url.searchParams.get('offset')).toBe('10'))
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
      cuil: null,
      birth_date: null,
      phone: '',
      email: '',
      address: '',
      neighborhood: '',
    },
  })
})

it('registers everything about a person, the day they were born included', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()
  const type = (key: string, text: string) =>
    user.type(form.getByRole('textbox', { name: t(`people.${key}`) }), text)

  await type('firstName', 'Elena')
  await type('lastName', 'Paz')
  await type('birthDate', '05/01/1983')
  await type('phone', '111')
  await type('email', 'elena@noetinger.test')
  await type('address', 'Mitre 780')
  await type('neighborhood', 'Sur')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({
    person: {
      first_name: 'Elena',
      last_name: 'Paz',
      birth_date: '1983-01-05',
      phone: '111',
      email: 'elena@noetinger.test',
      address: 'Mitre 780',
      neighborhood: 'Sur',
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

it('says why the list cannot be loaded, and closes the create form with Escape', async () => {
  mockApiError('get', `${BASE}/people`, 500, 'boom')
  renderSocial(<PeoplePage />)
  const user = userEvent.setup()

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('create') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says why the document could not be looked up, and does not save', async () => {
  mockApiError('get', `${BASE}/people/lookup`, 500, 'boom')
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '30111222')
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})

it('ignores what the registry says about a document that was changed meanwhile', async () => {
  server.use(
    http.get(`*/api${BASE}/people/lookup`, async ({ request }) => {
      const dni = new URL(request.url).searchParams.get('dni')
      if (dni === '1234567') {
        await delay(300)
        return HttpResponse.json({ person: makeRegistryPerson(), registered_id: null })
      }
      return HttpResponse.json({ person: null, registered_id: null })
    }),
  )
  const { user, form } = await openForm()
  const dni = form.getByRole('textbox', { name: t('people.dni') })

  await user.type(dni, '1234567')
  await user.tab()
  await user.type(dni, '8')
  await new Promise((resolve) => setTimeout(resolve, 400))

  expect(form.queryByText(t('people.inRegistry', { name: 'Pérez, Juana' }))).toBeNull()
  expect(form.getByRole('textbox', { name: t('people.firstName') })).toHaveValue('')
})

it('keeps the form and says why the person could not be registered', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  mockApiError('post', `${BASE}/people`, 409, 'dni_exists')
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '30111222')
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.dni_exists'))).toBeInTheDocument()
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

const cuilField = (form: Awaited<ReturnType<typeof openForm>>['form']) =>
  form.getByRole('textbox', { name: t('people.cuil') })

it('saves the CUIL in digits, however it is typed', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '12345678')
  await user.type(cuilField(form), '20-12345678-6')
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() =>
    expect(requests[0]?.body).toMatchObject({ person: { dni: '12345678', cuil: '20123456786' } }),
  )
})

it('refuses a CUIL that is not one, or of another document, without calling the server', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')

  await user.type(cuilField(form), '20-12345678-7')
  await user.tab()
  expect(await form.findByText(t('people.cuilInvalid'))).toBeInTheDocument()
  await user.clear(cuilField(form))
  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '30111222')
  await user.type(cuilField(form), '20-12345678-6')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('people.cuilMismatch'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)
  expect(lookups.every(({ url }) => !url.searchParams.has('cuil'))).toBe(true)
})

it('looks somebody without a document up by CUIL, and shows what the registry has', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, {
    person: makeRegistryPerson({ dni: '12345678', cuil: '20123456786' }),
    registered_id: null,
  })
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()

  await user.type(cuilField(form), '20-12345678-6')
  await user.tab()

  expect(
    await form.findByText(t('people.inRegistry', { name: 'Pérez, Juana' })),
  ).toBeInTheDocument()
  expect(lookups[0].url.searchParams.get('cuil')).toBe('20123456786')
  expect(form.getByRole('textbox', { name: t('people.dni') })).toHaveValue('12345678')
  await user.click(form.getByRole('button', { name: t('app.save') }))
  await waitFor(() =>
    expect(requests[0]?.body).toMatchObject({ person: { dni: '12345678', cuil: '20123456786' } }),
  )
  // What it answered was enough.
  expect(lookups).toHaveLength(1)
})

it('does not leave the registry data of one CUIL under another', async () => {
  mockApi('get', `${BASE}/people/lookup`, {
    person: makeRegistryPerson({ dni: null, cuil: '20123456786' }),
    registered_id: null,
  })
  const { user, form } = await openForm()
  await user.type(cuilField(form), '20123456786')
  await user.tab()
  const name = form.getByRole('textbox', { name: t('people.firstName') })
  await waitFor(() => expect(name).toHaveValue('Juana'))

  await user.type(cuilField(form), '{Backspace}')

  expect(name).toHaveValue('')
})

it('keeps the CUIL that was typed when the registry has none', async () => {
  mockApi('get', `${BASE}/people/lookup`, ({ url }) => ({
    person: url.searchParams.has('dni')
      ? (makeRegistryPerson({ dni: '12345678', cuil: null }) as never)
      : null,
    registered_id: null,
  }))
  const requests = mockApi('post', `${BASE}/people`, makePerson(), 201)
  const { user, form } = await openForm()
  await user.type(cuilField(form), '20-12345678-6')
  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '12345678')
  await user.tab()
  await form.findByText(t('people.inRegistry', { name: 'Pérez, Juana' }))

  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() =>
    expect(requests[0]?.body).toMatchObject({ person: { dni: '12345678', cuil: '20123456786' } }),
  )
})

it('says that somebody else has the CUIL', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  mockApiError('post', `${BASE}/people`, 409, 'cuil_exists')
  const { user, form } = await openForm()
  await user.type(form.getByRole('textbox', { name: t('people.firstName') }), 'Elena')
  await user.type(form.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.type(form.getByRole('textbox', { name: t('people.dni') }), '12345678')
  await user.type(cuilField(form), '20123456786')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.cuil_exists'))).toBeInTheDocument()
})
