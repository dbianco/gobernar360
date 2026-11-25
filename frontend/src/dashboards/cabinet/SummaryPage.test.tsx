import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { makeSummary } from './testData'
import { BASE, renderCabinet } from './testRender'

const label = (key: string, options = {}) => t(`cabinet.summary.${key}`, options)
const EMPTY = makeSummary({
  total: 0,
  by_state: { overdue: 0, open: 0, done: 0, dropped: 0 },
  on_time_share: null,
  by_owner: [],
  most_postponed: [],
  closed_meetings: 0,
  last_meeting: null,
})

it('shows commitments by state and owner, the share on time and the most postponed', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderCabinet(<SummaryPage />, { level: 'viewer' })

  const owners = await screen.findByRole('table', { name: label('byOwner') })
  const cells = (row: HTMLElement) =>
    within(row)
      .getAllByRole('cell')
      .map((cell) => cell.textContent)
  const [, leo, ana] = within(owners).getAllByRole('row')
  expect(cells(leo)).toEqual(['Leo Paz', '2', '1', '1', '0', '25 %'])
  expect(cells(ana)).toEqual(['Ana Gómez', '0', '2', '2', '1', t('app.none')])
  const cards = [...document.querySelectorAll('[data-indicator]')].map((card) =>
    [...card.querySelectorAll('p')].slice(0, 2).map((p) => p.textContent),
  )
  expect(cards).toEqual([
    [label('columns.overdue'), '2'],
    [label('columns.open'), '3'],
    [label('columns.done'), '3'],
    [label('columns.dropped'), '1'],
    [label('onTime'), '40 %'],
  ])
  const postponed = screen.getByRole('table', { name: label('mostPostponed') })
  expect(within(postponed).getByRole('link', { name: 'Certificar la obra' })).toBeInTheDocument()
  expect(
    screen.getByText(label('lastMeeting', { count: 3, date: '17/11/2026' })),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/commitments.csv`,
  )
  expect(screen.getByRole('region', { name: t('status.title') })).toBeInTheDocument()
})

it('searches the owners', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderCabinet(<SummaryPage />)
  const user = userEvent.setup()

  const owners = within(await screen.findByRole('table', { name: label('byOwner') }))
  await user.type(screen.getByRole('searchbox'), 'gomez')
  expect(owners.queryByRole('row', { name: /Leo Paz/ })).toBeNull()
  expect(owners.getByRole('row', { name: /Ana Gómez/ })).toBeInTheDocument()
  await user.type(screen.getByRole('searchbox'), 'x')

  expect(screen.getByText(t('app.noMatches'))).toBeInTheDocument()
})

it('says when nothing was postponed', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary({ most_postponed: [] }))
  renderCabinet(<SummaryPage />)

  expect(await screen.findByText(label('noPostponed'))).toBeInTheDocument()
})

it('leads an editor to the meetings when there is nothing yet', async () => {
  mockApi('get', `${BASE}/summary`, EMPTY)
  renderCabinet(<SummaryPage />)

  expect(await screen.findByRole('link', { name: label('goToMeetings') })).toHaveAttribute(
    'href',
    '/d/cabinet/meetings',
  )
})

it('tells a viewer who loads them', async () => {
  mockApi('get', `${BASE}/summary`, EMPTY)
  renderCabinet(<SummaryPage />, { level: 'viewer' })

  expect(await screen.findByText(label('emptyViewerBody'))).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: label('byOwner') })).toBeNull()
})

it('says when it cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'boom')
  renderCabinet(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('moves the status strip between years', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderCabinet(<SummaryPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('status.previousYear') }))

  expect(await screen.findByText(`${t('status.title')} 2025`)).toBeInTheDocument()
})
