import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ActorDetailPage } from './ActorDetailPage'
import {
  CREDIT,
  FAIR,
  FOOD,
  LUIS,
  makeActorDetail,
  makeAssignment,
  makePerson,
  page,
  WORKSHOP,
} from './testData'
import { BASE, renderEconomic } from './testRender'
import { answerConfirm } from '../../test/confirm'

const label = (key: string, options = {}) => t(`economic.actors.${key}`, options)
const assignment = (key: string, options = {}) => t(`economic.assignments.${key}`, options)

function renderDetail(level: AccessLevel = 'editor') {
  mockApi('get', `${BASE}/actors/a-1`, makeActorDetail())
  const assignments = mockApi('get', `${BASE}/assignments`, page([makeAssignment()]))
  const view = renderEconomic(
    <Routes>
      <Route path="/d/economic/actors/:id" element={<ActorDetailPage />} />
      <Route path="/d/economic/actors" element={<p>actor list</p>} />
    </Routes>,
    { level, route: '/d/economic/actors/a-1' },
  )
  return { ...view, assignments }
}

it('shows the actor, its people and its assignments', async () => {
  const { assignments } = renderDetail('viewer')

  expect(await screen.findByRole('heading', { name: 'Panadería La Espiga' })).toBeInTheDocument()
  expect(screen.getByText('30-71111111-8')).toBeInTheDocument()
  const person = screen.getByRole('link', { name: 'Pérez, Juana' })
  expect(person).toHaveAttribute('href', '/d/economic/people/ep-1')
  expect(screen.getByText(t('economic.roles.owner'))).toBeInTheDocument()
  expect(await screen.findByRole('row', { name: /Microcrédito productivo/ })).toHaveTextContent(
    '10/03/2026',
  )
  expect(assignments[0].url.searchParams.get('actor_id')).toBe('a-1')
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
  expect(screen.queryByRole('button', { name: label('linkPerson') })).toBeNull()
  expect(screen.queryByRole('button', { name: assignment('add') })).toBeNull()
})

it('links a person found by search', async () => {
  const people = mockApi('get', `${BASE}/people`, page([LUIS]))
  const requests = mockApi('post', `${BASE}/actors/a-1/people`, { id: 'l-2' }, 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('linkPerson') }))
  await user.type(screen.getByRole('textbox', { name: label('findPerson') }), 'acosta')
  await waitFor(() => expect(people.at(-1)?.url.searchParams.get('q')).toBe('acosta'))
  await user.selectOptions(await screen.findByLabelText(label('role')), 'employee')
  await user.click(screen.getByRole('button', { name: label('linkNamed', { name: 'Acosta, Luis' }) }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ person_id: LUIS.id, role: 'employee' })
})

it('unlinks a person', async () => {
  const requests = mockApi('delete', `${BASE}/actors/a-1/people/l-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('unlinkNamed', { name: 'Pérez, Juana' }) }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('assigns a tool, offering only the tools meant for actors', async () => {
  const requests = mockApi('post', `${BASE}/assignments`, makeAssignment(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: assignment('add') }))
  const form = within(await screen.findByRole('dialog'))
  // The tools load after the dialog opens.
  await form.findByRole('option', { name: FAIR.name })
  const tool = form.getByLabelText(assignment('tool')) as HTMLSelectElement
  expect([...tool.options].map((option) => option.text)).toEqual([
    assignment('chooseTool'),
    FAIR.name,
    CREDIT.name,
  ])
  expect([...tool.options].map((option) => option.text)).not.toContain(WORKSHOP.name)
  await user.selectOptions(tool, FAIR.id)
  fireEvent.change(form.getByLabelText(assignment('date')), { target: { value: '02/04/2026' } })
  await user.type(form.getByRole('textbox', { name: assignment('note') }), 'Puesto 12')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    tool_id: FAIR.id,
    actor_id: 'a-1',
    date: '2026-04-02',
    note: 'Puesto 12',
  })
})

it('deletes an assignment after confirming', async () => {
  const requests = mockApi('delete', `${BASE}/assignments/as-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: assignment('deleteNamed', { name: 'Microcrédito productivo' }),
    }),
  )
  await answerConfirm(user, true)

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('deletes the actor after confirming and returns to the list', async () => {
  const requests = mockApi('delete', `${BASE}/actors/a-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  await answerConfirm(user, true)

  expect(await screen.findByText('actor list')).toBeInTheDocument()
  expect(requests).toHaveLength(1)
})

it('corrects the note of an assignment from the actor', async () => {
  const requests = mockApi('patch', `${BASE}/assignments/as-1`, makeAssignment())
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: assignment('editNamed', { name: 'Microcrédito productivo' }),
    }),
  )
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: assignment('note') }), ' pagada')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ date: '2026-03-10', note: 'Primera cuota pagada' })
})

it('keeps it when the deletion is not confirmed', async () => {
  const deleted = mockApi('delete', `${BASE}/actors/a-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  await answerConfirm(user, false)

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deleted).toHaveLength(0)
})

it('says why the deletion failed and stays', async () => {
  mockApiError('delete', `${BASE}/actors/a-1`, 409, 'in_use')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('closes the edit form with Escape', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('saves the edited actor, sending empty choices as null, and closes the form', async () => {
  const requests = mockApi('patch', `${BASE}/actors/a-1`, makeActorDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(form.getByLabelText(label('type')), '')
  await user.clear(form.getByLabelText(label('employees')))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({
    name: 'Panadería La Espiga',
    actor_type_id: null,
    sector_id: FOOD.id,
    cuit: '30711111118',
    employee_count: null,
  })
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('keeps the edit form open and says why saving failed', async () => {
  mockApiError('patch', `${BASE}/actors/a-1`, 409, 'conflict')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('keeps the link panel open and says why linking failed', async () => {
  mockApi('get', `${BASE}/people`, page([LUIS]))
  mockApiError('post', `${BASE}/actors/a-1/people`, 409, 'conflict')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('linkPerson') }))
  await user.type(screen.getByRole('textbox', { name: label('findPerson') }), 'acosta')
  await user.click(
    await screen.findByRole('button', { name: label('linkNamed', { name: 'Acosta, Luis' }) }),
  )

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: label('findPerson') })).toBeInTheDocument()
})

it('says when the search finds nobody new and when it fails', async () => {
  // Juana is already linked, so finding only her is finding nobody.
  const people = mockApi('get', `${BASE}/people`, page([makePerson()]))
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('linkPerson') }))
  const search = screen.getByRole('textbox', { name: label('findPerson') })
  await user.type(search, 'p')
  expect(screen.queryByText(label('noMatches'))).toBeNull()
  await user.type(search, 'e')
  expect(await screen.findByText(label('noMatches'))).toBeInTheDocument()
  expect(people.at(-1)?.url.searchParams.get('limit')).toBe('8')

  mockApiError('get', `${BASE}/people`, 500, 'boom')
  await user.type(search, 'r')
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: t('app.cancel') }))
  expect(screen.queryByRole('textbox', { name: label('findPerson') })).toBeNull()
})

it('says when the actor has no people', async () => {
  mockApi('get', `${BASE}/assignments`, page([]))
  mockApi('get', `${BASE}/actors/a-2`, makeActorDetail({ id: 'a-2', people: [] }))
  renderEconomic(
    <Routes>
      <Route path="/d/economic/actors/:id" element={<ActorDetailPage />} />
    </Routes>,
    { route: '/d/economic/actors/a-2' },
  )

  expect(await screen.findByText(label('noPeople'))).toBeInTheDocument()
})

it('says why the actor could not be loaded', async () => {
  mockApiError('get', `${BASE}/actors/a-9`, 404, 'not_found')
  renderEconomic(
    <Routes>
      <Route path="/d/economic/actors/:id" element={<ActorDetailPage />} />
    </Routes>,
    { route: '/d/economic/actors/a-9' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
  expect(screen.queryByRole('heading', { level: 3 })).toBeNull()
})
