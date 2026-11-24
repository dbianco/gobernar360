import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { DeliveriesPage } from './DeliveriesPage'
import { BOX, LUIS, makeDelivery, page, SHEETS } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.deliveries.${key}`, options)
const YEAR = new Date().getFullYear()

it('lists the deliveries of the year with who received them', async () => {
  const requests = mockApi('get', `${BASE}/deliveries`, page([makeDelivery()]))
  renderSocial(<DeliveriesPage />, { level: 'viewer' })

  const row = within(await screen.findByRole('row', { name: new RegExp(BOX.name) }))
  expect(row.getByRole('link', { name: 'Pérez, Juana' })).toHaveAttribute(
    'href',
    '/d/social/people/sp-1',
  )
  expect(row.getByText('Alimentos')).toBeInTheDocument()
  expect(row.getByText('2')).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/deliveries.csv?year=${YEAR}`,
  )
  expect(screen.queryByRole('button', { name: label('add') })).toBeNull()
  expect(
    screen.queryByRole('button', { name: label('deleteNamed', { name: BOX.name }) }),
  ).toBeNull()
})

it('filters by benefit and year on the server', async () => {
  const requests = mockApi('get', `${BASE}/deliveries`, page([makeDelivery()], 120))
  renderSocial(<DeliveriesPage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: new RegExp(BOX.name) })
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))
  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('offset')).toBe('50'))
  await user.selectOptions(screen.getByLabelText(label('benefit')), SHEETS.id)
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(YEAR - 1))

  await waitFor(() => {
    const params = requests.at(-1)?.url.searchParams
    expect(params?.get('benefit_id')).toBe(SHEETS.id)
    expect(params?.get('year')).toBe(String(YEAR - 1))
    // Changing a filter goes back to the first page.
    expect(params?.get('offset')).toBe('0')
  })
})

it('says so when the year has no deliveries', async () => {
  mockApi('get', `${BASE}/deliveries`, page([]))
  renderSocial(<DeliveriesPage />)

  expect(await screen.findByText(label('emptyYear'))).toBeInTheDocument()
})

it('records a delivery for a person found by search', async () => {
  mockApi('get', `${BASE}/deliveries`, page([]))
  const search = mockApi('get', `${BASE}/people`, page([LUIS]))
  const requests = mockApi('post', `${BASE}/deliveries`, makeDelivery(), 201)
  renderSocial(<DeliveriesPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  expect(form.getByRole('button', { name: t('app.save') })).toBeDisabled()
  await user.type(form.getByRole('textbox', { name: t('social.people.find') }), 'gom')
  await user.click(
    await form.findByRole('button', {
      name: t('social.people.chooseNamed', { name: 'Gómez, Luis' }),
    }),
  )
  expect(search.at(-1)?.url.searchParams.get('q')).toBe('gom')
  expect(form.getByText('Gómez, Luis')).toBeInTheDocument()
  await user.selectOptions(form.getByLabelText(label('benefit')), BOX.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ benefit_id: BOX.id, person_id: 'sp-2', quantity: 1 })
})

it('deletes a delivery after confirming', async () => {
  mockApi('get', `${BASE}/deliveries`, page([makeDelivery()]))
  const requests = mockApi('delete', `${BASE}/deliveries/d-1`, null, 204)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  renderSocial(<DeliveriesPage />)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: label('deleteNamed', { name: BOX.name }) }),
  )

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('explains an empty benefit list and shows why a delivery failed', async () => {
  mockApi('get', `${BASE}/deliveries`, page([]))
  mockApi('get', `${BASE}/people`, page([LUIS]))
  mockApiError('post', `${BASE}/deliveries`, 422, 'validation_error')
  const view = renderSocial(<DeliveriesPage />)
  mockApi('get', `${BASE}/benefits`, [])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('add') }))
  expect(await screen.findByText(label('noBenefits'))).toBeInTheDocument()
  view.unmount()

  const second = renderSocial(<DeliveriesPage />)
  mockApiError('get', `${BASE}/benefits`, 500, 'generic')
  await user.click(await screen.findByRole('button', { name: label('add') }))
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  second.unmount()

  renderSocial(<DeliveriesPage />)
  await user.click(await screen.findByRole('button', { name: label('add') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: t('social.people.find') }), 'gom')
  await user.click(
    await form.findByRole('button', {
      name: t('social.people.chooseNamed', { name: 'Gómez, Luis' }),
    }),
  )
  await user.selectOptions(form.getByLabelText(label('benefit')), BOX.id)
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.validation_error'))).toBeInTheDocument()
})
