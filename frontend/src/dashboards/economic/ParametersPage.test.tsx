import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { CREDIT, FAIR, FINANCE, MICROCREDITS, SHOP, TRAINING } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string, options = {}) => t(`economic.parameters.${key}`, options)
const renderParameters = () => renderEconomic(<ParametersPage />, { level: 'admin' })
const section = (key: string) =>
  within(screen.getByRole('heading', { name: label(key) }).closest('section') as HTMLElement)

it('lists the lists of the municipality and its tools', async () => {
  renderParameters()

  expect(await screen.findByText(SHOP.name)).toBeInTheDocument()
  expect(section('sectors').getByText('Alimentos')).toBeInTheDocument()
  expect(section('categories').getByText(MICROCREDITS.name)).toBeInTheDocument()
  const row = within(screen.getByRole('row', { name: new RegExp(CREDIT.name) }))
  expect(row.getByText(FINANCE.name)).toBeInTheDocument()
  expect(row.getByText(MICROCREDITS.name)).toBeInTheDocument()
  expect(row.getByText(t('economic.audiences.both'))).toBeInTheDocument()
})

it('adds an actor type', async () => {
  const requests = mockApi('post', `${BASE}/actor-types`, { id: 'at-9', name: 'x' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await screen.findByText(SHOP.name)
  await user.type(screen.getByLabelText(label('newActorType')), 'Cooperativa')
  await user.click(section('actorTypes').getByRole('button', { name: t('app.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Cooperativa' })
})

it('adds a subcategory under its category', async () => {
  const requests = mockApi('post', `${BASE}/tool-subcategories`, { id: 'ts-9' }, 201)
  renderParameters()
  const user = userEvent.setup()

  const field = await screen.findByLabelText(label('newSubcategoryFor', { name: TRAINING.name }))
  await user.type(field, 'Oficios{Enter}')

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ category_id: TRAINING.id, name: 'Oficios' })
})

it('creates a tool from the form', async () => {
  const requests = mockApi('post', `${BASE}/tools`, CREDIT, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addTool') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Aval municipal')
  await user.type(form.getByRole('textbox', { name: label('description') }), 'Garantía')
  await user.selectOptions(form.getByLabelText(label('category')), FINANCE.id)
  await user.selectOptions(form.getByLabelText(label('audience')), 'actors')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    category_id: FINANCE.id,
    subcategory_id: null,
    name: 'Aval municipal',
    description: 'Garantía',
    audience: 'actors',
  })
})

it('only offers the subcategories of the chosen category and edits a tool', async () => {
  const requests = mockApi('patch', `${BASE}/tools/${CREDIT.id}`, CREDIT)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: CREDIT.name }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  const subcategory = form.getByLabelText(label('subcategory')) as HTMLSelectElement
  expect(subcategory.value).toBe(MICROCREDITS.id)
  expect([...subcategory.options].map((option) => option.text)).toEqual([
    label('noSubcategory'),
    MICROCREDITS.name,
  ])
  await user.selectOptions(form.getByLabelText(label('category')), TRAINING.id)
  expect(subcategory.value).toBe('')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    category_id: TRAINING.id,
    subcategory_id: null,
    name: CREDIT.name,
    description: CREDIT.description,
    audience: 'both',
  })
})

it('explains that a tool with assignments cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/tools/${FAIR.id}`, 409, 'in_use')
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: FAIR.name }) }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('shows an error instead of empty lists when loading fails', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/tools`, 500, 'generic')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
})

const renameItem = async (user: ReturnType<typeof userEvent.setup>, name: string, to: string) => {
  await user.click(await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }))
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${to}{Enter}`)
}
const deleteItem = async (user: ReturnType<typeof userEvent.setup>, name: string) =>
  user.click(await screen.findByRole('button', { name: t('app.list.deleteNamed', { name }) }))

it('renames and deletes list items, categories and subcategories', async () => {
  const sector = mockApi('patch', `${BASE}/sectors/se-1`, {})
  const actorType = mockApi('delete', `${BASE}/actor-types/at-2`, null, 204)
  const category = mockApi('patch', `${BASE}/tool-categories/${TRAINING.id}`, {})
  const categoryAdded = mockApi('post', `${BASE}/tool-categories`, {}, 201)
  const categoryDeleted = mockApi('delete', `${BASE}/tool-categories/${FINANCE.id}`, null, 204)
  const subcategory = mockApi('patch', `${BASE}/tool-subcategories/ts-2`, {})
  const subcategoryDeleted = mockApi('delete', `${BASE}/tool-subcategories/ts-1`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await renameItem(user, 'Alimentos', 'Gastronomía')
  await deleteItem(user, 'Industria')
  await renameItem(user, TRAINING.name, 'Formación')
  await deleteItem(user, FINANCE.name)
  await renameItem(user, 'Cursos', 'Cursos cortos')
  await deleteItem(user, MICROCREDITS.name)
  await user.type(
    screen.getByRole('textbox', { name: label('newCategory') }),
    'Asistencia técnica{Enter}',
  )

  await waitFor(() => expect(categoryAdded).toHaveLength(1))
  expect(sector[0].body).toEqual({ name: 'Gastronomía' })
  expect(actorType).toHaveLength(1)
  expect(category[0].body).toEqual({ name: 'Formación' })
  expect(categoryDeleted).toHaveLength(1)
  expect(subcategory[0].body).toEqual({ name: 'Cursos cortos' })
  expect(subcategoryDeleted).toHaveLength(1)
  expect(categoryAdded[0].body).toEqual({ name: 'Asistencia técnica' })
})

it('closes the tool form without saving', async () => {
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addTool') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('asks for a category before tools, and says when there are no tools yet', async () => {
  const view = renderParameters()
  mockApi('get', `${BASE}/tool-categories`, [])
  mockApi('get', `${BASE}/tools`, [])

  expect(await screen.findByText(label('needsCategory'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('addTool') })).toBeNull()
  view.unmount()

  renderParameters()
  mockApi('get', `${BASE}/tools`, [])
  expect(await screen.findByText(label('noTools'))).toBeInTheDocument()
})
