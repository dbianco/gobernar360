import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { ANNUAL, makeSeries, MONTHLY } from './testData'
import { BASE, renderEnvironment } from './testRender'
import { TrackingPage } from './TrackingPage'

const THIS_YEAR = new Date().getFullYear()
const label = (key: string) => t(`environment.tracking.${key}`)
const mockSeries = () => ({
  monthly: mockApi('get', `${BASE}/variables/${MONTHLY.id}/series`, makeSeries()),
  annual: mockApi(
    'get',
    `${BASE}/variables/${ANNUAL.id}/series`,
    makeSeries({
      variable: ANNUAL,
      monthly: [],
      annual: [{ year: THIS_YEAR, value: 7, loaded: 1, expected: 1 }],
    }),
  ),
})

async function openTable(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: label('showTable') }))
  return within(screen.getByRole('table'))
}

it('shows the twelve months of the first variable', async () => {
  const requests = mockSeries()
  renderEnvironment(<TrackingPage />)
  const user = userEvent.setup()

  const table = await openTable(user)

  expect(table.getAllByRole('row')).toHaveLength(13)
  expect(table.getByRole('row', { name: /Enero/ })).toHaveTextContent('1.000')
  expect(table.getByRole('row', { name: /Diciembre/ })).toHaveTextContent('—')
  expect(requests.monthly[0].url.searchParams.get('year')).toBe(String(THIS_YEAR))
  expect(screen.getByRole('heading', { name: new RegExp(MONTHLY.name) })).toBeInTheDocument()
})

it('switches to the yearly figures', async () => {
  mockSeries()
  renderEnvironment(<TrackingPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(label('view')), 'annual')
  const table = await openTable(user)

  expect(table.getAllByRole('row')).toHaveLength(3)
  expect(table.getByRole('row', { name: new RegExp(String(THIS_YEAR - 1)) })).toHaveTextContent(
    '13.000',
  )
})

it('offers only the variables of the chosen category and subcategory', async () => {
  const requests = mockSeries()
  renderEnvironment(<TrackingPage />)
  const user = userEvent.setup()

  const variableSelect = await screen.findByLabelText(label('variable'))
  await user.selectOptions(screen.getByLabelText(label('category')), 'water')

  await waitFor(() => expect(requests.annual).toHaveLength(1))
  expect(within(variableSelect).getAllByRole('option').map((o) => o.textContent)).toEqual([
    ANNUAL.name,
  ])
  expect(
    within(screen.getByLabelText(label('subcategory')))
      .getAllByRole('option')
      .map((o) => o.textContent),
  ).toEqual([t('app.all'), ANNUAL.subcategory.name])
})

it('shows an annual variable by year only', async () => {
  mockSeries()
  renderEnvironment(<TrackingPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(label('variable')), ANNUAL.id)

  await waitFor(() => expect(screen.getByLabelText(label('view'))).toBeDisabled())
  expect(screen.getByLabelText(label('view'))).toHaveValue('annual')
  const table = await openTable(user)
  expect(table.getByRole('row', { name: new RegExp(String(THIS_YEAR)) })).toHaveTextContent('7')
})

it('says so when the variable has no values yet', async () => {
  mockApi(
    'get',
    `${BASE}/variables/${MONTHLY.id}/series`,
    makeSeries({
      monthly: makeSeries().monthly.map((point) => ({ ...point, value: null })),
      annual: [],
    }),
  )
  renderEnvironment(<TrackingPage />)

  expect(await screen.findByText(label('noValues'))).toBeInTheDocument()
})

it('explains that there is nothing to follow before variables exist', async () => {
  renderEnvironment(<TrackingPage />, { variables: [] })

  expect(await screen.findByText(label('empty'))).toBeInTheDocument()
})

it('shows an error when the series cannot be loaded', async () => {
  mockApiError('get', `${BASE}/variables/${MONTHLY.id}/series`, 500, 'generic')
  renderEnvironment(<TrackingPage />)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('narrows the variables by subcategory, and says when a category has none', async () => {
  const requests = mockSeries()
  renderEnvironment(<TrackingPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(label('subcategory')), ANNUAL.subcategory.id)
  await waitFor(() => expect(requests.annual).toHaveLength(1))
  expect(
    within(screen.getByLabelText(label('variable')))
      .getAllByRole('option')
      .map((o) => o.textContent),
  ).toEqual([ANNUAL.name])

  await user.selectOptions(screen.getByLabelText(label('category')), 'air')
  expect(await screen.findByText(label('noMatch'))).toBeInTheDocument()
})

it('says why the variables cannot be loaded', async () => {
  renderEnvironment(<TrackingPage />)
  mockApiError('get', `${BASE}/variables`, 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})
