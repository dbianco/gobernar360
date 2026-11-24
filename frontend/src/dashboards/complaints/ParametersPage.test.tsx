import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { LAMP, LIGHTS, WORKS } from './testData'
import { BASE, renderComplaints } from './testRender'

const label = (key: string, options = {}) => t(`complaints.parameters.${key}`, options)

function renderParameters() {
  return renderComplaints(<ParametersPage />, { level: 'admin', route: '/d/complaints/parameters' })
}

it('lists the types with their area, target and whether they are offered', async () => {
  renderParameters()

  const types = within(await screen.findByRole('table', { name: label('types') }))
  expect(types.getByRole('row', { name: /Luminaria apagada/ })).toHaveTextContent(
    'Alumbrado Público3 días hábiles',
  )
  expect(types.getByRole('row', { name: /Operativo de ramas/ })).toHaveTextContent(
    label('inactive'),
  )
})

it('adds a type routed to an area with its target', async () => {
  const created = mockApi('post', `${BASE}/types`, {}, 201)
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addType') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.type(dialog.getByRole('textbox', { name: label('name') }), 'Semáforo roto')
  await user.selectOptions(dialog.getByLabelText(label('area')), WORKS.id)
  await user.type(dialog.getByRole('textbox', { name: label('targetField') }), '2')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(created).toHaveLength(1))
  expect(created[0].body).toEqual({
    name: 'Semáforo roto',
    area_id: WORKS.id,
    target_days: 2,
    is_active: true,
  })
})

it('retires a type', async () => {
  const changed = mockApi('patch', `${BASE}/types/${LAMP.id}`, {})
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('editNamed', { name: LAMP.name }) }),
  )
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('checkbox', { name: label('isActive') }))
  await user.click(dialog.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(changed).toHaveLength(1))
  expect(changed[0].body).toMatchObject({ is_active: false, target_days: 3 })
})

it('sets the working weekdays and adds a holiday', async () => {
  const weekdays = mockApi('put', `${BASE}/calendar/weekdays`, {})
  const holidays = mockApi('post', `${BASE}/calendar/holidays`, {}, 201)
  renderParameters()
  const user = userEvent.setup()

  const save = await screen.findByRole('button', { name: label('saveWeekdays') })
  expect(save).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: 'Sábado' }))
  await user.click(save)
  await user.type(screen.getByLabelText(label('holidayDate')), '2026-07-09')
  await user.type(screen.getByRole('textbox', { name: label('holidayName') }), 'Independencia')
  await user.click(screen.getByRole('button', { name: label('addHoliday') }))

  await waitFor(() => expect(holidays).toHaveLength(1))
  expect(weekdays[0].body).toEqual({ weekdays: [1, 2, 3, 4, 5, 6] })
  expect(holidays[0].body).toEqual({ date: '2026-07-09', name: 'Independencia' })
  expect(screen.getByRole('row', { name: /Día de la Memoria/ })).toHaveTextContent('24/03/2026')
})

it('adds, renames and deletes areas and zones', async () => {
  const added = mockApi('post', `${BASE}/zones`, {}, 201)
  const renamed = mockApi('patch', `${BASE}/areas/${LIGHTS.id}`, {})
  const deleted = mockApi('delete', `${BASE}/zones/zo-2`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await user.type(await screen.findByRole('textbox', { name: label('newZone') }), 'Sur{Enter}')
  await user.click(
    screen.getByRole('button', { name: t('app.list.renameNamed', { name: LIGHTS.name }) }),
  )
  const field = screen.getByRole('textbox', {
    name: t('app.list.renameNamed', { name: LIGHTS.name }),
  })
  await user.clear(field)
  await user.type(field, 'Alumbrado{Enter}')
  await user.click(
    screen.getByRole('button', { name: t('app.list.deleteNamed', { name: 'Norte' }) }),
  )

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(added[0].body).toEqual({ name: 'Sur' })
  expect(renamed[0].body).toEqual({ name: 'Alumbrado' })
})

it('deletes a type, showing why when it is in use', async () => {
  const deleted = mockApiError('delete', `${BASE}/types/${LAMP.id}`, 409, 'in_use')
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: LAMP.name }) }),
  )

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
  expect(deleted).toHaveLength(1)
})

it('closes the type form without saving', async () => {
  renderParameters()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('addType') }))
  await user.click(
    within(await screen.findByRole('dialog')).getByRole('button', { name: t('app.cancel') }),
  )

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('asks for an area before any type', async () => {
  renderParameters()
  mockApi('get', `${BASE}/areas`, [])
  mockApi('get', `${BASE}/types`, [])

  expect(await screen.findByText(label('needsArea'))).toBeInTheDocument()
  expect(screen.getByText(label('noTypes'))).toBeInTheDocument()
  expect(screen.getByRole('button', { name: label('addType') })).toBeDisabled()
})

it('reports parameters that fail to load', async () => {
  renderParameters()
  mockApiError('get', `${BASE}/zones`, 500, 'generic')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('removes a holiday', async () => {
  const deleted = mockApi('delete', `${BASE}/calendar/holidays/ho-1`, null, 204)
  renderParameters()
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', {
      name: label('deleteHoliday', { name: 'Día de la Memoria 24/03/2026' }),
    }),
  )
  await user.click(screen.getByRole('checkbox', { name: 'Lunes' }))
  await user.click(screen.getByRole('checkbox', { name: 'Lunes' }))

  await waitFor(() => expect(deleted).toHaveLength(1))
  expect(screen.getByRole('button', { name: label('saveWeekdays') })).toBeDisabled()
})

it('shows why a type, the weekdays or a holiday could not be saved', async () => {
  mockApiError('post', `${BASE}/types`, 422, 'validation_error')
  mockApiError('post', `${BASE}/calendar/holidays`, 409, 'conflict')
  renderParameters()
  mockApi('get', `${BASE}/calendar`, { weekdays: [1, 2, 3, 4, 5], holidays: [] })
  const user = userEvent.setup()

  expect(await screen.findByText(label('noHolidays'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('addType') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.type(dialog.getByRole('textbox', { name: label('name') }), 'Otro')
  await user.type(dialog.getByRole('textbox', { name: label('targetField') }), '5')
  await user.click(dialog.getByRole('button', { name: t('app.save') }))
  expect(await dialog.findByText(t('errors.validation_error'))).toBeInTheDocument()
  await user.keyboard('{Escape}')

  await user.type(screen.getByLabelText(label('holidayDate')), '2026-07-09')
  await user.type(screen.getByRole('textbox', { name: label('holidayName') }), 'Independencia')
  await user.click(screen.getByRole('button', { name: label('addHoliday') }))
  expect(await screen.findByText(t('errors.conflict'))).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: label('holidayName') })).toHaveValue('Independencia')
})
