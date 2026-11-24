import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { AssignmentsPage } from './AssignmentsPage'
import { makeAssignment, page, WORKSHOP } from './testData'
import { BASE, renderEconomic } from './testRender'

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
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed', { name: 'Panadería La Espiga' }),
    }),
  )

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
    await screen.findByRole('button', {
      name: label('editNamed', { name: 'Panadería La Espiga' }),
    }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(label('tool'))).toBeDisabled()
  expect(form.getByLabelText(label('tool'))).toHaveValue('Microcrédito productivo')
  expect(form.getByRole('textbox', { name: label('note') })).toHaveValue('Primera cuota')
  fireEvent.change(form.getByLabelText(label('date')), { target: { value: '2026-03-12' } })
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ date: '2026-03-12', note: 'Primera cuota' })
})

it('changes the year, keeps an assignment when deletion is declined and shows refusals', async () => {
  const list = mockApi('get', `${BASE}/assignments`, page([makeAssignment(), TO_PERSON]))
  const deleted = mockApiError('delete', `${BASE}/assignments/as-2`, 409, 'conflict')
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(t('app.year')), String(YEAR - 1))
  await waitFor(() => expect(list.at(-1)?.url.searchParams.get('year')).toBe(String(YEAR - 1)))
  const remove = await screen.findByRole('button', {
    name: label('deleteNamed', { name: 'Pérez, Juana' }),
  })
  await user.click(remove)
  expect(deleted).toHaveLength(0)
  confirm.mockReturnValue(true)
  await user.click(remove)

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
})

it('edits an assignment made to a person and closes the form', async () => {
  mockApi('get', `${BASE}/assignments`, page([TO_PERSON]))
  renderEconomic(<AssignmentsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: 'Pérez, Juana' }) }),
  )
  expect(await screen.findByRole('dialog', { name: label('editTitle') })).toBeInTheDocument()
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('reports assignments that cannot be loaded', async () => {
  mockApiError('get', `${BASE}/assignments`, 500, 'generic')
  renderEconomic(<AssignmentsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
