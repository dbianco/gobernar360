import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { makeSummary } from './testData'
import { BASE, renderEconomic } from './testRender'

const label = (key: string, options = {}) => t(`economic.summary.${key}`, options)
const card = (name: string) =>
  within(screen.getByText(name, { selector: '[data-indicator] *' }).closest('[data-indicator]') as HTMLElement)
const YEAR = new Date().getFullYear()

it('shows the headline numbers and both tool tables', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderEconomic(<SummaryPage />, { level: 'viewer' })

  await screen.findByText(label('actorTools'))
  expect(card(label('actors')).getByText('12')).toBeInTheDocument()
  expect(card(label('actors')).getByText(label('withAssignments', { count: 5 }))).toBeInTheDocument()
  expect(card(label('people')).getByText('14')).toBeInTheDocument()
  expect(card(label('tools')).getByText('6')).toBeInTheDocument()
  expect(card(label('assignments')).getByText('21')).toBeInTheDocument()
  const actors = within(screen.getByRole('table', { name: label('actorTools') }))
  expect(actors.getByRole('row', { name: /Feria de emprendedores/ })).toHaveTextContent('3')
  const people = within(screen.getByRole('table', { name: label('personTools') }))
  expect(people.getByRole('row', { name: /Taller de oficios/ })).toHaveTextContent('2')
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
})

it('asks for another year and points the downloads at it', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderEconomic(<SummaryPage />)
  const user = userEvent.setup()

  await screen.findByText(label('actorTools'))
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(YEAR - 1))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(YEAR - 1)))
  expect(screen.getByRole('link', { name: label('downloadAssignments') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/assignments.csv?year=${YEAR - 1}`,
  )
  expect(screen.getByRole('link', { name: label('downloadActors') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/actors.csv`,
  )
  expect(screen.getByRole('link', { name: label('downloadPeople') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/people.csv`,
  )
})

it('says so when a kind of recipient has no assignments in the year', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary({ person_tools: [] }))
  renderEconomic(<SummaryPage />)

  expect(await screen.findByText(label('noAssignments'))).toBeInTheDocument()
})

it('invites an editor to load data when the dashboard is empty', async () => {
  mockApi(
    'get',
    `${BASE}/summary`,
    makeSummary({
      actors: { total: 0, with_assignments: 0 },
      people: { total: 0, with_assignments: 0 },
      tools: 0,
      assignments: 0,
      actor_tools: [],
      person_tools: [],
    }),
  )
  renderEconomic(<SummaryPage />)

  expect(await screen.findByText(label('emptyTitle'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('economic.actors.create') })).toHaveAttribute(
    'href',
    '/d/economic/actors',
  )
  expect(screen.getByRole('link', { name: t('economic.people.create') })).toHaveAttribute(
    'href',
    '/d/economic/people',
  )
  expect(screen.queryByText(label('actorTools'))).toBeNull()
})

it('shows an error when the summary cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'generic')
  renderEconomic(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
