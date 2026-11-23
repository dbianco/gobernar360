import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { PersonDetailPage } from './PersonDetailPage'
import {
  BOX,
  LUIS,
  makeDelivery,
  makeIntervention,
  makePerson,
  page,
  SECRET,
  SHEETS,
  VISIT,
} from './testData'
import { BASE, renderSocial } from './testRender'
import { answerConfirm } from '../../test/confirm'

const label = (key: string, options = {}) => t(`social.people.${key}`, options)
const delivery = (key: string, options = {}) => t(`social.deliveries.${key}`, options)
const intervention = (key: string, options = {}) => t(`social.interventions.${key}`, options)

function renderDetail(
  level: AccessLevel = 'editor',
  records: { deliveries?: unknown[]; interventions?: unknown[] } = {},
) {
  mockApi('get', `${BASE}/people/sp-1`, makePerson())
  const deliveries = mockApi('get', `${BASE}/deliveries`, page(records.deliveries ?? []))
  const interventions = mockApi('get', `${BASE}/interventions`, page(records.interventions ?? []))
  const view = renderSocial(
    <Routes>
      <Route path="/d/social/people/:id" element={<PersonDetailPage />} />
      <Route path="/d/social/people" element={<p>people list</p>} />
    </Routes>,
    { level, route: '/d/social/people/sp-1' },
  )
  return { ...view, deliveries, interventions }
}

it('shows the person, their household and their history', async () => {
  const { deliveries, interventions } = renderDetail('editor', {
    deliveries: [makeDelivery()],
    interventions: [makeIntervention()],
  })

  expect(await screen.findByRole('heading', { name: 'Pérez, Juana' })).toBeInTheDocument()
  expect(screen.getByText('12.345.678')).toBeInTheDocument()
  expect(screen.getByText('01/05/1990')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Familia Pérez' })).toHaveAttribute(
    'href',
    '/d/social/households/h-1',
  )
  expect(screen.getByText(t('social.relationships.head'))).toBeInTheDocument()
  const delivered = within(await screen.findByRole('row', { name: new RegExp(BOX.name) }))
  expect(delivered.getByText('10/03/2026')).toBeInTheDocument()
  expect(delivered.getByText('Retira la hija')).toBeInTheDocument()
  const done = within(await screen.findByRole('row', { name: new RegExp(VISIT.name) }))
  expect(done.getByText(SECRET)).toBeInTheDocument()
  expect(done.getByText('Lic. Marta Ruiz')).toBeInTheDocument()
  expect(deliveries[0].url.searchParams.get('person_id')).toBe('sp-1')
  expect(interventions[0].url.searchParams.get('person_id')).toBe('sp-1')
})

it('keeps the description and the write controls from a viewer', async () => {
  renderDetail('viewer', {
    deliveries: [makeDelivery()],
    interventions: [makeIntervention({ description: null })],
  })

  const done = within(await screen.findByRole('row', { name: new RegExp(VISIT.name) }))
  expect(done.getByText(t('social.reserved'))).toBeInTheDocument()
  expect(screen.queryByText(SECRET)).toBeNull()
  expect(screen.getByText(t('social.reservedHint'))).toBeInTheDocument()
  for (const name of [t('app.edit'), label('remove'), delivery('add'), intervention('add')]) {
    expect(screen.queryByRole('button', { name })).toBeNull()
  }
  expect(
    screen.queryByRole('button', { name: delivery('deleteNamed', { name: BOX.name }) }),
  ).toBeNull()
})

it('edits the registry data of the person', async () => {
  const requests = mockApi('patch', `${BASE}/people/sp-1`, makePerson())
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByText(t('people.commonHint'))).toBeInTheDocument()
  await user.clear(form.getByRole('textbox', { name: t('people.neighborhood') }))
  await user.type(form.getByRole('textbox', { name: t('people.neighborhood') }), 'Sur')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    person: {
      first_name: 'Juana',
      last_name: 'Pérez',
      dni: '12345678',
      birth_date: '1990-05-01',
      phone: '3472 555111',
      email: '',
      address: 'Belgrano 45',
      neighborhood: 'Sur',
    },
  })
})

it('records a delivery for the person', async () => {
  const requests = mockApi('post', `${BASE}/deliveries`, makeDelivery(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: delivery('add') }))
  const form = within(await screen.findByRole('dialog'))
  await form.findByRole('option', { name: new RegExp(SHEETS.name) })
  await user.selectOptions(form.getByLabelText(delivery('benefit')), SHEETS.id)
  fireEvent.change(form.getByLabelText(delivery('date')), { target: { value: '2026-05-06' } })
  const quantity = form.getByLabelText(delivery('quantity'))
  await user.clear(quantity)
  await user.type(quantity, '12')
  await user.type(form.getByRole('textbox', { name: delivery('note') }), 'Para el techo')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    benefit_id: SHEETS.id,
    person_id: 'sp-1',
    date: '2026-05-06',
    quantity: 12,
    note: 'Para el techo',
  })
})

it('corrects a delivery without changing who received what', async () => {
  const requests = mockApi('patch', `${BASE}/deliveries/d-1`, makeDelivery())
  renderDetail('editor', { deliveries: [makeDelivery()] })
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: delivery('editNamed', { name: BOX.name }) }),
  )
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByLabelText(delivery('benefit'))).toBeDisabled()
  const quantity = form.getByLabelText(delivery('quantity'))
  await user.clear(quantity)
  await user.type(quantity, '3')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ date: '2026-03-10', quantity: 3, note: 'Retira la hija' })
})

it('records an intervention, signed by the member by default', async () => {
  const requests = mockApi('post', `${BASE}/interventions`, makeIntervention(), 201)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: intervention('add') }))
  const form = within(await screen.findByRole('dialog'))
  await form.findByRole('option', { name: VISIT.name })
  await user.selectOptions(form.getByLabelText(intervention('type')), VISIT.id)
  fireEvent.change(form.getByLabelText(intervention('date')), { target: { value: '2026-05-06' } })
  expect(form.getByRole('textbox', { name: intervention('performedBy') })).toHaveValue('Ana Gómez')
  expect(form.getByText(intervention('descriptionHint'))).toBeInTheDocument()
  await user.type(form.getByRole('textbox', { name: intervention('description') }), 'Sin novedades')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    intervention_type_id: VISIT.id,
    person_id: 'sp-1',
    date: '2026-05-06',
    description: 'Sin novedades',
    performed_by: 'Ana Gómez',
  })
})

it('deletes an intervention after confirming', async () => {
  const requests = mockApi('delete', `${BASE}/interventions/i-1`, null, 204)
  renderDetail('editor', { interventions: [makeIntervention()] })
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: intervention('deleteNamed', { name: VISIT.name }) }),
  )
  await answerConfirm(user, true)

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('removes the person from the dashboard after confirming', async () => {
  const requests = mockApi('delete', `${BASE}/people/sp-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('remove') }))
  const question = await answerConfirm(user, true)

  expect(await screen.findByText('people list')).toBeInTheDocument()
  expect(requests).toHaveLength(1)
  expect(question).toContain(label('deleteConfirm', { name: 'Pérez, Juana' }))
})

it('keeps it when the deletion is not confirmed', async () => {
  const deleted = mockApi('delete', `${BASE}/people/sp-1`, null, 204)
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('remove') }))
  await answerConfirm(user, false)

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(deleted).toHaveLength(0)
})

it('says why the deletion failed and stays', async () => {
  mockApiError('delete', `${BASE}/people/sp-1`, 409, 'in_use')
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('remove') }))
  await answerConfirm(user, true)

  expect(await screen.findByText(t('errors.in_use'))).toBeInTheDocument()
})

it('closes the edit form with Escape', async () => {
  renderDetail()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.edit') }))
  await screen.findByRole('dialog')
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('says when the person belongs to no household', async () => {
  mockApi('get', `${BASE}/people/sp-2`, LUIS)
  mockApi('get', `${BASE}/deliveries`, page([]))
  mockApi('get', `${BASE}/interventions`, page([]))
  renderSocial(
    <Routes>
      <Route path="/d/social/people/:id" element={<PersonDetailPage />} />
    </Routes>,
    { route: '/d/social/people/sp-2' },
  )

  expect(await screen.findByText(label('noHousehold'))).toBeInTheDocument()
})

it('says why the person cannot be loaded', async () => {
  mockApiError('get', `${BASE}/people/sp-9`, 404, 'not_found')
  renderSocial(
    <Routes>
      <Route path="/d/social/people/:id" element={<PersonDetailPage />} />
    </Routes>,
    { route: '/d/social/people/sp-9' },
  )

  expect(await screen.findByText(t('errors.not_found'))).toBeInTheDocument()
})
