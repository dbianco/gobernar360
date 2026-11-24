import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { ANNUAL, ENERGY, MONTHLY } from './testData'
import { BASE, renderEnvironment } from './testRender'

const label = (key: string) => t(`environment.parameters.${key}`)
const renderParameters = () => renderEnvironment(<ParametersPage />, { level: 'admin' })

it('lists the subcategories and variables of the chosen category', async () => {
  renderParameters()
  const user = userEvent.setup()

  const rename = { name: t('app.list.renameNamed', { name: ENERGY.name }) }
  expect(await screen.findByRole('button', rename)).toBeInTheDocument()
  expect(screen.getByRole('row', { name: new RegExp(MONTHLY.name) })).toBeInTheDocument()
  expect(screen.queryByRole('row', { name: new RegExp(ANNUAL.name) })).toBeNull()

  await user.selectOptions(screen.getByLabelText(label('category')), 'water')

  expect(await screen.findByRole('row', { name: new RegExp(ANNUAL.name) })).toBeInTheDocument()
  expect(screen.queryByRole('button', rename)).toBeNull()
})

it('adds a subcategory to the chosen category', async () => {
  const requests = mockApi('post', `${BASE}/subcategories`, { id: 's-9' }, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(label('category')), 'waste')
  await user.type(screen.getByLabelText(label('newSubcategory')), 'Reciclado')
  await user.click(screen.getByRole('button', { name: t('app.add') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ category: 'waste', name: 'Reciclado' })
})

it('creates a variable from the form', async () => {
  const requests = mockApi('post', `${BASE}/variables`, MONTHLY, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addVariable') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Consumo del corralón')
  await user.type(form.getByRole('textbox', { name: label('unit') }), 'kWh')
  await user.type(form.getByLabelText(label('target')), '800,5')
  await user.selectOptions(form.getByLabelText(label('direction')), 'lower_is_better')
  await user.selectOptions(form.getByLabelText(label('source')), 'external')
  await user.selectOptions(form.getByLabelText(label('aggregation')), 'average')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    subcategory_id: ENERGY.id,
    name: 'Consumo del corralón',
    unit: 'kWh',
    frequency: 'monthly',
    target: '800.5',
    direction: 'lower_is_better',
    source: 'external',
    annual_aggregation: 'average',
  })
})

it('edits a variable without sending its frequency', async () => {
  const requests = mockApi('patch', `${BASE}/variables/${MONTHLY.id}`, MONTHLY)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('editNamed').replace('{{name}}', MONTHLY.name),
    }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(label('frequency'))).toBeDisabled()
  await user.clear(form.getByLabelText(label('target')))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    subcategory_id: ENERGY.id,
    name: MONTHLY.name,
    unit: 'kWh',
    target: null,
    direction: 'lower_is_better',
    source: 'municipal',
    annual_aggregation: 'sum',
  })
})

it('asks for a subcategory before a variable can be added', async () => {
  renderParameters()
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(label('category')), 'air')

  expect(await screen.findByText(label('needsSubcategory'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('addVariable') })).toBeNull()
})

it('explains that a variable with values cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/variables/${MONTHLY.id}`, 409, 'in_use')
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed').replace('{{name}}', MONTHLY.name),
    }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('shows an error instead of empty lists when loading fails', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/variables`, 500, 'generic')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('app.list.empty'))).toBeNull()
})

it('reads a dotted target as thousands and rejects an ambiguous one', async () => {
  const requests = mockApi('post', `${BASE}/variables`, MONTHLY, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addVariable') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Consumo')
  await user.type(form.getByLabelText(label('target')), '1.5')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('environment.invalidNumber'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)

  await user.clear(form.getByLabelText(label('target')))
  await user.type(form.getByLabelText(label('target')), '420.000')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ target: '420000' })
})

const renameTo = async (user: ReturnType<typeof userEvent.setup>, name: string, to: string) => {
  await user.click(await screen.findByRole('button', { name: t('app.list.renameNamed', { name }) }))
  const field = screen.getByRole('textbox', { name: t('app.list.renameNamed', { name }) })
  await user.clear(field)
  await user.type(field, `${to}{Enter}`)
}

it('renames and deletes a subcategory', async () => {
  const renamed = mockApi('patch', `${BASE}/subcategories/${ENERGY.id}`, {})
  const deleted = mockApi('delete', `${BASE}/subcategories/${ENERGY.id}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await renameTo(user, ENERGY.name, 'Energía eléctrica')
  await user.click(
    await screen.findByRole('button', { name: t('app.list.deleteNamed', { name: ENERGY.name }) }),
  )

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(renamed[0].body).toEqual({ name: 'Energía eléctrica' })
})

it('shows a variable without a target as such, says when there are none, and closes its form', async () => {
  const view = renderParameters()
  mockApi('get', `${BASE}/variables`, [{ ...MONTHLY, target: null }])
  const user = userEvent.setup()

  const row = within(await screen.findByRole('row', { name: new RegExp(MONTHLY.name) }))
  expect(row.getByText(t('app.none'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('addVariable') }))
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  view.unmount()

  renderParameters()
  mockApi('get', `${BASE}/variables`, [])
  expect(await screen.findByText(label('noVariables'))).toBeInTheDocument()
})
