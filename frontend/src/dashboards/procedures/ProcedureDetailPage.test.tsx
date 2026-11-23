import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProcedureDetailPage } from './ProcedureDetailPage'
import { FORM, makeDetail, makeLink } from './testData'
import { BASE, renderProcedures } from './testRender'
import type { ProcedureDetail } from './types'

const label = (key: string, options = {}) => t(`procedures.detail.${key}`, options)
const URL = `${BASE}/procedures/pr-1`

function renderDetail(detail: ProcedureDetail = makeDetail(), level: AccessLevel = 'editor') {
  mockApi('get', URL, detail)
  return renderProcedures(
    <Routes>
      <Route path="/d/procedures/procedures/:id" element={<ProcedureDetailPage />} />
      <Route path="/d/procedures/procedures" element={<p>list</p>} />
    </Routes>,
    { level, route: '/d/procedures/procedures/pr-1' },
  )
}

it('shows the procedure and what it asks for, with the source of each requirement', async () => {
  renderDetail(makeDetail({ channel: 'both', url: 'https://muni.example/hab' }))

  expect(await screen.findByRole('heading', { name: 'Habilitación comercial' })).toBeInTheDocument()
  expect(screen.getByText(t('procedures.audiences.organizations'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'https://muni.example/hab' })).toHaveAttribute(
    'rel',
    'noopener noreferrer',
  )
  const dni = within(screen.getByRole('row', { name: /DNI/ }))
  expect(dni.getByText('RENAPER')).toBeInTheDocument()
  expect(dni.getByText(label('optional'))).toBeInTheDocument()
  expect(dni.getByText(t('procedures.formats.digital'))).toBeInTheDocument()
  expect(dni.getByText('Copia.')).toBeInTheDocument()
  const debt = within(screen.getByRole('row', { name: /Libre deuda municipal/ }))
  expect(debt.getByText(t('app.yes'))).toBeInTheDocument()
})

it('marks a procedure that is no longer offered', async () => {
  renderDetail(makeDetail({ is_active: false }))

  expect(await screen.findByText(t('procedures.list.inactive'))).toBeInTheDocument()
})

it('offers only the requirements the procedure does not ask for yet', async () => {
  const requests = mockApi('post', `${URL}/requirements`, {}, 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addRequirement') }))
  const form = within(await screen.findByRole('dialog'))
  const select = form.getByLabelText(label('requirement'))
  expect(within(select).getAllByRole('option').map((option) => option.textContent)).toEqual([
    FORM.name,
  ])
  await user.click(form.getByRole('checkbox', { name: label('mandatory') }))
  await user.selectOptions(form.getByLabelText(label('format')), 'digital')
  await user.type(form.getByRole('textbox', { name: label('note') }), 'Firmado.')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    requirement_id: FORM.id,
    mandatory: false,
    format: 'digital',
    note: 'Firmado.',
  })
})

it('changes how a requirement is asked for', async () => {
  const requests = mockApi('patch', `${URL}/requirements/ln-1`, {})
  renderDetail()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: 'Libre deuda municipal' }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.queryByLabelText(label('requirement'))).not.toBeInTheDocument()
  await user.selectOptions(form.getByLabelText(label('format')), 'digital')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ mandatory: true, format: 'digital', note: '' })
})

it('removes a requirement from the procedure', async () => {
  const requests = mockApi('delete', `${URL}/requirements/ln-2`, null, 204)
  renderDetail()

  await userEvent.click(
    await screen.findByRole('button', { name: label('removeNamed', { name: 'DNI' }) }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('edits the procedure, clearing the cost when it becomes free', async () => {
  const requests = mockApi('patch', URL, makeDetail())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('edit') }))
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(t('procedures.form.cost'))).toHaveValue('25000')
  await user.click(form.getByRole('checkbox', { name: t('procedures.form.isFree') }))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ is_free: true, cost: null, duration_days: 20 })
})

it('deletes the procedure after confirming and returns to the list', async () => {
  const requests = mockApi('delete', URL, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('delete') }))
  await user.click(await screen.findByRole('button', { name: t('app.confirm') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(await screen.findByText('list')).toBeInTheDocument()
})

it('is read-only for a viewer', async () => {
  renderDetail(makeDetail(), 'viewer')

  await screen.findByRole('heading', { name: 'Habilitación comercial' })

  for (const name of [label('edit'), label('delete'), label('addRequirement')]) {
    expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  }
  expect(
    screen.queryByRole('button', { name: label('removeNamed', { name: 'DNI' }) }),
  ).not.toBeInTheDocument()
})

it('says so when the procedure asks for nothing yet', async () => {
  renderDetail(makeDetail({ requirements: [] }))

  expect(await screen.findByText(label('noRequirements'))).toBeInTheDocument()
})

it('does not offer to add a requirement until the list of requirements is known', async () => {
  renderDetail()
  mockApiError('get', `${BASE}/requirements`, 500, 'generic')

  await screen.findByRole('heading', { name: 'Habilitación comercial' })

  expect(screen.getByRole('button', { name: label('addRequirement') })).toBeDisabled()
})

it('writes a single day in the singular', async () => {
  renderDetail(makeDetail({ duration_days: 1 }))

  expect(await screen.findByText('1 día')).toBeInTheDocument()
})

it('leaves blank what the procedure does not say, and flags requirements without source', async () => {
  renderDetail(
    makeDetail({
      duration_days: null,
      annual_volume: null,
      is_active: false,
      requirements: [makeLink({ requirement: FORM })],
    }),
    'viewer',
  )

  expect(await screen.findByText(t('procedures.list.inactive'))).toBeInTheDocument()
  expect(screen.getByText(label('days')).nextElementSibling?.textContent).toBe(t('app.none'))
  expect(screen.getByText(label('volume')).nextElementSibling?.textContent).toBe(t('app.none'))
  expect(screen.getByText(label('noSource'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('delete') })).toBeNull()
})

it('stays on the procedure and says why when it cannot be deleted', async () => {
  mockApiError('delete', URL, 409, 'in_use')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('delete') }))
  await user.click(await screen.findByRole('button', { name: t('app.confirm') }))

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(screen.queryByText('list')).toBeNull()
})

it('opens the form to edit the procedure', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('edit') }))

  expect(await screen.findByRole('dialog')).toBeInTheDocument()
})

it('shows an error when the procedure cannot be loaded', async () => {
  mockApiError('get', URL, 404, 'not_found')
  renderProcedures(
    <Routes>
      <Route path="/d/procedures/procedures/:id" element={<ProcedureDetailPage />} />
    </Routes>,
    { route: '/d/procedures/procedures/pr-1' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})

it('adds the requirement chosen, and keeps the form open when saving fails', async () => {
  const requests = mockApiError('post', `${URL}/requirements`, 409, 'conflict')
  renderDetail(makeDetail({ requirements: [] }))
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addRequirement') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(form.getByLabelText(label('requirement')), FORM.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(requests[0].body).toMatchObject({ requirement_id: FORM.id })
})

it('keeps the procedure form open and says why saving failed', async () => {
  mockApiError('patch', URL, 409, 'conflict')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()
})
