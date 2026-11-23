import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ReportsPage } from './ReportsPage'
import { makeReports } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string) => t(`economic.reports.${key}`)

/** Open a chart's table view and return its rows as "name|count". */
async function tableOf(title: string) {
  const section = screen.getByRole('heading', { name: title }).closest('section') as HTMLElement
  await userEvent.setup().click(within(section).getByRole('button', { name: t('app.chart.showTable') }))
  return within(section)
    .getAllByRole('row')
    .map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent).join('|'))
}

it('breaks actors, people and assignments down', async () => {
  mockApi('get', `${BASE}/reports`, makeReports())
  renderEconomic(<ReportsPage />, { level: 'viewer' })

  await screen.findByRole('heading', { name: label('actorsByType') })
  expect(await tableOf(label('actorsByType'))).toEqual([
    'Comercio|4',
    `${t('economic.actors.noType')}|1`,
  ])
  expect(await tableOf(label('actorsBySector'))).toEqual(['Alimentos|5'])
  expect(await tableOf(label('peopleByStatus'))).toEqual([
    `${t('economic.employmentStatuses.self_employed')}|4`,
    `${t('economic.employmentStatuses.unemployed')}|2`,
  ])
  expect(await tableOf(label('assignmentsByCategory'))).toEqual(['Capacitación|9'])
  const months = await tableOf(label('assignmentsByMonth'))
  expect(months).toHaveLength(12)
  expect(months.slice(0, 3)).toEqual(['Enero|0', 'Febrero|0', 'Marzo|7'])
})

it('asks for the reports of another year', async () => {
  const requests = mockApi('get', `${BASE}/reports`, makeReports())
  renderEconomic(<ReportsPage />)
  const user = userEvent.setup()
  const year = new Date().getFullYear()

  await screen.findByRole('heading', { name: label('actorsByType') })
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(year - 1))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(year - 1)))
})

it('shows a month chart without bars as empty', async () => {
  mockApi(
    'get',
    `${BASE}/reports`,
    makeReports({
      assignments_by_category: [],
      assignments_by_month: Array.from({ length: 12 }, (_, i) => ({ month: i + 1, count: 0 })),
    }),
  )
  renderEconomic(<ReportsPage />)

  await screen.findByRole('heading', { name: label('assignmentsByMonth') })
  const section = screen
    .getByRole('heading', { name: label('assignmentsByMonth') })
    .closest('section') as HTMLElement
  expect(within(section).getByText(t('app.chart.noData'))).toBeInTheDocument()
})

it('says why the reports cannot be loaded', async () => {
  mockApiError('get', `${BASE}/reports`, 500, 'boom')
  renderEconomic(<ReportsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
