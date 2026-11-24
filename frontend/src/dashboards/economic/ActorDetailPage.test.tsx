import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ActorDetailPage } from './ActorDetailPage'
import { CREDIT, FAIR, LUIS, makeActorDetail, makeAssignment, page, WORKSHOP } from './testData'
import { BASE, renderEconomic } from './testRender'

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
  await user.click(
    screen.getByRole('button', { name: label('linkNamed', { name: 'Acosta, Luis' }) }),
  )

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
  fireEvent.change(form.getByLabelText(assignment('date')), { target: { value: '2026-04-02' } })
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
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: assignment('deleteNamed', { name: 'Microcrédito productivo' }),
    }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('deletes the actor after confirming and returns to the list', async () => {
  const requests = mockApi('delete', `${BASE}/actors/a-1`, null, 204)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))

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

it('keeps the actor when the deletion is declined or refused', async () => {
  const requests = mockApiError('delete', `${BASE}/actors/a-1`, 409, 'in_use')
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.delete') }))
  expect(requests).toHaveLength(0)
  confirm.mockReturnValue(true)
  await user.click(screen.getByRole('button', { name: t('app.delete') }))

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Panadería La Espiga' })).toBeInTheDocument()
})

it('opens and closes the actor form', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  expect(await screen.findByRole('dialog', { name: label('editTitle') })).toBeInTheDocument()
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('says when nobody matches the search or it fails, and when a link is refused', async () => {
  mockApi('get', `${BASE}/people`, page([]))
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('linkPerson') }))
  await user.type(screen.getByRole('textbox', { name: label('findPerson') }), 'Zz')
  expect(await screen.findByText(label('noMatches'))).toBeInTheDocument()

  mockApiError('get', `${BASE}/people`, 500, 'generic')
  await user.type(screen.getByRole('textbox', { name: label('findPerson') }), 'x')
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('shows why a person could not be linked, and an actor without people', async () => {
  mockApi('get', `${BASE}/actors/a-1`, makeActorDetail({ people: [] }))
  mockApi('get', `${BASE}/assignments`, page([]))
  mockApi('get', `${BASE}/people`, page([LUIS]))
  mockApiError('post', `${BASE}/actors/a-1/people`, 409, 'conflict')
  renderEconomic(
    <Routes>
      <Route path="/d/economic/actors/:id" element={<ActorDetailPage />} />
    </Routes>,
    { route: '/d/economic/actors/a-1' },
  )
  const user = userEvent.setup()

  expect(await screen.findByText(label('noPeople'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('linkPerson') }))
  await user.type(screen.getByRole('textbox', { name: label('findPerson') }), 'Luis')
  await user.click(
    await screen.findByRole('button', {
      name: label('linkNamed', { name: LUIS.person.full_name }),
    }),
  )

  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
})

it('reports an actor that cannot be loaded', async () => {
  mockApiError('get', `${BASE}/actors/a-1`, 404, 'not_found')
  mockApi('get', `${BASE}/assignments`, page([]))
  renderEconomic(
    <Routes>
      <Route path="/d/economic/actors/:id" element={<ActorDetailPage />} />
    </Routes>,
    { route: '/d/economic/actors/a-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})

it('explains when no tool fits, and shows why an assignment failed', async () => {
  mockApiError('post', `${BASE}/assignments`, 422, 'validation_error')
  const view = renderDetail()
  mockApi('get', `${BASE}/tools`, [WORKSHOP])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: assignment('add') }))
  expect(await screen.findByText(assignment('noTools'))).toBeInTheDocument()
  view.unmount()

  const second = renderDetail()
  mockApiError('get', `${BASE}/tools`, 500, 'generic')
  await user.click(await screen.findByRole('button', { name: assignment('add') }))
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  second.unmount()

  renderDetail()
  await user.click(await screen.findByRole('button', { name: assignment('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(await form.findByLabelText(assignment('tool')), FAIR.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.validation_error'))).toBeInTheDocument()
})
