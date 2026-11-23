import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ProceduresPage } from './ProceduresPage'
import { makeProcedure, OBRAS, page, RENTAS } from './testData'
import { BASE, renderProcedures } from './testRender'

const label = (key: string, options = {}) => t(`procedures.list.${key}`, options)
const field = (key: string) => t(`procedures.form.${key}`)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists procedures with their area, channel, cost and figures', async () => {
  mockApi(
    'get',
    `${BASE}/procedures`,
    page([
      makeProcedure(),
      makeProcedure({
        id: 'pr-2',
        name: 'Libre deuda',
        channel: 'online',
        is_free: true,
        cost: null,
        duration_days: null,
        annual_volume: null,
        is_active: false,
      }),
    ]),
  )
  renderProcedures(<ProceduresPage />)

  const shop = within(await screen.findByRole('row', { name: /Habilitación comercial/ }))
  expect(shop.getByRole('link', { name: 'Habilitación comercial' })).toHaveAttribute(
    'href',
    '/d/procedures/procedures/pr-1',
  )
  expect(shop.getByText(RENTAS.name)).toBeInTheDocument()
  expect(shop.getByText(t('procedures.channels.in_person'))).toBeInTheDocument()
  expect(shop.getByText(/\$\s?25\.000/)).toBeInTheDocument()
  expect(shop.getByText(label('daysValue', { count: 20 }))).toBeInTheDocument()
  expect(shop.getByText('180')).toBeInTheDocument()
  const debt = within(screen.getByRole('row', { name: /Libre deuda/ }))
  expect(debt.getByText(label('free'))).toBeInTheDocument()
  expect(debt.getByText(label('inactive'))).toBeInTheDocument()
})

it('searches and filters on the server', async () => {
  const requests = mockApi('get', `${BASE}/procedures`, page([makeProcedure()]))
  renderProcedures(<ProceduresPage />)
  const user = userEvent.setup()

  await screen.findByRole('row', { name: /Habilitación/ })
  expect(last(requests).url.searchParams.get('active')).toBeNull()
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'hab')
  await user.selectOptions(screen.getByLabelText(label('area')), OBRAS.id)
  await user.selectOptions(screen.getByLabelText(label('channel')), 'online')
  await user.selectOptions(screen.getByLabelText(label('state')), 'true')

  await waitFor(() => expect(last(requests).url.searchParams.get('active')).toBe('true'))
  const params = last(requests).url.searchParams
  expect([params.get('q'), params.get('area_id'), params.get('channel'), params.get('limit')]).toEqual(
    ['hab', OBRAS.id, 'online', '10'],
  )
})

it('moves to the next page', async () => {
  const requests = mockApi('get', `${BASE}/procedures`, page([makeProcedure()], 120))
  renderProcedures(<ProceduresPage />)

  expect(await screen.findByText('1–10 de 120')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: t('app.pager.next') }))

  await waitFor(() => expect(last(requests).url.searchParams.get('offset')).toBe('10'))
})

it('lets an editor create a paid procedure', async () => {
  mockApi('get', `${BASE}/procedures`, page([]))
  const requests = mockApi('post', `${BASE}/procedures`, makeProcedure(), 201)
  renderProcedures(<ProceduresPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: field('name') }), 'Permiso de obra')
  await user.selectOptions(form.getByLabelText(field('area')), OBRAS.id)
  await user.selectOptions(form.getByLabelText(field('channel')), 'both')
  await user.type(form.getByRole('textbox', { name: field('url') }), 'https://muni.example/obra')
  expect(form.queryByLabelText(field('cost'))).not.toBeInTheDocument()
  await user.click(form.getByRole('checkbox', { name: field('isFree') }))
  await user.type(form.getByLabelText(field('cost')), '40000')
  await user.type(form.getByLabelText(field('days')), '30')
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    name: 'Permiso de obra',
    description: '',
    area_id: OBRAS.id,
    audience: 'both',
    channel: 'both',
    url: 'https://muni.example/obra',
    is_free: false,
    cost: 40000,
    duration_days: 30,
    annual_volume: null,
    is_active: true,
  })
})

it('does not ask for a link when the procedure is only in person', async () => {
  mockApi('get', `${BASE}/procedures`, page([]))
  renderProcedures(<ProceduresPage />)

  await userEvent.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))

  expect(form.queryByRole('textbox', { name: field('url') })).not.toBeInTheDocument()
})

it('gives a viewer no way to create procedures', async () => {
  mockApi('get', `${BASE}/procedures`, page([makeProcedure()]))
  renderProcedures(<ProceduresPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: /Habilitación/ })

  expect(screen.queryByRole('button', { name: label('create') })).not.toBeInTheDocument()
})

it('says so when nothing matches', async () => {
  mockApi('get', `${BASE}/procedures`, page([]))
  renderProcedures(<ProceduresPage />)

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
})

it('fills in every detail of a new procedure', async () => {
  mockApi('get', `${BASE}/procedures`, page([]))
  const requests = mockApi('post', `${BASE}/procedures`, makeProcedure(), 201)
  renderProcedures(<ProceduresPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: field('name') }), 'Poda')
  await user.type(form.getByRole('textbox', { name: field('description') }), 'Pedido de poda')
  await user.selectOptions(form.getByLabelText(field('audience')), 'organizations')
  await user.type(form.getByLabelText(field('volume')), '1200')
  await user.click(form.getByRole('checkbox', { name: field('isActive') }))
  await user.click(form.getByRole('button', { name: t('app.save') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({
    name: 'Poda',
    description: 'Pedido de poda',
    area_id: OBRAS.id,
    audience: 'organizations',
    annual_volume: 1200,
    is_active: false,
  })
})

it('keeps the form open and says why creating failed, and closes it with Escape', async () => {
  mockApi('get', `${BASE}/procedures`, page([]))
  mockApiError('post', `${BASE}/procedures`, 409, 'conflict')
  renderProcedures(<ProceduresPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('create') }))
  const form = within(await screen.findByRole('dialog'))
  await user.type(form.getByRole('textbox', { name: field('name') }), 'Permiso de obra')
  await user.click(form.getByRole('button', { name: t('app.save') }))
  expect(await form.findByText(t('errors.conflict'))).toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('asks for an area before any procedure, and says why the list cannot be loaded', async () => {
  mockApiError('get', `${BASE}/procedures`, 500, 'boom')
  renderProcedures(<ProceduresPage />)
  mockApi('get', `${BASE}/areas`, [])

  expect(await screen.findByText(label('needsArea'))).toBeInTheDocument()
  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: label('create') })).toBeNull()
})
