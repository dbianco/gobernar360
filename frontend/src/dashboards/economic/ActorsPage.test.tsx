import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { ActorsPage } from './ActorsPage'
import { INDUSTRY, makeActor, page } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string) => t(`economic.actors.${key}`)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists the actors with their type and sector', async () => {
  mockApi('get', `${BASE}/actors`, page([makeActor(), makeActor({ id: 'a-2', name: 'Taller', actor_type: null, sector: null, cuit: '' })]))
  renderEconomic(<ActorsPage />)

  const row = within(await screen.findByRole('row', { name: /Panadería La Espiga/ }))
  expect(row.getByText('Comercio')).toBeInTheDocument()
  expect(row.getByText('Alimentos')).toBeInTheDocument()
  expect(row.getByText('30-71111111-8')).toBeInTheDocument()
  expect(row.getByRole('link', { name: 'Panadería La Espiga' })).toHaveAttribute(
    'href',
    '/d/economic/actors/a-1',
  )
})

it('searches and filters on the server', async () => {
  const requests = mockApi('get', `${BASE}/actors`, page([makeActor()]))
  renderEconomic(<ActorsPage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Panadería/ })
  await user.type(screen.getByRole('textbox', { name: t('app.search') }), 'pan')
  await waitFor(() => expect(last(requests).url.searchParams.get('q')).toBe('pan'))
  await user.selectOptions(screen.getByLabelText(label('type')), INDUSTRY.id)

  await waitFor(() =>
    expect(last(requests).url.searchParams.get('actor_type_id')).toBe(INDUSTRY.id),
  )
  expect(last(requests).url.searchParams.get('limit')).toBe('50')
})

it('moves to the next page', async () => {
  const requests = mockApi('get', `${BASE}/actors`, page([makeActor()], 120))
  renderEconomic(<ActorsPage />)
  const user = userEvent.setup()

  expect(await screen.findByText('1–50 de 120')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  await waitFor(() => expect(last(requests).url.searchParams.get('offset')).toBe('50'))
  expect(await screen.findByText('51–100 de 120')).toBeInTheDocument()
})

it('hides the create button from viewers and says when nothing matches', async () => {
  mockApi('get', `${BASE}/actors`, page([]))
  renderEconomic(<ActorsPage />, { level: 'viewer' })

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})

it('creates an actor from the form', async () => {
  mockApi('get', `${BASE}/actors`, page([]))
  const requests = mockApi('post', `${BASE}/actors`, makeActor(), 201)
  renderEconomic(<ActorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'Tornería Giménez')
  await user.selectOptions(form.getByLabelText(label('type')), INDUSTRY.id)
  await user.type(form.getByRole('textbox', { name: label('cuit') }), '20-28888888-3')
  await user.type(form.getByLabelText(label('employees')), '5')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Tornería Giménez',
    actor_type_id: INDUSTRY.id,
    sector_id: null,
    cuit: '20288888883',
    address: '',
    phone: '',
    email: '',
    employee_count: 5,
    notes: '',
  })
})

it('rejects a malformed CUIT without calling the server', async () => {
  mockApi('get', `${BASE}/actors`, page([]))
  const requests = mockApi('post', `${BASE}/actors`, makeActor(), 201)
  renderEconomic(<ActorsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: label('name') }), 'x')
  await user.type(form.getByRole('textbox', { name: label('cuit') }), '123')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  expect(await form.findByText(label('cuitInvalid'))).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})
