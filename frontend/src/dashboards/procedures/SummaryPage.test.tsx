import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { makeSummary } from './testData'
import { BASE, renderProcedures } from './testRender'
import type { Summary } from './types'

const label = (key: string, options = {}) => t(`procedures.summary.${key}`, options)

function renderSummary(summary: Summary = makeSummary(), level: AccessLevel = 'viewer') {
  mockApi('get', `${BASE}/summary`, summary)
  return renderProcedures(<SummaryPage />, { level })
}

const card = async (key: string) =>
  (await screen.findByText(label(key))).closest('[data-indicator]') as HTMLElement

it('shows the headline numbers', async () => {
  renderSummary()

  expect(await card('procedures')).toHaveTextContent('12')
  const online = await card('online')
  expect(online).toHaveTextContent('5')
  expect(online).toHaveTextContent(label('onlineHint', { percent: '41,7 %' }))
  expect(await card('averageRequirements')).toHaveTextContent('3,4')
  expect(await card('requirements')).toHaveTextContent('16')
  expect(await card('sources')).toHaveTextContent('11')
})

it('breaks procedures down by area and by channel', async () => {
  renderSummary()
  const user = userEvent.setup()

  const byChannel = (await screen.findByRole('heading', { name: label('byChannel') })).closest(
    'section',
  ) as HTMLElement
  await user.click(within(byChannel).getByRole('button', { name: t('app.chart.showTable') }))
  const online = within(byChannel).getByRole('row', {
    name: new RegExp(`^${t('procedures.channels.online')}`),
  })
  expect(online).toHaveTextContent('2')
  const byArea = screen.getByRole('heading', { name: label('byArea') }).closest('section')!
  await user.click(within(byArea as HTMLElement).getByRole('button', { name: t('app.chart.showTable') }))
  expect(within(byArea as HTMLElement).getByRole('row', { name: /Rentas/ })).toHaveTextContent('7')
})

it('lists the most requested requirements with their source', async () => {
  renderSummary()

  const table = within(await screen.findByRole('table', { name: label('topRequirements') }))
  expect(within(table.getByRole('row', { name: /DNI/ })).getByText('RENAPER')).toBeInTheDocument()
  const form = within(table.getByRole('row', { name: /Formulario/ }))
  expect(form.getByText(label('noSource'))).toBeInTheDocument()
  expect(form.getByText('5')).toBeInTheDocument()
})

it('offers the downloads and the status strip with its own year', async () => {
  renderSummary()

  expect(await screen.findByRole('link', { name: label('downloadProcedures') })).toHaveAttribute(
    'href',
    '/api/dashboards/procedures/export/procedures.csv',
  )
  expect(screen.getByRole('link', { name: label('downloadRequirements') })).toHaveAttribute(
    'href',
    '/api/dashboards/procedures/export/procedure-requirements.csv',
  )
  expect(screen.getByRole('region', { name: t('status.title') })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: t('status.previousYear') })).toBeInTheDocument()
})

it('invites an editor to load procedures when there are none', async () => {
  renderSummary(makeSummary({ procedures: 0, requirements: 0, sources: 0 }), 'editor')

  expect(await screen.findByText(label('emptyTitle'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: label('goToProcedures') })).toHaveAttribute(
    'href',
    '/d/procedures/procedures',
  )
})

it('tells a viewer there is nothing yet', async () => {
  renderSummary(makeSummary({ procedures: 0, requirements: 0, sources: 0 }))

  expect(await screen.findByText(label('emptyViewerBody'))).toBeInTheDocument()
})

it('shows dashes when no procedure is offered but the catalog has data', async () => {
  renderSummary(makeSummary({ procedures: 0, online: 0, average_requirements: null }))

  expect(await card('averageRequirements')).toHaveTextContent('—')
  expect(await card('online')).not.toHaveTextContent('%')
})

it('says when no requirement is asked for yet', async () => {
  renderSummary(makeSummary({ top_requirements: [] }))

  expect(await screen.findByText(label('noTopRequirements'))).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: label('topRequirements') })).toBeNull()
})

it('says why the summary cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'boom')
  renderProcedures(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
