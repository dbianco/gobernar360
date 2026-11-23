import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { makeSummary, TERM } from './testData'
import { BASE, renderProjects } from './testRender'

const card = (labelKey: string) =>
  within(screen.getByText(t(labelKey)).closest('[data-indicator]') as HTMLElement)

it('renders status counts and budget percentages', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderProjects(<SummaryPage />)

  expect(await screen.findByText(t('projects.summary.active'))).toBeInTheDocument()
  expect(card('projects.summary.active').getByText('10')).toBeInTheDocument()
  expect(card('projects.status.delayed').getByText('3')).toBeInTheDocument()
  expect(card('projects.summary.averageProgress').getByText('48 %')).toBeInTheDocument()
  expect(card('projects.summary.budgetPlanned').getByText('40 %')).toBeInTheDocument()
  expect(card('projects.summary.budgetExecuted').getByText('25 %')).toBeInTheDocument()
  expect(card('projects.summary.milestonesCompleted').getByText('12 / 20')).toBeInTheDocument()
  expect(card('projects.summary.milestonesInAlert').getByText('2')).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('term_id')).toBe(TERM.id)
})

it('shows a dash when a ratio is null', async () => {
  mockApi(
    'get',
    `${BASE}/summary`,
    makeSummary({
      budget: {
        total: null,
        planned: '0.00',
        executed: '0.00',
        planned_ratio: null,
        executed_ratio: null,
      },
    }),
  )
  renderProjects(<SummaryPage />)

  await screen.findByText(t('projects.summary.active'))
  expect(card('projects.summary.budgetTotal').getByText('—')).toBeInTheDocument()
  expect(card('projects.summary.budgetPlanned').getByText('—')).toBeInTheDocument()
  expect(card('projects.summary.budgetExecuted').getByText('—')).toBeInTheDocument()
})

it('refetches the summary when a filter changes', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderProjects(<SummaryPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(t('projects.filters.year')), '2024')
  await user.selectOptions(screen.getByLabelText(t('projects.filters.axis')), 'Ciudad segura')

  await waitFor(() => {
    const last = requests[requests.length - 1].url.searchParams
    expect(last.get('year')).toBe('2024')
    expect(last.get('axis_id')).toBe('a-2')
  })
})

it('export links carry the current filters', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderProjects(<SummaryPage />)

  await userEvent
    .setup()
    .selectOptions(await screen.findByLabelText(t('projects.filters.year')), '2024')

  expect(screen.getByRole('link', { name: t('projects.summary.downloadProjects') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/projects.csv?term_id=${TERM.id}&year=2024`,
  )
  expect(
    screen.getByRole('link', { name: t('projects.summary.downloadIndicators') }),
  ).toHaveAttribute('href', `/api${BASE}/export/indicators.csv?term_id=${TERM.id}`)
})

it('offers each chart as a table', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderProjects(<SummaryPage />)

  const section = within(
    (await screen.findByRole('heading', { name: t('projects.summary.byDepartment') })).closest(
      'section',
    ) as HTMLElement,
  )
  await userEvent.setup().click(section.getByRole('button', { name: t('projects.summary.showTable') }))

  expect(section.getByRole('row', { name: /Obras Públicas\s*9/ })).toBeInTheDocument()
})

it('lets the lights of an earlier year be looked at and corrected', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  const status = mockApi('get', '/dashboards/projects/status', [])
  renderProjects(<SummaryPage />)
  const thisYear = new Date().getFullYear()
  await waitFor(() => expect(status[0]?.url.searchParams.get('year')).toBe(String(thisYear)))

  await userEvent.click(await screen.findByRole('button', { name: t('status.previousYear') }))

  await waitFor(() => expect(status.at(-1)?.url.searchParams.get('year')).toBe(String(thisYear - 1)))
  expect(screen.getByRole('button', { name: t('status.nextYear') })).toBeEnabled()
})

it('does not offer the lights of a year that has not started', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderProjects(<SummaryPage />)

  expect(await screen.findByRole('button', { name: t('status.nextYear') })).toBeDisabled()
})

it('says why the summary cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'boom')
  renderProjects(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
