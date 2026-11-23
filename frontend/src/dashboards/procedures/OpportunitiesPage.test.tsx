import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { OpportunitiesPage } from './OpportunitiesPage'
import { makeOpportunities } from './testData'
import { BASE, renderProcedures } from './testRender'

const label = (key: string) => t(`procedures.opportunities.${key}`)

it('lists each source with what is asked of people that it already holds', async () => {
  mockApi('get', `${BASE}/opportunities`, makeOpportunities())
  renderProcedures(<OpportunitiesPage />, { level: 'viewer' })

  const rows = await screen.findAllByRole('row')
  // Header, the two sources in the order the API ranks them, then what people bring.
  expect(rows).toHaveLength(4)
  const municipal = within(rows[1])
  expect(municipal.getByText('Rentas municipal')).toBeInTheDocument()
  expect(municipal.getByText(t('procedures.levels.municipal'))).toBeInTheDocument()
  expect(municipal.getByText('Rentas')).toBeInTheDocument()
  expect(municipal.getByText('3.190')).toBeInTheDocument()
  expect(within(rows[2]).getByText('RENAPER')).toBeInTheDocument()
  const rest = within(rows[3])
  expect(rest.getByText(label('withoutSource'))).toBeInTheDocument()
  expect(rest.getByText('2.620')).toBeInTheDocument()
})

it('offers the download', async () => {
  mockApi('get', `${BASE}/opportunities`, makeOpportunities())
  renderProcedures(<OpportunitiesPage />, { level: 'viewer' })

  expect(await screen.findByRole('link', { name: label('download') })).toHaveAttribute(
    'href',
    '/api/dashboards/procedures/export/opportunities.csv',
  )
})

it('says so when no requirement has a source yet', async () => {
  mockApi(
    'get',
    `${BASE}/opportunities`,
    makeOpportunities({
      sources: [],
      without_source: { requirements: 0, procedures: 0, annual_volume: 0 },
    }),
  )
  renderProcedures(<OpportunitiesPage />, { level: 'viewer' })

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('says why the opportunities cannot be loaded', async () => {
  mockApiError('get', `${BASE}/opportunities`, 500, 'boom')
  renderProcedures(<OpportunitiesPage />, { level: 'viewer' })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('says when the search matches no source', async () => {
  mockApi('get', `${BASE}/opportunities`, makeOpportunities())
  renderProcedures(<OpportunitiesPage />, { level: 'viewer' })
  const user = userEvent.setup()

  await screen.findByText('RENAPER')
  await user.type(screen.getByRole('searchbox', { name: t('app.search') }), 'zzz')

  expect(await screen.findByText(t('app.noMatches'))).toBeInTheDocument()
  expect(screen.queryByText('RENAPER')).toBeNull()
})
