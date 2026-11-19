import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { SummaryPage } from './SummaryPage'
import { ANNUAL, makeSummary } from './testData'
import { BASE, renderEnvironment } from './testRender'

const THIS_YEAR = new Date().getFullYear()

it('shows each variable with its value against the target, compliance and loads', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderEnvironment(<SummaryPage />)

  const capped = within(await screen.findByRole('row', { name: /Consumo del palacio municipal/ }))
  expect(capped.getByText('2.500 / 12.000 kWh')).toBeInTheDocument()
  expect(capped.getByText('100 %')).toBeInTheDocument()
  expect(capped.getByText(t('environment.summary.met'))).toBeInTheDocument()
  expect(capped.getByText('2 / 12')).toBeInTheDocument()

  const goal = within(screen.getByRole('row', { name: /Puntos de monitoreo/ }))
  expect(goal.getByText('7,5 / 10 puntos')).toBeInTheDocument()
  expect(goal.getByText('75 %')).toBeInTheDocument()
  expect(goal.getByText(t('environment.summary.missed'))).toBeInTheDocument()
})

it('shows the headline numbers', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderEnvironment(<SummaryPage />)

  const card = async (key: string) =>
    (await screen.findByText(t(`environment.summary.${key}`))).closest('[data-indicator]')!
  expect(await card('variables')).toHaveTextContent('2')
  expect(await card('loads')).toHaveTextContent('3 / 13')
  expect(await card('targetsMet')).toHaveTextContent('1')
  expect(await card('targetsMissed')).toHaveTextContent('1')
})

it('shows dashes for a variable with no target and no values', async () => {
  const summary = makeSummary()
  summary.categories[2].variables = [
    {
      variable: { ...ANNUAL, target: null },
      value: null,
      loaded: 0,
      expected: 1,
      achievement: null,
      target_met: null,
    },
  ]
  mockApi('get', `${BASE}/summary`, summary)
  renderEnvironment(<SummaryPage />)

  const row = within(await screen.findByRole('row', { name: /Puntos de monitoreo/ }))
  expect(row.getAllByText('—')).toHaveLength(2)
  expect(row.getByText('0 / 1')).toBeInTheDocument()
})

it('names the categories that have no variables yet', async () => {
  mockApi('get', `${BASE}/summary`, makeSummary())
  renderEnvironment(<SummaryPage />)

  const note = await screen.findByText(new RegExp(t('environment.summary.withoutVariables')))
  expect(note).toHaveTextContent(t('environment.categories.waste'))
  expect(note).toHaveTextContent(t('environment.categories.governance'))
  expect(note).not.toHaveTextContent(t('environment.categories.energy'))
})

it('asks for the chosen year and links the download of that year', async () => {
  const requests = mockApi('get', `${BASE}/summary`, makeSummary())
  renderEnvironment(<SummaryPage />)
  const user = userEvent.setup()

  await user.selectOptions(
    await screen.findByLabelText(t('environment.year')),
    String(THIS_YEAR - 1),
  )

  await waitFor(() =>
    expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(THIS_YEAR - 1)),
  )
  expect(requests[0].url.searchParams.get('year')).toBe(String(THIS_YEAR))
  expect(screen.getByRole('link', { name: t('environment.summary.download') })).toHaveAttribute(
    'href',
    `/api${BASE}/export/values.csv?year=${THIS_YEAR - 1}`,
  )
})

it('explains what to do when no variable has been defined', async () => {
  mockApi(
    'get',
    `${BASE}/summary`,
    makeSummary({
      variable_count: 0,
      categories: makeSummary().categories.map((c) => ({ ...c, variables: [] })),
    }),
  )
  renderEnvironment(<SummaryPage />, { level: 'admin' })

  expect(await screen.findByText(t('environment.summary.emptyTitle'))).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('environment.summary.goToParameters') })).toHaveAttribute(
    'href',
    '/d/environment/parameters',
  )
})

it('shows an error when the summary cannot be loaded', async () => {
  mockApiError('get', `${BASE}/summary`, 500, 'generic')
  renderEnvironment(<SummaryPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
