import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { AssignmentsPage } from './AssignmentsPage'
import { makeAssignment, page, WORKSHOP } from './testData'
import { BASE, renderEconomic } from './testRender'
import { answerConfirm } from '../../test/confirm'

const label = (key: string, options = {}) => t(`economic.assignments.${key}`, options)
const YEAR = new Date().getFullYear()
const TO_PERSON = makeAssignment({
  id: 'as-2',
  date: '2026-02-01',
  note: '',
  tool: { id: WORKSHOP.id, name: WORKSHOP.name },
  actor: null,
  person: { id: 'ep-1', full_name: 'Pérez, Juana' },
})

it('lists the assignments of the year with their recipients', async () => {
  const requests = mockApi('get', `${BASE}/assignments`, page([makeAssignment(), TO_PERSON]))
  renderEconomic(<AssignmentsPage />, { level: 'viewer' })

  const toActor = within(await screen.findByRole('row', { name: /Microcrédito productivo/ }))
  expect(toActor.getByText('10/03/2026')).toBeInTheDocument()
  expect(toActor.getByText(label('actor'))).toBeInTheDocument()
  expect(toActor.getByRole('link', { name: 'Panadería La Espiga' })).toHaveAttribute(
    'href',
    '/d/economic/actors/a-1',
  )
  const toPerson = within(screen.getByRole('row', { name: /Taller de oficios/ }))
  expect(toPerson.getByText(label('person'))).toBeInTheDocument()
  expect(toPerson.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/economic/people/ep-1',
  )
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
  expect(screen.queryByRole('button', { name: /Eliminar/ })).toBeNull()
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/assignments.csv?year=${YEAR}`,
  )
})

it('filters by tool', async () => {
  const requests = mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Microcrédito productivo/ })
  await user.selectOptions(screen.getByLabelText(label('tool')), WORKSHOP.id)

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('tool_id')).toBe(WORKSHOP.id))
})

it('lets an editor delete an assignment', async () => {
  mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  const requests = mockApi('delete', `${BASE}/assignments/as-1`, null, 204)
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed', { name: 'Panadería La Espiga' }),
    }),
  )
  await answerConfirm(user, true)

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('says when the year has no assignments', async () => {
  mockApi('get', `${BASE}/assignments`, page([]))
  renderEconomic(<AssignmentsPage />)

  expect(await screen.findByText(label('emptyYear'))).toBeInTheDocument()
})

it('lets an editor correct the date and the note of an assignment', async () => {
  mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  const requests = mockApi('patch', `${BASE}/assignments/as-1`, makeAssignment())
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: 'Panadería La Espiga' }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(label('tool'))).toBeDisabled()
  expect(form.getByLabelText(label('tool'))).toHaveValue('Microcrédito productivo')
  expect(form.getByRole('textbox', { name: label('note') })).toHaveValue('Primera cuota')
  fireEvent.change(form.getByLabelText(label('date')), { target: { value: '12/03/2026' } })
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ date: '2026-03-12', note: 'Primera cuota' })
})

it('searches by tool or recipient on the server', async () => {
  const requests = mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.type(await screen.findByRole('searchbox', { name: t('app.search') }), 'espiga')

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('q')).toBe('espiga'))
})

it('asks the server for another year, from the first page', async () => {
  const requests = mockApi('get', `${BASE}/assignments`, page([makeAssignment()], 30))
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()
  await screen.findByRole('row', { name: /Microcrédito productivo/ })
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  await user.selectOptions(screen.getByLabelText(t('app.year')), String(YEAR - 1))

  await waitFor(() => {
    const params = requests.at(-1)?.url.searchParams
    expect([params?.get('year'), params?.get('offset')]).toEqual([String(YEAR - 1), '0'])
  })
})

it('keeps an assignment when its deletion is not confirmed, and says why one failed', async () => {
  mockApi('get', `${BASE}/assignments`, page([TO_PERSON]))
  const deleted = mockApiError('delete', `${BASE}/assignments/as-2`, 409, 'in_use')
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()
  const remove = () =>
    screen.findByRole('button', { name: label('deleteNamed', { name: 'Pérez, Juana' }) })

  await user.click(await remove())
  await answerConfirm(user, false)
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deleted).toHaveLength(0)

  await user.click(await remove())
  await answerConfirm(user, true)
  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('corrects an assignment to a person, and closes the form with Escape', async () => {
  mockApi('get', `${BASE}/assignments`, page([TO_PERSON]))
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: 'Pérez, Juana' }) }),
  )
  await screen.findByRole('dialog', { name: label('editTitle') })
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('shows an error when the assignments cannot be loaded', async () => {
  mockApiError('get', `${BASE}/assignments`, 500, 'generic')
  renderEconomic(<AssignmentsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('shows and corrects an assignment whose recipient is no longer there', async () => {
  mockApi('get', `${BASE}/assignments`, page([makeAssignment({ actor: null, person: null })]))
  const patches = mockApi('patch', `${BASE}/assignments/:id`, makeAssignment())
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  const rows = (await screen.findAllByRole('row')).slice(1)
  expect(rows).toHaveLength(1)
  await user.click(within(rows[0]).getAllByRole('button')[0])
  const form = within(await screen.findByRole('dialog', { name: label('editTitle') }))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(patches).toHaveLength(1))
})
