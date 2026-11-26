import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ComplaintsPage } from './ComplaintsPage'
import { makeClock, makeComplaint, makeDetail, NORTH, POTHOLE } from './testData'
import { BASE, renderComplaints } from './testRender'

const label = (key: string, options = {}) => t(`complaints.list.${key}`, options)
const form = (key: string, options = {}) => t(`complaints.form.${key}`, options)

function renderList(level: AccessLevel = 'editor', items = [makeComplaint()]) {
  const requests = mockApi('get', `${BASE}/complaints`, { items, total: items.length })
  const view = renderComplaints(
    <Routes>
      <Route path="/d/complaints/complaints" element={<ComplaintsPage />} />
      <Route path="/d/complaints/complaints/:id" element={<p>detail page</p>} />
    </Routes>,
    { level, route: '/d/complaints/complaints' },
  )
  return { ...view, list: requests }
}

it('lists complaints with their state, deadline and how their clock stands', async () => {
  renderList('viewer', [
    makeComplaint(),
    makeComplaint({
      id: 'co-2',
      number: 102,
      state: 'waiting',
      clock: makeClock({ left_days: -2, status: 'overdue', paused: true }),
    }),
    makeComplaint({
      id: 'co-3',
      number: 103,
      state: 'closed',
      clock: makeClock({
        used_days: 5,
        left_days: -2,
        status: 'overdue',
        resolved_on: '2026-03-09',
      }),
    }),
  ])

  const first = within(await screen.findByRole('row', { name: /San Martín 450.*En curso/ }))
  expect(
    first.getByRole('link', { name: t('complaints.table.openNamed', { number: 101 }) }),
  ).toHaveAttribute('href', '/d/complaints/complaints/co-1')
  expect(first.getByText('05/03/2026')).toBeInTheDocument()
  expect(first.getByText(t('complaints.statuses.on_time'))).toBeInTheDocument()
  expect(first.getByText('Quedan 2 días hábiles')).toBeInTheDocument()
  const late = within(screen.getByRole('row', { name: /102/ }))
  expect(late.getByText(t('complaints.statuses.overdue'))).toBeInTheDocument()
  expect(late.getByText(t('complaints.paused'))).toBeInTheDocument()
  expect(late.getByText('Vencido por 2 días hábiles')).toBeInTheDocument()
  // A solved complaint shows its outcome, not a pending deadline.
  const solved = within(screen.getByRole('row', { name: /103/ }))
  expect(solved.getByText(t('complaints.outcomes.overdue'))).toBeInTheDocument()
  expect(solved.getByText('Resuelto en 5 días hábiles')).toBeInTheDocument()
  expect(solved.queryByText('05/03/2026')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('create') })).not.toBeInTheDocument()
})

it('sends the filters as the query and starts again from the first page', async () => {
  const { list } = renderList()
  const user = userEvent.setup()
  await screen.findByRole('row', { name: /San Martín 450/ })

  await user.type(screen.getByRole('textbox', { name: t('app.search') }), 'mitre')
  await user.selectOptions(screen.getByLabelText(label('state')), 'open')
  await user.selectOptions(screen.getByLabelText(label('zone')), NORTH.id)
  await user.selectOptions(screen.getByLabelText(label('status')), 'overdue')

  await waitFor(() => {
    const query = list.at(-1)?.url.searchParams
    expect(query?.get('q')).toBe('mitre')
    expect(query?.get('state')).toBe('open')
    expect(query?.get('zone_id')).toBe(NORTH.id)
    expect(query?.get('status')).toBe('overdue')
    expect(query?.get('offset')).toBe('0')
  })
})

async function openForm() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: label('create') }))
  const dialog = within(await screen.findByRole('dialog'))
  return { user, dialog }
}

it('registers an anonymous complaint and opens it', async () => {
  const created = mockApi('post', `${BASE}/complaints`, makeDetail({ id: 'co-9' }), 201)
  renderList()
  const { user, dialog } = await openForm()

  // Retired types are not offered.
  const types = dialog.getByLabelText(form('type'))
  expect(
    within(types)
      .getAllByRole('option')
      .map((option) => option.textContent),
  ).toEqual(['Bache', 'Luminaria apagada'])
  expect(
    dialog.getByText(form('routing', { area: 'Obras Públicas', count: 15 })),
  ).toBeInTheDocument()
  await user.selectOptions(dialog.getByLabelText(form('zone')), NORTH.id)
  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Sarmiento 780')
  await user.type(dialog.getByRole('textbox', { name: form('description') }), 'Pozo grande')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toEqual({
    type_id: POTHOLE.id,
    zone_id: NORTH.id,
    address: 'Sarmiento 780',
    description: 'Pozo grande',
  })
  expect(await screen.findByText('detail page')).toBeInTheDocument()
})

it('files the complaint to a resident found in the registry by document', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, {
    person: makeDetail().person,
    registered_id: null,
  })
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'San Martín 450')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '33.123.456')
  // Saving before looking the document up shows who it is first.
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  expect(
    await dialog.findByText(form('found', { name: 'Fernández, Lucía', dni: '33.123.456' })),
  ).toBeInTheDocument()
  expect(lookups[0].url.searchParams.get('dni')).toBe('33123456')
  expect(created).toHaveLength(0)
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toMatchObject({ person_id: 'pe-1', address: 'San Martín 450' })
})

it('adds a resident the registry does not have', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Moreno 1120')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '40111222')
  await user.click(dialog.getByRole('button', { name: form('lookup') }))
  expect(await dialog.findByText(form('notFound'))).toBeInTheDocument()
  await user.type(dialog.getByRole('textbox', { name: t('people.firstName') }), 'Juan')
  await user.type(dialog.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.type(dialog.getByRole('textbox', { name: t('people.phone') }), '555')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toMatchObject({
    new_person: { first_name: 'Juan', last_name: 'Paz', phone: '555', email: '', dni: '40111222' },
  })
  expect(created[0].body).not.toHaveProperty('person_id')
})

it('files the complaint to a resident found by CUIL', async () => {
  const lookups = mockApi('get', `${BASE}/people/lookup`, {
    person: { ...makeDetail().person, dni: null, cuil: '20123456786' },
    registered_id: null,
  })
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'San Martín 450')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '20-12345678-6')
  await user.click(dialog.getByRole('button', { name: form('lookup') }))

  expect(
    await dialog.findByText(form('foundByCuil', { name: 'Fernández, Lucía', cuil: '20-12345678-6' })),
  ).toBeInTheDocument()
  const asked = lookups[0].url.searchParams
  expect([asked.get('cuil'), asked.get('dni')]).toEqual(['20123456786', null])
  await user.click(dialog.getByRole('button', { name: t('app.save') }))
  await waitFor(() => expect(created[0]?.body).toMatchObject({ person_id: 'pe-1' }))
})

it('adds a resident known only by their CUIL', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Moreno 1120')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '20123456786')
  await user.click(dialog.getByRole('button', { name: form('lookup') }))
  expect(await dialog.findByText(form('notFound'))).toBeInTheDocument()
  // It is already there.
  expect(dialog.queryByRole('textbox', { name: t('people.cuil') })).toBeNull()
  await user.type(dialog.getByRole('textbox', { name: t('people.firstName') }), 'Juan')
  await user.type(dialog.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toMatchObject({
    new_person: {
      first_name: 'Juan',
      last_name: 'Paz',
      cuil: '20123456786',
      phone: '',
      email: '',
    },
  })
  expect((created[0].body as { new_person: object }).new_person).not.toHaveProperty('dni')
})

it('takes the CUIL of a new resident, of their own document', async () => {
  mockApi('get', `${BASE}/people/lookup`, { person: null, registered_id: null })
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Moreno 1120')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '12345678')
  await user.click(dialog.getByRole('button', { name: form('lookup') }))
  const cuil = await dialog.findByRole('textbox', { name: t('people.cuil') })
  await user.type(cuil, '20-1234567')
  expect(dialog.getByText(t('people.cuilInvalid'))).toBeInTheDocument()
  await user.clear(cuil)
  await user.type(cuil, '27111111117')
  expect(dialog.getByText(t('people.cuilMismatch'))).toBeInTheDocument()
  await user.type(dialog.getByRole('textbox', { name: t('people.firstName') }), 'Juan')
  await user.type(dialog.getByRole('textbox', { name: t('people.lastName') }), 'Paz')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))
  expect(created).toHaveLength(0)
  await user.clear(cuil)
  await user.type(cuil, '20-12345678-6')
  expect(dialog.queryByText(t('people.cuilMismatch'))).toBeNull()
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toMatchObject({
    new_person: { dni: '12345678', cuil: '20123456786' },
  })
})

it('does not look up a document that cannot be one', async () => {
  renderList()
  const { user, dialog } = await openForm()

  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '12')

  expect(dialog.getByText(form('dniInvalid'))).toBeInTheDocument()
  expect(dialog.getByRole('button', { name: form('lookup') })).toBeDisabled()
  // Nor is it saved, although the rest is there.
  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Moreno 1120')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('shows why the registry could not be asked, and why saving failed', async () => {
  mockApiError('get', `${BASE}/people/lookup`, 500, 'generic')
  mockApiError('post', `${BASE}/complaints`, 422, 'invalid_reference')
  renderList()
  const { user, dialog } = await openForm()

  await user.selectOptions(dialog.getByLabelText(form('type')), 'ty-1')
  expect(
    dialog.getByText(form('routing', { area: 'Alumbrado Público', count: 3 })),
  ).toBeInTheDocument()
  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Mitre 1')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '12345678')
  await user.click(dialog.getByRole('button', { name: form('lookup') }))
  expect(await dialog.findByText(t('errors.generic'))).toBeInTheDocument()
  // Back to anonymous: the complaint can be saved without the registry.
  await user.click(dialog.getByRole('radio', { name: form('anonymous') }))
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  expect(await dialog.findByText(t('errors.invalid_reference'))).toBeInTheDocument()
})

it('does not save an identified complaint with a malformed document, and cancels', async () => {
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user, dialog } = await openForm()

  await user.type(dialog.getByRole('textbox', { name: form('address') }), 'Mitre 1')
  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '123')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))
  expect(created).toHaveLength(0)
  await user.click(dialog.getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.queryByText('detail page')).not.toBeInTheDocument()
})

it('asks for parameters before registering, and reports a list that cannot load', async () => {
  renderList('editor', [])
  mockApi('get', `${BASE}/zones`, [])
  mockApiError('get', `${BASE}/complaints`, 500, 'generic')

  expect(await screen.findByText(label('needsParameters'))).toBeInTheDocument()
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})

it('pages through a long list and filters by type and area', async () => {
  const { list } = renderList('viewer', [makeComplaint()])
  mockApi('get', `${BASE}/complaints`, (request) => {
    list.push(request)
    return { items: [makeComplaint()], total: 120 }
  })
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.pager.next') }))
  await waitFor(() => expect(list.at(-1)?.url.searchParams.get('offset')).toBe('10'))
  await user.selectOptions(screen.getByLabelText(label('type')), 'ty-2')
  await user.selectOptions(screen.getByLabelText(label('area')), 'ar-2')

  await waitFor(() => {
    const query = list.at(-1)?.url.searchParams
    expect(query?.get('type_id')).toBe('ty-2')
    expect(query?.get('area_id')).toBe('ar-2')
    expect(query?.get('offset')).toBe('0')
  })
})

it('closes the form without registering anything', async () => {
  const created = mockApi('post', `${BASE}/complaints`, makeDetail(), 201)
  renderList()
  const { user } = await openForm()

  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(created).toHaveLength(0)
})

it('says so when there are no complaints', async () => {
  renderList('viewer', [])

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('shows no clock for a rejected complaint', async () => {
  renderList('viewer', [
    makeComplaint({ state: 'rejected', clock: makeClock({ status: null }) }),
  ])

  const row = within(await screen.findByRole('row', { name: /101/ }))
  expect(row.getByText(t('complaints.states.rejected'))).toBeInTheDocument()
  for (const status of ['on_time', 'at_risk', 'overdue']) {
    expect(row.queryByText(t(`complaints.statuses.${status}`))).not.toBeInTheDocument()
  }
})
