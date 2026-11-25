import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { CommitmentsPage } from './CommitmentsPage'
import { HIDDEN, LEO, makeCommitment, page } from './testData'
import { BASE, renderCabinet } from './testRender'

const label = (key: string) => t(`cabinet.list.${key}`)
const last = <T,>(items: T[]) => items[items.length - 1]

it('lists what is pending: what, who, when, how and about what', async () => {
  const requests = mockApi(
    'get',
    `${BASE}/commitments`,
    page([
      makeCommitment(),
      makeCommitment({
        id: 'co-2',
        description: 'Señalizar',
        state: 'open',
        times_postponed: 0,
        subject: HIDDEN,
      }),
      makeCommitment({ id: 'co-3', description: 'Suelto', subject: null }),
    ]),
  )
  renderCabinet(<CommitmentsPage />, { level: 'viewer' })

  const row = within(await screen.findByRole('row', { name: /Certificar/ }))
  expect(row.getByRole('link', { name: 'Certificar la obra' })).toHaveAttribute(
    'href',
    '/d/cabinet/commitments/co-1',
  )
  expect(row.getByText(LEO.full_name)).toBeInTheDocument()
  expect(row.getByText('20/11/2026')).toBeInTheDocument()
  expect(row.getByText(t('cabinet.states.overdue'))).toBeInTheDocument()
  expect(row.getByText(t('commitments.postponed', { count: 2 }))).toBeInTheDocument()
  expect(row.getByRole('link', { name: 'Plaza central' })).toBeInTheDocument()
  expect(row.getByRole('link', { name: '20/10/2026' })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings/me-0',
  )
  const hidden = within(screen.getByRole('row', { name: /Señalizar/ }))
  expect(hidden.getByText(t('subjects.restricted.projects.project'))).toBeInTheDocument()
  expect(screen.getByRole('row', { name: /Suelto/ })).toHaveTextContent(t('app.none'))
  const params = last(requests).url.searchParams
  expect([params.get('state'), params.get('mine'), params.get('limit')]).toEqual([
    'pending',
    null,
    '10',
  ])
})

it('filters on the server, and the download takes the same filters', async () => {
  const requests = mockApi('get', `${BASE}/commitments`, page([makeCommitment()], 30))
  renderCabinet(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.pager.next') }))
  await user.type(screen.getByRole('searchbox'), 'obra')
  await user.selectOptions(screen.getByLabelText(label('state')), 'done')
  await screen.findByRole('option', { name: LEO.full_name })
  await user.selectOptions(screen.getByLabelText(label('owner')), LEO.id)

  await waitFor(() => expect(last(requests).url.searchParams.get('owner_id')).toBe(LEO.id))
  const params = last(requests).url.searchParams
  expect([params.get('q'), params.get('state'), params.get('offset')]).toEqual([
    'obra',
    'done',
    '0',
  ])
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/commitments.csv?q=obra&state=done&owner_id=${LEO.id}`,
  )
  await user.selectOptions(screen.getByLabelText(label('state')), label('allStates'))
  await waitFor(() => expect(last(requests).url.searchParams.has('state')).toBe(false))
})

it('shows only their own to whoever is signed in', async () => {
  const requests = mockApi('get', `${BASE}/commitments`, page([makeCommitment()]))
  renderCabinet(<CommitmentsPage mine />, { level: 'viewer' })

  const table = await screen.findByRole('table', { name: t('cabinet.tabs.mine') })
  expect(within(table).queryByText(LEO.full_name)).toBeNull()
  expect(screen.queryByLabelText(label('owner'))).toBeNull()
  expect(last(requests).url.searchParams.get('mine')).toBe('true')
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/commitments.csv?state=pending&mine=true`,
  )
})

it('says when none match', async () => {
  mockApi('get', `${BASE}/commitments`, page([]))
  const view = renderCabinet(<CommitmentsPage />)
  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  view.unmount()

  renderCabinet(<CommitmentsPage mine />)
  expect(await screen.findByText(label('emptyMine'))).toBeInTheDocument()
})

it('says when they cannot be loaded', async () => {
  mockApiError('get', `${BASE}/commitments`, 500, 'boom')
  renderCabinet(<CommitmentsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
