import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { IndicatorsPage } from './IndicatorsPage'
import { makeIndicator } from './testData'
import { BASE, renderProjects } from './testRender'

it('shows the current value against the target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('150 / 200 cuadras')).toBeInTheDocument()
  expect(row.getByText('75 %')).toBeInTheDocument()
})

it('shows a dash when the indicator has no target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator({ target: null })])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('—')).toBeInTheDocument()
})

it('hides editing from viewers', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: /Cuadras pavimentadas/ })

  expect(screen.queryByRole('button', { name: t('projects.indicators.add') })).toBeNull()
})

const label = (key: string, options = {}) => t(`projects.indicators.${key}`, options)

it('lets an editor add an indicator, sending empty numbers as null', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  const created = mockApi('post', `${BASE}/indicators`, makeIndicator(), 201)
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(
    form.getByRole('combobox', { name: label('objective') }),
    'Ciudad inclusiva › Reducir el déficit habitacional',
  )
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Cuadras pavimentadas')
  await user.type(form.getByRole('textbox', { name: label('unit') }), 'cuadras')
  await user.type(form.getByRole('spinbutton', { name: label('target') }), '200')
  await user.type(form.getByRole('spinbutton', { name: label('currentValue') }), ' 150.5 ')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toEqual({
    objective_id: 'o-1',
    name: 'Cuadras pavimentadas',
    unit: 'cuadras',
    baseline: null,
    target: '200',
    current_value: '150.5',
  })
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('lets an editor correct an indicator, starting from its values', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const updated = mockApi('patch', `${BASE}/indicators/i-1`, makeIndicator())
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('editNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByRole('combobox', { name: label('objective') })).toHaveValue('o-1')
  expect(form.getByRole('spinbutton', { name: label('baseline') })).toHaveValue(120)
  const current = form.getByRole('spinbutton', { name: label('currentValue') })
  await user.clear(current)
  await user.type(current, '160')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(updated).toHaveLength(1))
  expect(updated[0].body).toEqual({
    objective_id: 'o-1',
    name: 'Cuadras pavimentadas',
    unit: 'cuadras',
    baseline: '120',
    target: '200',
    current_value: '160',
  })
})

it('closes the form without saving when cancelled', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const updated = mockApi('patch', `${BASE}/indicators/i-1`, makeIndicator())
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('editNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(updated).toHaveLength(0)
})

it('shows why the server refused an indicator and keeps the form open', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  mockApiError('post', `${BASE}/indicators`, 422, 'validation_error')
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.selectOptions(form.getByRole('combobox', { name: label('objective') }), 'o-2')
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Luminarias')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(t('errors.validation_error'))).toBeInTheDocument()
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('deletes an indicator', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  const deleted = mockApi('delete', `${BASE}/indicators/i-1`, null, 204)
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed', { name: 'Cuadras pavimentadas' }),
    }),
  )

  await waitFor(() => expect(deleted).toHaveLength(1))
})

it('asks for objectives before indicators can be added', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  renderProjects(<IndicatorsPage />)
  mockApi('get', `${BASE}/objectives`, [])

  expect(await screen.findByText(label('needsObjectives'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('add') })).toBeNull()
  expect(screen.getByText(label('empty'))).toBeInTheDocument()
})

it('writes values without a unit, without a target, or without a value', async () => {
  mockApi('get', `${BASE}/indicators`, [
    makeIndicator({ id: 'i-1', name: 'Sin unidad', unit: '' }),
    makeIndicator({ id: 'i-2', name: 'Sin meta', target: null }),
    makeIndicator({ id: 'i-3', name: 'Sin valor', current_value: null }),
  ])
  renderProjects(<IndicatorsPage />, { level: 'viewer' })

  const noUnit = within(await screen.findByRole('row', { name: /Sin unidad/ }))
  const noTarget = within(screen.getByRole('row', { name: /Sin meta/ }))
  const noValue = within(screen.getByRole('row', { name: /Sin valor/ }))

  expect(noUnit.getByText('150 / 200')).toBeInTheDocument()
  expect(noUnit.getByText('75 %')).toBeInTheDocument()
  expect(noTarget.getByText('150 cuadras')).toBeInTheDocument()
  expect(noValue.getByText('— / 200 cuadras')).toBeInTheDocument()
  expect(noValue.getAllByText('—')).toHaveLength(1)
  expect(screen.queryByRole('button', { name: t('app.edit') })).toBeNull()
})

it('shows an error when the indicators cannot be loaded', async () => {
  mockApiError('get', `${BASE}/indicators`, 500, 'generic')
  renderProjects(<IndicatorsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('says why a deletion failed, and when the search matches nothing', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  mockApiError('delete', `${BASE}/indicators/${makeIndicator().id}`, 409, 'in_use')
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteNamed', { name: makeIndicator().name }),
    }),
  )
  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()

  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'zzz')
  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
})

it('closes the form with Escape', async () => {
  mockApi('get', `${BASE}/indicators`, [])
  renderProjects(<IndicatorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})
