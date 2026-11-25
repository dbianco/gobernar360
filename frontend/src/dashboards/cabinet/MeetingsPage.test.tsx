import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { MeetingsPage } from './MeetingsPage'
import { makeRow, page } from './testData'
import { BASE, renderCabinet } from './testRender'

const label = (key: string, options = {}) => t(`cabinet.meetings.${key}`, options)
const CLOSED = makeRow({ id: 'me-0', date: '2026-10-20', closed: true, items: 3, commitments: 1 })

it('lists meetings with their state and what came out of them', async () => {
  mockApi('get', `${BASE}/meetings`, page([makeRow(), CLOSED]))
  renderCabinet(<MeetingsPage />, { level: 'viewer' })

  const open = await screen.findByRole('row', { name: /23\/11\/2026/ })
  expect(within(open).getByRole('link')).toHaveAttribute('href', '/d/cabinet/meetings/me-1')
  expect(within(open).getByText(t('cabinet.meeting.open'))).toBeInTheDocument()
  const cells = within(screen.getByRole('row', { name: /20\/10\/2026/ })).getAllByRole('cell')
  expect(cells.map((cell) => cell.textContent)).toEqual([
    '20/10/2026',
    t('cabinet.meeting.closed'),
    '3',
    '1',
  ])
  expect(screen.queryByRole('link', { name: label('prepare') })).toBeNull()
})

it('lets an editor prepare the next one when the last is closed', async () => {
  mockApi('get', `${BASE}/meetings`, page([CLOSED]))
  renderCabinet(<MeetingsPage />)

  expect(await screen.findByRole('link', { name: label('prepare') })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings/new',
  )
})

it('leads an editor to the meeting that is still open, instead of preparing another', async () => {
  mockApi('get', `${BASE}/meetings`, page([makeRow()]))
  renderCabinet(<MeetingsPage />)

  expect(
    await screen.findByRole('link', { name: label('continue', { date: '23/11/2026' }) }),
  ).toHaveAttribute('href', '/d/cabinet/meetings/me-1')
  expect(screen.queryByRole('link', { name: label('prepare') })).toBeNull()
})

it('searches on the server, from the first page', async () => {
  const requests = mockApi('get', `${BASE}/meetings`, ({ url }) =>
    url.searchParams.get('q') === 'x' ? page([]) : page([CLOSED], 30),
  )
  renderCabinet(<MeetingsPage />, { level: 'viewer' })
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('app.pager.next') }))
  await waitFor(() =>
    expect(requests.some(({ url }) => url.searchParams.get('offset') === '10')).toBe(true),
  )
  await user.type(screen.getByRole('searchbox'), 'x')

  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
  const last = requests[requests.length - 1].url.searchParams
  expect([last.get('q'), last.get('offset')]).toEqual(['x', '0'])
})

it('says when there are none', async () => {
  mockApi('get', `${BASE}/meetings`, page([]))
  renderCabinet(<MeetingsPage />)

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(await screen.findByRole('link', { name: label('prepare') })).toBeInTheDocument()
})

it('says when they cannot be loaded', async () => {
  mockApiError('get', `${BASE}/meetings`, 500, 'boom')
  renderCabinet(<MeetingsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: label('prepare') })).toBeNull()
})
