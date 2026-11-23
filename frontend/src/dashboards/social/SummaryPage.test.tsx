import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { makeSummary } from './testData'
import { BASE, renderSocial } from './testRender'

const label = (key: string, options = {}) => t(`social.summary.${key}`, options)
const card = (name: string) =>
  within(
    screen.getByText(name, { selector: '[data-indicator] *' }).closest(
      '[data-indicator]',
    ) as HTMLElement,
  )
const YEAR = new Date().getFullYear()
const EMPTY = makeSummary({
  people: 0,
  households: 0,
  people_with_deliveries: 0,
  deliveries: 0,
  units: 0,
  interventions: 0,
  people_with_interventions: 0,
  benefits: [],
  intervention_types: [],
})

it('shows the headline numbers and both tables', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderSocial(<SummaryPage />, { level: 'viewer' })

  await screen.findByText(label('benefits'))
  expect(card(label('people')).getByText('16')).toBeInTheDocument()
  expect(
    card(label('people')).getByText(label('peopleWithDeliveries', { count: 9 })),
  ).toBeInTheDocument()
  expect(card(label('households')).getByText('5')).toBeInTheDocument()
  expect(card(label('deliveries')).getByText('15')).toBeInTheDocument()
  expect(card(label('deliveries')).getByText(label('units', { count: 39 }))).toBeInTheDocument()
  expect(card(label('interventions')).getByText('8')).toBeInTheDocument()
  expect(
    card(label('interventions')).getByText(label('peopleWithInterventions', { count: 7 })),
  ).toBeInTheDocument()
  const benefits = within(screen.getByRole('table', { name: label('benefits') }))
  expect(benefits.getByRole('row', { name: /Chapas/ })).toHaveTextContent('Hábitat112')
  const types = within(screen.getByRole('table', { name: label('interventionTypes') }))
  expect(types.getByRole('row', { name: /Visita a domicilio/ })).toHaveTextContent('3')
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
})

it('asks for another year and points the downloads at it', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderSocial(<SummaryPage />)
  const user = userEvent.setup()

  await screen.findByText(label('benefits'))
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(YEAR - 1))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(YEAR - 1)))
  const href = (key: string) => screen.getByRole('link', { name: label(key) }).getAttribute('href')
  expect(href('downloadDeliveries')).toBe(`/api${BASE}/export/deliveries.csv?year=${YEAR - 1}`)
  expect(href('downloadInterventions')).toBe(
    `/api${BASE}/export/interventions.csv?year=${YEAR - 1}`,
  )
  expect(href('downloadPeople')).toBe(`/api${BASE}/export/people.csv`)
  expect(href('downloadHouseholds')).toBe(`/api${BASE}/export/households.csv`)
})

it('says so when the year has no records', async () => {
  mockApi(
    'get',
    `${BASE}/summary`,
    makeSummary({ deliveries: 0, units: 0, benefits: [], intervention_types: [] }),
  )
  renderSocial(<SummaryPage />)

  expect(await screen.findByText(label('noDeliveries'))).toBeInTheDocument()
  expect(screen.getByText(label('noInterventions'))).toBeInTheDocument()
})

async function renderEmpty(level: AccessLevel) {
  mockApi('get', `${BASE}/summary`, EMPTY)
  renderSocial(<SummaryPage />, { level })
  expect(await screen.findByText(label('emptyTitle'))).toBeInTheDocument()
  expect(screen.queryByText(label('benefits'))).toBeNull()
}

it('tells a viewer of an empty dashboard to wait for the team', async () => {
  await renderEmpty('viewer')

  expect(screen.getByText(label('emptyViewerBody'))).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: label('goToPeople') })).toBeNull()
})

it('invites an editor to load people when the dashboard is empty', async () => {
  await renderEmpty('editor')

  expect(screen.getByRole('link', { name: label('goToPeople') })).toHaveAttribute(
    'href',
    '/d/social/people',
  )
  expect(screen.queryByRole('link', { name: label('goToParameters') })).toBeNull()
})

it('points an admin of an empty dashboard at the parameters first', async () => {
  await renderEmpty('admin')

  expect(screen.getByRole('link', { name: label('goToParameters') })).toHaveAttribute(
    'href',
    '/d/social/parameters',
  )
})

it('shows an error when the summary cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'generic')
  renderSocial(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('names interventions without a type as none', async () => {
  mockApi(
    'get',
    `${BASE}/summary`,
    makeSummary({ intervention_types: [{ name: null, count: 4 }] }),
  )
  renderSocial(<SummaryPage />, { level: 'viewer' })

  const types = within(await screen.findByRole('table', { name: label('interventionTypes') }))
  expect(types.getByRole('row', { name: new RegExp(t('app.none')) })).toHaveTextContent('4')
})
