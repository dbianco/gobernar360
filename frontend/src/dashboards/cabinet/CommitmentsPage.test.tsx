import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { choosePerson } from '../../test/person'
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
    '/commitments/co-1',
  )
  expect(row.getByText(LEO.full_name)).toBeInTheDocument()
  expect(row.getByText('20/11/2026')).toBeInTheDocument()
  expect(row.getByText(t('commitments.states.overdue'))).toBeInTheDocument()
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
  expect([params.get('state'), params.get('limit')]).toEqual(['pending', '10'])
})

it('shows the date agreed when it was moved, and that the owner left', async () => {
  mockApi(
    'get',
    `${BASE}/commitments`,
    page([
      makeCommitment({ due_date: '2026-12-15', owner_left: true }),
      makeCommitment({ id: 'co-2', description: 'Señalizar' }),
    ]),
  )
  renderCabinet(<CommitmentsPage />, { level: 'viewer' })

  const agreed = t('commitments.agreedFor', { date: '20/11/2026' })
  const moved = within(await screen.findByRole('row', { name: /Certificar/ }))
  expect(moved.getByText('15/12/2026')).toBeInTheDocument()
  expect(moved.getByText(agreed)).toBeInTheDocument()
  expect(moved.getByText(t('commitments.ownerLeft'))).toBeInTheDocument()
  const same = within(screen.getByRole('row', { name: /Señalizar/ }))
  expect(same.queryByText(agreed)).toBeNull()
  expect(same.queryByText(t('commitments.ownerLeft'))).toBeNull()
})

it('filters on the server, and the download takes the same filters', async () => {
  const requests = mockApi('get', `${BASE}/commitments`, page([makeCommitment()], 30))
  renderCabinet(<CommitmentsPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.pager.next') }))
  await user.type(screen.getByRole('searchbox'), 'obra')
  await user.selectOptions(screen.getByLabelText(label('state')), 'done')
  const owner = screen.getByRole('combobox', { name: label('owner') })
  expect(owner).toHaveAttribute('placeholder', label('allOwners'))
  await choosePerson(user, owner, 'leo', LEO.full_name)

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
  await user.click(screen.getByRole('button', { name: t('app.person.clear') }))
  await waitFor(() => expect(last(requests).url.searchParams.has('owner_id')).toBe(false))
  await user.selectOptions(screen.getByLabelText(label('state')), label('allStates'))
  await waitFor(() => expect(last(requests).url.searchParams.has('state')).toBe(false))
})

it('says when none match', async () => {
  mockApi('get', `${BASE}/commitments`, page([]))
  renderCabinet(<CommitmentsPage />)

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
})

it('says when they cannot be loaded', async () => {
  mockApiError('get', `${BASE}/commitments`, 500, 'boom')
  renderCabinet(<CommitmentsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
