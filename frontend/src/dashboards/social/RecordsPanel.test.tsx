import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { answerConfirm } from '../../test/confirm'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { RecordsPanel } from './RecordsPanel'
import { BOX, makeDelivery, makeIntervention, page, VISIT } from './testData'
import { BASE, renderSocial } from './testRender'

const delivery = (key: string, options = {}) => t(`social.deliveries.${key}`, options)
const intervention = (key: string, options = {}) => t(`social.interventions.${key}`, options)

function renderPanel(
  records: { deliveries?: unknown[]; interventions?: unknown[]; total?: number } = {},
  scope: { person_id: string } | { household_id: string } = { person_id: 'sp-1' },
) {
  const deliveries = records.deliveries ?? []
  const interventions = records.interventions ?? []
  mockApi('get', `${BASE}/deliveries`, page(deliveries, records.total ?? deliveries.length))
  mockApi('get', `${BASE}/interventions`, page(interventions))
  return renderSocial(<RecordsPanel scope={scope} canEdit />)
}

it('says that it shows only the most recent records', async () => {
  renderPanel({ deliveries: [makeDelivery()], total: 250 })

  expect(await screen.findByText(t('social.mostRecent', { count: 1 }))).toBeInTheDocument()
})

it('says why the history cannot be loaded', async () => {
  mockApiError('get', `${BASE}/deliveries`, 500, 'boom')
  mockApi('get', `${BASE}/interventions`, page([]))
  renderSocial(<RecordsPanel scope={{ person_id: 'sp-1' }} canEdit />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(await screen.findByText(intervention('empty'))).toBeInTheDocument()
})

it('offers no adding in a household history, and names the person of each record', async () => {
  renderPanel(
    { deliveries: [makeDelivery()], interventions: [makeIntervention({ performed_by: '' })] },
    { household_id: 'h-1' },
  )

  expect(
    await screen.findByRole('heading', { name: delivery('householdTitle') }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: delivery('add') })).toBeNull()
  expect(screen.queryByRole('button', { name: intervention('add') })).toBeNull()
  const row = within(await screen.findByRole('row', { name: new RegExp(VISIT.name) }))
  expect(row.getByRole('link', { name: 'Pérez, Juana' })).toBeInTheDocument()
  // Nobody signed it.
  expect(row.getByText(t('app.none'))).toBeInTheDocument()
})

it('closes the add forms with Escape', async () => {
  renderPanel()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: delivery('add') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: intervention('add') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says when there is nothing to deliver or to record', async () => {
  renderPanel()
  mockApi('get', `${BASE}/benefits`, [])
  mockApi('get', `${BASE}/intervention-types`, [])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: delivery('add') }))
  expect(
    await within(screen.getByRole('dialog')).findByText(delivery('noBenefits')),
  ).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: intervention('add') }))
  expect(
    await within(screen.getByRole('dialog')).findByText(intervention('noTypes')),
  ).toBeInTheDocument()
})

it('says why the catalogs cannot be loaded', async () => {
  renderPanel()
  mockApiError('get', `${BASE}/benefits`, 500, 'boom')
  mockApiError('get', `${BASE}/intervention-types`, 500, 'boom')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: delivery('add') }))
  expect(
    await within(screen.getByRole('dialog')).findByText(t('errors.generic')),
  ).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(screen.getByRole('button', { name: intervention('add') }))
  expect(
    await within(screen.getByRole('dialog')).findByText(t('errors.generic')),
  ).toBeInTheDocument()
})

it('keeps the forms open and says why saving failed', async () => {
  renderPanel({ deliveries: [makeDelivery()], interventions: [makeIntervention()] })
  mockApiError('patch', `${BASE}/deliveries/d-1`, 422, 'validation_error')
  mockApiError('patch', `${BASE}/interventions/i-1`, 422, 'future_month')
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: delivery('editNamed', { name: BOX.name }) }),
  )
  let form = within(await screen.findByRole('dialog'))
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.validation_error'))).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(
    screen.getByRole('button', { name: intervention('editNamed', { name: VISIT.name }) }),
  )
  form = within(await screen.findByRole('dialog'))
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.future_month'))).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('keeps records whose deletion is not confirmed, and says why one failed', async () => {
  const deletedDelivery = mockApi('delete', `${BASE}/deliveries/d-1`, null, 204)
  renderPanel({ deliveries: [makeDelivery()], interventions: [makeIntervention()] })
  mockApiError('delete', `${BASE}/interventions/i-1`, 409, 'in_use')
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: delivery('deleteNamed', { name: BOX.name }) }),
  )
  await answerConfirm(user, false)
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deletedDelivery).toHaveLength(0)

  await user.click(
    screen.getByRole('button', { name: intervention('deleteNamed', { name: VISIT.name }) }),
  )
  await answerConfirm(user, false)
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

  await user.click(
    screen.getByRole('button', { name: intervention('deleteNamed', { name: VISIT.name }) }),
  )
  await answerConfirm(user, true)
  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('says why deleting a delivery failed', async () => {
  renderPanel({ deliveries: [makeDelivery()] })
  mockApiError('delete', `${BASE}/deliveries/d-1`, 409, 'in_use')
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: delivery('deleteNamed', { name: BOX.name }) }),
  )
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})
