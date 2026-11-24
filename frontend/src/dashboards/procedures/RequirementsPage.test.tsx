import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { RequirementsPage } from './RequirementsPage'
import { DNI, FORM, FREE_DEBT, RENTAS_SOURCE } from './testData'
import { BASE, renderProcedures } from './testRender'

const label = (key: string, options = {}) => t(`procedures.requirements.${key}`, options)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists requirements with their source and how many procedures ask for them', async () => {
  renderProcedures(<RequirementsPage />)

  const debt = within(await screen.findByRole('row', { name: /Libre deuda municipal/ }))
  expect(debt.getByText('Rentas municipal')).toBeInTheDocument()
  expect(debt.getByText(t('procedures.levels.municipal'))).toBeInTheDocument()
  expect(debt.getByText('4')).toBeInTheDocument()
  const form = within(screen.getByRole('row', { name: /Formulario de solicitud/ }))
  expect(form.getByText(label('noSource'))).toBeInTheDocument()
})

it('searches on the server', async () => {
  const { requests } = renderProcedures(<RequirementsPage />)

  await screen.findByRole('row', { name: /DNI/ })
  await userEvent.type(screen.getByRole('textbox', { name: label('search') }), 'libre')

  await waitFor(() => expect(last(requests.requirements).url.searchParams.get('q')).toBe('libre'))
})

it('lets an editor add a requirement with its source', async () => {
  const requests = mockApi('post', `${BASE}/requirements`, FREE_DEBT, 201)
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Plano aprobado')
  await user.type(form.getByRole('textbox', { name: label('description') }), 'Visado.')
  await user.selectOptions(form.getByLabelText(label('sourceField')), RENTAS_SOURCE.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Plano aprobado',
    description: 'Visado.',
    source_id: RENTAS_SOURCE.id,
  })
})

it('lets an editor remove the source of a requirement', async () => {
  const requests = mockApi('patch', `${BASE}/requirements/${DNI.id}`, DNI)
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'DNI' }) }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(form.getByLabelText(label('sourceField')), '')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'DNI', description: '', source_id: null })
})

it('says why a requirement in use cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/requirements/${DNI.id}`, 409, 'in_use')
  renderProcedures(<RequirementsPage />)

  await userEvent.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: 'DNI' }) }),
  )

  expect(await screen.findByRole('alert')).toHaveTextContent(t('errors.in_use'))
})

it('gives a viewer no way to change requirements', async () => {
  renderProcedures(<RequirementsPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: new RegExp(FORM.name) })

  expect(screen.queryByRole('button', { name: label('add') })).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: label('editNamed', { name: 'DNI' }) }),
  ).not.toBeInTheDocument()
})

it('says so when nothing is loaded yet', async () => {
  renderProcedures(<RequirementsPage />)
  mockApi('get', `${BASE}/requirements`, [])

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
})

it('says when there are no requirements, reports a failed load and closes the form', async () => {
  const view = renderProcedures(<RequirementsPage />)
  mockApi('get', `${BASE}/requirements`, [])
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  view.unmount()

  const second = renderProcedures(<RequirementsPage />)
  mockApiError('get', `${BASE}/requirements`, 500, 'generic')
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  second.unmount()

  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: DNI.name }) }),
  )
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
