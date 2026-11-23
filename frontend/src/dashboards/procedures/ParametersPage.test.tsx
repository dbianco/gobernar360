import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { renameThenDelete } from '../../test/catalog'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { OBRAS, RENAPER, RENTAS, RENTAS_SOURCE } from './testData'
import { BASE, renderProcedures } from './testRender'

const label = (key: string, options = {}) => t(`procedures.parameters.${key}`, options)
const renderParameters = () => renderProcedures(<ParametersPage />, { level: 'admin' })

it('lists areas and sources with their level and area', async () => {
  renderParameters()

  const municipal = within(await screen.findByRole('row', { name: /Rentas municipal/ }))
  expect(municipal.getByText(t('procedures.levels.municipal'))).toBeInTheDocument()
  expect(municipal.getByText(RENTAS.name)).toBeInTheDocument()
  const national = within(screen.getByRole('row', { name: /RENAPER/ }))
  expect(national.getByText(t('procedures.levels.national'))).toBeInTheDocument()
  expect(screen.getByText(OBRAS.name)).toBeInTheDocument()
})

it('adds an area', async () => {
  const requests = mockApi('post', `${BASE}/areas`, { id: 'ar-9', name: 'x' }, 201)
  renderParameters()

  await userEvent.type(await screen.findByLabelText(label('newArea')), 'Tránsito{Enter}')

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'Tránsito' })
})

it('creates a municipal source with its area', async () => {
  const requests = mockApi('post', `${BASE}/sources`, RENTAS_SOURCE, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addSource') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Catastro municipal')
  await user.selectOptions(form.getByLabelText(label('area')), OBRAS.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Catastro municipal',
    level: 'municipal',
    area_id: OBRAS.id,
  })
})

it('offers an area only for municipal sources', async () => {
  const requests = mockApi('post', `${BASE}/sources`, RENAPER, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addSource') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'ANSES')
  await user.selectOptions(form.getByLabelText(label('area')), OBRAS.id)
  await user.selectOptions(form.getByLabelText(label('level')), 'national')
  expect(form.queryByLabelText(label('area'))).not.toBeInTheDocument()
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'ANSES', level: 'national', area_id: null })
})

it('edits a source', async () => {
  const requests = mockApi('patch', `${BASE}/sources/${RENAPER.id}`, RENAPER)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('editNamed', { name: 'RENAPER' }) }))
  const form = within(await screen.findByRole('dialog'))
  const name = form.getByRole('textbox', { name: label('name') })
  expect(name).toHaveValue('RENAPER')
  await user.type(name, ' Nación')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ name: 'RENAPER Nación', level: 'national', area_id: null })
})

it('says why a source in use cannot be deleted', async () => {
  mockApiError('delete', `${BASE}/sources/${RENAPER.id}`, 409, 'in_use')
  renderParameters()

  await userEvent.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: 'RENAPER' }) }),
  )

  expect(await screen.findByRole('alert')).toHaveTextContent(t('errors.in_use'))
})

it.each([['/areas', RENTAS.id, RENTAS.name]])('renames and deletes items of %s', async (path, id, name) => {
  const renamed = mockApi('patch', `${BASE}${path}/${id}`, {})
  const deleted = mockApi('delete', `${BASE}${path}/${id}`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await renameThenDelete(user, name, 'Nuevo nombre')

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(renamed[0].body).toEqual({ name: 'Nuevo nombre' })
})

it('closes the form with Escape without saving', async () => {
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addSource') }))
  await screen.findByRole('dialog', { name: label('addSource') })
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says when there are no sources, and keeps the form open when saving fails', async () => {
  mockApiError('post', `${BASE}/sources`, 409, 'conflict')
  renderParameters()
  mockApi('get', `${BASE}/sources`, [])
  const user = userEvent.setup()

  expect(await screen.findByText(label('noSources'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('addSource') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Catastro municipal')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()
})

it('says when the search matches no source', async () => {
  renderParameters()
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /RENAPER/ })
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'zzz')

  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
})

it('says why the catalog cannot be loaded', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/areas`, 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
