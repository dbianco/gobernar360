import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ReportsPage } from './ReportsPage'
import { makeReports } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string) => t(`social.reports.${key}`)

/** Open a chart's table view and return its rows as "name|count". */
async function tableOf(title: string) {
  const section = screen.getByRole('heading', { name: title }).closest('section') as HTMLElement
  await userEvent
    .setup()
    .click(within(section).getByRole('button', { name: t('app.chart.showTable') }))
  return within(section)
    .getAllByRole('row')
    .map((row) =>
      within(row)
        .getAllByRole('cell')
        .map((cell) => cell.textContent)
        .join('|'),
    )
}

it('breaks deliveries, interventions and people down', async () => {
  mockApi('get', `${BASE}/reports`, makeReports())
  renderSocial(<ReportsPage />, { level: 'viewer' })

  await screen.findByRole('heading', { name: label('deliveriesByCategory') })
  expect(await tableOf(label('deliveriesByCategory'))).toEqual(['Alimentos|9', 'Hábitat|2'])
  expect(await tableOf(label('interventionsByType'))).toEqual([
    'Visita a domicilio|3',
    'Entrevista presencial|2',
  ])
  expect(await tableOf(label('peopleByNeighborhood'))).toEqual([
    'Sur|7',
    `${label('noNeighborhood')}|1`,
  ])
  expect(await tableOf(label('deliveriesByNeighborhood'))).toEqual(['Sur|8', 'Norte|3'])
  const deliveries = await tableOf(label('deliveriesByMonth'))
  expect(deliveries).toHaveLength(12)
  expect(deliveries.slice(2, 4)).toEqual(['Marzo|6', 'Abril|5'])
  expect((await tableOf(label('interventionsByMonth'))).slice(0, 3)).toEqual([
    'Enero|0',
    'Febrero|1',
    'Marzo|4',
  ])
})

it('asks for the reports of another year', async () => {
  const requests = mockApi('get', `${BASE}/reports`, makeReports())
  renderSocial(<ReportsPage />)
  const user = userEvent.setup()
  const year = new Date().getFullYear()

  await screen.findByRole('heading', { name: label('deliveriesByCategory') })
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(year - 1))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(year - 1)))
})

it('shows a month chart without bars as empty', async () => {
  const none = Array.from({ length: 12 }, (_, index) => ({ month: index + 1, count: 0 }))
  mockApi('get', `${BASE}/reports`, makeReports({ deliveries_by_month: none }))
  renderSocial(<ReportsPage />)

  await screen.findByRole('heading', { name: label('deliveriesByMonth') })
  const section = screen
    .getByRole('heading', { name: label('deliveriesByMonth') })
    .closest('section') as HTMLElement
  expect(within(section).getByText(t('app.chart.noData'))).toBeInTheDocument()
})

it('says why the reports cannot be loaded', async () => {
  mockApiError('get', `${BASE}/reports`, 500, 'boom')
  renderSocial(<ReportsPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('names what each chart counts, and what has no name', async () => {
  mockApi('get', `${BASE}/reports`, makeReports({
    deliveries_by_category: [{ name: null, count: 4 }],
    interventions_by_type: [{ name: null, count: 3 }],
  } as never))
  renderSocial(<ReportsPage />, { level: 'viewer' })
  await screen.findByRole('heading', { name: label('deliveriesByCategory') })

  expect(await tableOf(label('deliveriesByCategory'))).toEqual([`${t('app.none')}|4`])
  expect(await tableOf(label('interventionsByType'))).toEqual([`${t('app.none')}|3`])
})
