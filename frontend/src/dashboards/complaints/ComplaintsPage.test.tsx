import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
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

it('does not look up a document that cannot be one', async () => {
  renderList()
  const { user, dialog } = await openForm()

  await user.click(dialog.getByRole('radio', { name: form('identified') }))
  await user.type(dialog.getByRole('textbox', { name: form('dni') }), '12')

  expect(dialog.getByText(t('people.dniInvalid'))).toBeInTheDocument()
  expect(dialog.getByRole('button', { name: form('lookup') })).toBeDisabled()
})
