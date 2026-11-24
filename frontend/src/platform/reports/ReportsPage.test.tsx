import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ReportsPage } from './ReportsPage'
import type { ReportPreview, ReportSummary } from './types'

const report = (month: number, fields: Partial<ReportSummary> = {}): ReportSummary => ({
  id: `r-${month}-${fields.version ?? 1}`,
  year: 2026,
  month,
  version: 1,
  status: 'closed',
  closed_at: '2026-11-03T12:00:00Z',
  reopened_at: null,
  published: false,
  ...fields,
})

const PREVIEW: ReportPreview = {
  year: 2026,
  month: 10,
  version: null,
  comments: {},
  content: {
    dashboards: [
      {
        key: 'projects',
        name: 'Proyectos',
        light: 'yellow',
        indicators: [
          { key: 'projects.delayed', name: 'x', unit: null, value: 3, target: 4, on_track: true },
          { key: 'projects.active', name: 'x', unit: null, value: 9, target: null, on_track: null },
        ],
      },
      { key: 'social', name: 'Social', light: null, indicators: [] },
    ],
  },
}

const monthName = (month: number) =>
  t('status.monthYear', { month: t(`status.months.${month}`), year: 2026 })
const row = (month: number) =>
  within(screen.getByRole('rowheader', { name: monthName(month) }).closest('tr') as HTMLElement)

function renderReports(reports: ReportSummary[]) {
  // Only Date is faked so user events and queries keep their real timers.
  vi.useFakeTimers({ toFake: ['Date'], now: new Date(2026, 10, 20) })
  const requests = mockApi('get', '/reports', reports)
  renderApp(<ReportsPage />, { me: makeMe({ isAdmin: true }) })
  return requests
}

afterEach(() => vi.useRealTimers())

it('lists the months that ended, last first, with each report version', async () => {
  renderReports([
    report(9, { published: true }),
    report(8, { version: 2 }),
    report(8, { status: 'superseded', reopened_at: '2026-11-02T10:00:00Z' }),
  ])

  await screen.findByRole('rowheader', { name: monthName(10) })
  const months = screen.getAllByRole('rowheader').map((header) => header.textContent)
  expect(months.slice(0, 3)).toEqual([monthName(10), monthName(9), monthName(8)])
  expect(months).toHaveLength(12)
  expect(row(10).getByText(t('reports.states.open'))).toBeInTheDocument()
  expect(row(9).getByText(t('reports.published'))).toBeInTheDocument()
  expect(row(9).getByText('03/11/2026')).toBeInTheDocument()
  expect(row(8).getByText(/versión 2/)).toBeInTheDocument()
  expect(row(8).getByRole('link', { name: t('reports.downloadVersion', { version: 1 }) }))
    .toHaveAttribute('href', '/api/reports/r-8-1/pdf')
  expect(
    row(9).getByRole('link', { name: t('reports.downloadNamed', { month: monthName(9) }) }),
  ).toHaveAttribute('href', '/api/reports/r-9-1/pdf')
})

it('closes a month with a comment per dashboard', async () => {
  renderReports([])
  mockApi('get', '/reports/preview/2026/10', PREVIEW)
  const closes = mockApi('post', '/reports/2026/10/close', report(10), 201)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('reports.closeNamed', { month: monthName(10) }) }),
  )
  const dialog = await screen.findByRole('dialog')
  expect(
    within(dialog).getByText(t('reports.indicatorsOnTrack', { met: 1, total: 1 }), {
      exact: false,
    }),
  ).toBeInTheDocument()
  await user.type(
    within(dialog).getByLabelText(t('reports.comment', { dashboard: 'Proyectos' })),
    'Un mes con lluvias.',
  )
  await user.click(within(dialog).getByRole('button', { name: t('reports.confirmClose') }))

  await waitFor(() => expect(closes).toHaveLength(1))
  expect(closes[0].body).toEqual({ comments: { projects: 'Un mes con lluvias.' } })
  expect(
    await screen.findByText(t('reports.closed', { month: monthName(10) })),
  ).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('starts a reopened month from its comments', async () => {
  renderReports([report(10, { version: 2, status: 'draft', closed_at: null })])
  mockApi('get', '/reports/preview/2026/10', {
    ...PREVIEW,
    version: 2,
    comments: { social: 'Ya escrito.' },
  })
  const user = userEvent.setup()

  expect(await screen.findByText(t('reports.states.draft'), { exact: false })).toBeInTheDocument()
  await user.click(
    screen.getByRole('button', { name: t('reports.closeNamed', { month: monthName(10) }) }),
  )

  expect(
    await screen.findByLabelText(t('reports.comment', { dashboard: 'Social' })),
  ).toHaveValue('Ya escrito.')
})

it('keeps the dialog open and says why when closing fails', async () => {
  renderReports([])
  mockApi('get', '/reports/preview/2026/10', PREVIEW)
  mockApiError('post', '/reports/2026/10/close', 422, 'month_not_over')
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('reports.closeNamed', { month: monthName(10) }) }),
  )
  await user.click(await screen.findByRole('button', { name: t('reports.confirmClose') }))

  expect(
    await within(screen.getByRole('dialog')).findByText(t('errors.month_not_over')),
  ).toBeInTheDocument()
})

it('reopens a month after asking', async () => {
  renderReports([report(9)])
  const reopens = mockApi('post', '/reports/r-9-1/reopen', report(9, { version: 2 }), 201)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('reports.reopenNamed', { month: monthName(9) }) }),
  )
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent(t('reports.reopenBody', { version: 1, next: 2 }))
  await user.click(within(dialog).getByRole('button', { name: t('reports.reopen') }))

  await waitFor(() => expect(reopens).toHaveLength(1))
})

it('publishes and unpublishes a closed report', async () => {
  renderReports([report(9), report(8, { published: true })])
  const publish = mockApi('put', '/reports/r-9-1/publication', null, 204)
  const unpublish = mockApi('put', '/reports/r-8-1/publication', null, 204)
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('button', { name: t('reports.publishNamed', { month: monthName(9) }) }),
  )
  await user.click(
    screen.getByRole('button', { name: t('reports.unpublishNamed', { month: monthName(8) }) }),
  )

  await waitFor(() => expect(unpublish).toHaveLength(1))
  expect(publish[0].body).toEqual({ published: true })
  expect(unpublish[0].body).toEqual({ published: false })
})

it('explains why a report naming a person cannot be published', async () => {
  renderReports([report(9)])
  mockApiError('put', '/reports/r-9-1/publication', 422, 'personal_data')

  await userEvent.click(
    await screen.findByRole('button', { name: t('reports.publishNamed', { month: monthName(9) }) }),
  )

  expect(await screen.findByText(t('errors.personal_data'))).toBeInTheDocument()
})
