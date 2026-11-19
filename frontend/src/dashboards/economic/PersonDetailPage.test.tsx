import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { PersonDetailPage } from './PersonDetailPage'
import { CREDIT, FAIR, makeAssignment, makePersonDetail, page, WORKSHOP } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string, options = {}) => t(`economic.people.${key}`, options)
const assignment = (key: string, options = {}) => t(`economic.assignments.${key}`, options)

function renderDetail(level: AccessLevel = 'editor') {
  mockApi('get', `${BASE}/people/ep-1`, makePersonDetail())
  const assignments = mockApi('get', `${BASE}/assignments`, page([]))
  const view = renderEconomic(
    <Routes>
      <Route path="/d/economic/people/:id" element={<PersonDetailPage />} />
      <Route path="/d/economic/people" element={<p>people list</p>} />
    </Routes>,
    { level, route: '/d/economic/people/ep-1' },
  )
  return { ...view, assignments }
}

it('shows the person, their actors and no write controls to a viewer', async () => {
  const { assignments } = renderDetail('viewer')

  expect(await screen.findByRole('heading', { name: 'Pérez, Juana' })).toBeInTheDocument()
  expect(screen.getByText('12.345.678')).toBeInTheDocument()
  expect(screen.getByText('01/05/1990')).toBeInTheDocument()
  expect(screen.getByText(t('economic.employmentStatuses.self_employed'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Panadería La Espiga' })).toHaveAttribute(
    'href',
    '/d/economic/actors/a-1',
  )
  expect(await screen.findByText(assignment('empty'))).toBeInTheDocument()
  expect(assignments[0].url.searchParams.get('person_id')).toBe('ep-1')
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
  expect(screen.queryByRole('button', { name: label('remove') })).toBeNull()
})

it('edits the common and the economic data', async () => {
  const requests = mockApi('patch', `${BASE}/people/ep-1`, makePersonDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByText(t('people.commonHint'))).toBeInTheDocument()
  await user.clear(form.getByRole('textbox', { name: t('people.dni') }))
  await user.clear(form.getByRole('textbox', { name: label('occupation') }))
  await user.type(form.getByRole('textbox', { name: label('occupation') }), 'Modista')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    person: {
      first_name: 'Juana',
      last_name: 'Pérez',
      dni: null,
      birth_date: '1990-05-01',
      phone: '3472 555222',
      email: '',
      address: 'Belgrano 45',
      neighborhood: 'Centro',
    },
    employment_status: 'self_employed',
    occupation: 'Modista',
  })
})

it('assigns a tool, offering only the tools meant for people', async () => {
  const requests = mockApi('post', `${BASE}/assignments`, makeAssignment(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: assignment('add') }))
  const form = within(await screen.findByRole('dialog'))
  // The tools load after the dialog opens.
  await form.findByRole('option', { name: WORKSHOP.name })
  const tool = form.getByLabelText(assignment('tool')) as HTMLSelectElement
  expect([...tool.options].map((option) => option.text)).toEqual([
    assignment('chooseTool'),
    CREDIT.name,
    WORKSHOP.name,
  ])
  expect([...tool.options].map((option) => option.text)).not.toContain(FAIR.name)
  await user.selectOptions(tool, WORKSHOP.id)
  fireEvent.change(form.getByLabelText(assignment('date')), { target: { value: '2026-05-06' } })
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    tool_id: WORKSHOP.id,
    person_id: 'ep-1',
    date: '2026-05-06',
    note: '',
  })
})

it('removes the person from the dashboard after confirming', async () => {
  const requests = mockApi('delete', `${BASE}/people/ep-1`, null, 204)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('remove') }))

  expect(await screen.findByText('people list')).toBeInTheDocument()
  expect(requests).toHaveLength(1)
})
