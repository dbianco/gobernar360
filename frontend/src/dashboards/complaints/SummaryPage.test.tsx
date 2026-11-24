import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { currentYear } from '../../platform/years'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { emptySummary, makeSummary } from './testData'
import { BASE, renderComplaints } from './testRender'
import type { Summary } from './types'

const label = (key: string, options = {}) => t(`complaints.summary.${key}`, options)

function renderSummary(summary: Summary = makeSummary(), level: AccessLevel = 'viewer') {
  const requests = mockApi('get', `${BASE}/summary`, summary)
  renderComplaints(<SummaryPage />, { level })
  return requests
}

const card = (name: string) =>
  within(screen.getByText(name, { selector: 'p' }).closest('[data-indicator]') as HTMLElement)

it('starts with the status strip and shows the backlog and the period figures', async () => {
  renderSummary()

  expect(await screen.findByRole('region', { name: t('status.title') })).toBeInTheDocument()
  await screen.findByText(label('backlogTitle'))
  expect(card(label('open')).getByText('7')).toBeInTheDocument()
  expect(card(label('overdue')).getByText('2')).toBeInTheDocument()
  expect(card(label('onTime')).getByText('71,4 %')).toBeInTheDocument()
  expect(
    card(label('onTime')).getByText(label('onTimeHint', { count: 10, total: 14 })),
  ).toBeInTheDocument()
  expect(card(label('median')).getByText('4')).toBeInTheDocument()
  expect(card(label('median')).getByText(label('medianHint', { p90: '8,8' }))).toBeInTheDocument()
  expect(
    screen.getByRole('heading', {
      name: label('periodTitle', { from: '01/04/2025', to: '20/03/2026' }),
    }),
  ).toBeInTheDocument()
})

it('shows resolution times by type and by area', async () => {
  renderSummary()

  const byType = within(await screen.findByRole('table', { name: label('byType') }))
  expect(byType.getByRole('row', { name: /Luminaria apagada/ }).textContent).toBe(
    'Luminaria apagada10875 %48,8',
  )
  const byArea = within(screen.getByRole('table', { name: label('byArea') }))
  expect(byArea.getByRole('row', { name: /Alumbrado/ })).toHaveTextContent('5,5')
})

it('lists repeated complaints with their numbers', async () => {
  renderSummary()

  const repeated = within(await screen.findByRole('table', { name: label('repeated') }))
  const row = within(repeated.getByRole('row', { name: /San Martín 450/ }))
  expect(row.getByText('101, 107, 112')).toBeInTheDocument()
  expect(row.getByText('02/03/2026')).toBeInTheDocument()
  expect(screen.getByText(label('repeatedHint', { count: 30 }))).toBeInTheDocument()
})

it('downloads the period it shows and asks again when the period changes', async () => {
  const requests = renderSummary()
  const user = userEvent.setup()
  await screen.findByText(label('backlogTitle'))
  expect(screen.getByRole('link', { name: label('downloadComplaints') })).toHaveAttribute(
    'href',
    '/api/dashboards/complaints/export/complaints.csv',
  )

  await user.selectOptions(screen.getByLabelText(label('period')), 'lastYear')
  await user.selectOptions(screen.getByLabelText(label('repeatDays')), '60')

  const last = currentYear() - 1
  await waitFor(() => {
    const query = requests.at(-1)?.url.searchParams
    expect(query?.get('from')).toBe(`${last}-01-01`)
    expect(query?.get('to')).toBe(`${last}-12-31`)
    expect(query?.get('repeat_days')).toBe('60')
  })
  expect(screen.getByRole('link', { name: label('downloadAreas') })).toHaveAttribute(
    'href',
    `/api/dashboards/complaints/export/areas.csv?from=${last}-01-01&to=${last}-12-31`,
  )
})

it('invites editors to register complaints when there are none', async () => {
  renderSummary(emptySummary(), 'editor')

  expect(await screen.findByText(label('emptyTitle'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: label('goToComplaints') })).toHaveAttribute(
    'href',
    '/d/complaints/complaints',
  )
})
