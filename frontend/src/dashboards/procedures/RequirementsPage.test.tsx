import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { RequirementsPage } from './RequirementsPage'
import { DNI, FORM, FREE_DEBT, RENTAS_SOURCE } from './testData'
import { BASE, renderProcedures } from './testRender'

const label = (key: string, options = {}) => t(`procedures.requirements.${key}`, options)

it('lists requirements with their source and how many procedures ask for them', async () => {
  renderProcedures(<RequirementsPage />)

  const debt = within(await screen.findByRole('row', { name: /Libre deuda municipal/ }))
  expect(debt.getByText('Rentas municipal')).toBeInTheDocument()
  expect(debt.getByText(t('procedures.levels.municipal'))).toBeInTheDocument()
  expect(debt.getByText('4')).toBeInTheDocument()
  const form = within(screen.getByRole('row', { name: /Formulario de solicitud/ }))
  expect(form.getByText(label('noSource'))).toBeInTheDocument()
})

it('searches by requirement or source, ignoring accents', async () => {
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()
  await screen.findByRole('row', { name: /DNI/ })
  const search = screen.getByRole('searchbox', { name: t('app.search') })

  await user.type(search, 'RENTAS')

  expect(screen.getByRole('row', { name: /Libre deuda municipal/ })).toBeInTheDocument()
  expect(screen.queryByRole('row', { name: /Formulario de solicitud/ })).toBeNull()
  await user.clear(search)
  await user.type(search, 'no existe')
  expect(await screen.findByText(label('noMatches'))).toBeInTheDocument()
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

it('keeps the form open and says why saving failed, and closes it with Escape', async () => {
  mockApiError('post', `${BASE}/requirements`, 409, 'conflict')
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Plano aprobado')
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says why the requirements cannot be loaded', async () => {
  renderProcedures(<RequirementsPage />)
  mockApiError('get', `${BASE}/requirements`, 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('opens a requirement with what it has, and closes once it is saved', async () => {
  const requests = mockApi('patch', `${BASE}/requirements/${FREE_DEBT.id}`, FREE_DEBT)
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: FREE_DEBT.name }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.queryByRole('alert')).toBeNull()
  expect(form.getByRole('textbox', { name: label('name') })).toHaveValue(FREE_DEBT.name)
  const description = form.getByRole('textbox', { name: label('description') })
  expect(description).toHaveValue(FREE_DEBT.description)
  expect(form.getByText(label('sourceHint'))).toBeInTheDocument()
  const source = form.getByLabelText(label('sourceField'))
  expect(source).toHaveValue(RENTAS_SOURCE.id)
  const options = within(source)
    .getAllByRole('option')
    .map((option) => option.textContent)
  expect(options[0]).toBe(label('noSource'))
  expect(options).toContain(`${RENTAS_SOURCE.name} (${t('procedures.levels.municipal')})`)
  await user.clear(description)
  await user.type(description, 'Con sello.')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(requests[0].body).toEqual({
    name: FREE_DEBT.name,
    description: 'Con sello.',
    source_id: RENTAS_SOURCE.id,
  })
})

it('opens a new requirement empty, without a source, and Cancel closes it', async () => {
  renderProcedures(<RequirementsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByRole('textbox', { name: label('name') })).toHaveValue('')
  expect(form.getByRole('textbox', { name: label('description') })).toHaveValue('')
  expect(form.getByLabelText(label('sourceField'))).toHaveValue('')
  await user.click(form.getByRole('button', { name: t('app.cancel') }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})
