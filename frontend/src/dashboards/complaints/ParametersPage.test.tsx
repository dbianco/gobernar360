import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { ParametersPage } from './ParametersPage'
import { LAMP, WORKS } from './testData'
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
