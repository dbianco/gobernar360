import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { BOX, FOOD, HOUSING, SHEETS, VISIT } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.parameters.${key}`, options)
const renderParameters = () => renderSocial(<ParametersPage />, { level: 'admin' })
const section = (key: string) =>
  within(screen.getByRole('heading', { name: label(key) }).closest('section') as HTMLElement)

it('lists the catalogs of the municipality', async () => {
  renderParameters()

  expect(await screen.findByText(VISIT.name)).toBeInTheDocument()
  expect(section('categories').getByText(HOUSING.name)).toBeInTheDocument()
  const row = within(screen.getByRole('row', { name: new RegExp(BOX.name) }))
  expect(row.getByText(FOOD.name)).toBeInTheDocument()
  expect(row.getByText(BOX.description)).toBeInTheDocument()
})

it('adds an intervention type', async () => {
  const requests = mockApi('post', `${BASE}/intervention-types`, { id: 'it-9', name: 'x' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await screen.findByText(VISIT.name)
  await user.type(screen.getByLabelText(label('newInterventionType')), 'Acompañamiento')
  await user.click(section('interventionTypes').getByRole('button', { name: t('app.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Acompañamiento' })
})

it('creates a benefit from the form', async () => {
  const requests = mockApi('post', `${BASE}/benefits`, BOX, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addBenefit') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Frazadas')
  await user.type(form.getByRole('textbox', { name: label('description') }), 'De invierno')
  await user.selectOptions(form.getByLabelText(label('category')), HOUSING.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    category_id: HOUSING.id,
    name: 'Frazadas',
    description: 'De invierno',
  })
})

it('edits a benefit', async () => {
  const requests = mockApi('patch', `${BASE}/benefits/${BOX.id}`, BOX)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: BOX.name }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(label('category'))).toHaveValue(FOOD.id)
  const name = form.getByRole('textbox', { name: label('name') })
  await user.clear(name)
  await user.type(name, 'Bolsón')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    category_id: FOOD.id,
    name: 'Bolsón',
    description: BOX.description,
  })
})

it('explains that a benefit already delivered cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/benefits/${SHEETS.id}`, 409, 'in_use')
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: SHEETS.name }) }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('shows an error instead of empty lists when loading fails', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/benefits`, 500, 'generic')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
})

it('renames and deletes catalog items', async () => {
  const renamed = mockApi('patch', `${BASE}/intervention-types/${VISIT.id}`, {})
  const deleted = mockApi('delete', `${BASE}/benefit-categories/${HOUSING.id}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('app.list.renameNamed', { name: VISIT.name }) }),
  )
  const field = screen.getByRole('textbox', {
    name: t('app.list.renameNamed', { name: VISIT.name }),
  })
  await user.clear(field)
  await user.type(field, 'Visita{Enter}')
  await user.click(
    await screen.findByRole('button', { name: t('app.list.deleteNamed', { name: HOUSING.name }) }),
  )

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(renamed[0].body).toEqual({ name: 'Visita' })
})

it('asks for a category before benefits, says when there are none and closes the form', async () => {
  const view = renderParameters()
  mockApi('get', `${BASE}/benefit-categories`, [])
  expect(await screen.findByText(label('needsCategory'))).toBeInTheDocument()
  view.unmount()

  renderParameters()
  mockApi('get', `${BASE}/benefits`, [])
  const user = userEvent.setup()
  expect(await screen.findByText(label('noBenefits'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('addBenefit') }))
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
