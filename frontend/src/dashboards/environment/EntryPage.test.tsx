import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { EntryPage } from './EntryPage'
import { ANNUAL, makeValue, MONTHLY } from './testData'
import { BASE, renderEnvironment } from './testRender'

const THIS_YEAR = new Date().getFullYear()
const monthCell = (month: number, variable = MONTHLY) =>
  t('environment.entry.cell', {
    variable: variable.name,
    period: t(`environment.monthNames.${month}`),
  })
const yearCell = (year = THIS_YEAR) =>
  t('environment.entry.cell', { variable: ANNUAL.name, period: year })

it('shows twelve month cells for a monthly variable and one for an annual one', async () => {
  mockApi('get', `${BASE}/values`, [
    makeValue({ period: 2, value: 1500.5 }),
    makeValue({ variable_id: ANNUAL.id, period: 0, value: 7 }),
  ])
  renderEnvironment(<EntryPage />)

  expect(await screen.findByLabelText(monthCell(2))).toHaveValue('1500,5')
  for (let month = 1; month <= 12; month += 1) {
    expect(screen.getByLabelText(monthCell(month))).toBeInTheDocument()
  }
  expect(screen.getByLabelText(monthCell(1))).toHaveValue('')
  expect(screen.getByLabelText(yearCell())).toHaveValue('7')
  expect(screen.queryByLabelText(monthCell(1, ANNUAL))).toBeNull()
})

it('saves a cell when leaving it', async () => {
  mockApi('get', `${BASE}/values`, [])
  const requests = mockApi('put', `${BASE}/values`, makeValue({ period: 3, value: 1500.5 }))
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await user.type(await screen.findByLabelText(monthCell(3)), '1500,5')
  await user.tab()

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    variable_id: MONTHLY.id,
    year: THIS_YEAR,
    period: 3,
    value: '1500.5',
  })
})

it('saves the whole-year value of an annual variable', async () => {
  mockApi('get', `${BASE}/values`, [])
  const requests = mockApi('put', `${BASE}/values`, makeValue())
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await user.type(await screen.findByLabelText(yearCell()), '0')
  await user.tab()

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({
    variable_id: ANNUAL.id,
    year: THIS_YEAR,
    period: 0,
    value: '0',
  })
})

it('clears the value when the cell is emptied', async () => {
  mockApi('get', `${BASE}/values`, [makeValue({ period: 1, value: 1000 })])
  const requests = mockApi('put', `${BASE}/values`, null, 204)
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await user.clear(await screen.findByLabelText(monthCell(1)))
  await user.tab()

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toMatchObject({ period: 1, value: null })
})

it('does not save a cell that was not changed', async () => {
  mockApi('get', `${BASE}/values`, [makeValue({ period: 1, value: 1000 })])
  const requests = mockApi('put', `${BASE}/values`, makeValue())
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await user.click(await screen.findByLabelText(monthCell(1)))
  await user.tab()
  await user.click(screen.getByLabelText(monthCell(2)))
  await user.tab()

  expect(requests).toHaveLength(0)
})

it('marks a cell that is not a number and does not send it', async () => {
  mockApi('get', `${BASE}/values`, [])
  const requests = mockApi('put', `${BASE}/values`, makeValue())
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  const cell = await screen.findByLabelText(monthCell(4))
  await user.type(cell, 'mucho')
  await user.tab()

  expect(cell).toHaveAttribute('aria-invalid', 'true')
  expect(cell).toHaveValue('mucho')
  expect(requests).toHaveLength(0)
})

it('keeps what was typed and shows the error when saving fails', async () => {
  mockApi('get', `${BASE}/values`, [])
  mockApiError('put', `${BASE}/values`, 403, 'forbidden')
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  const cell = await screen.findByLabelText(monthCell(5))
  await user.type(cell, '12')
  await user.tab()

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(cell).toHaveValue('12')
  expect(cell).toHaveAttribute('aria-invalid', 'true')
})

it('loads the values of the chosen year', async () => {
  const requests = mockApi('get', `${BASE}/values`, [])
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await user.selectOptions(await screen.findByLabelText(t('environment.year')), `${THIS_YEAR - 1}`)

  await waitFor(() =>
    expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(THIS_YEAR - 1)),
  )
  expect(await screen.findByLabelText(yearCell(THIS_YEAR - 1))).toBeInTheDocument()
})

it('shows only the variables of the chosen category', async () => {
  mockApi('get', `${BASE}/values`, [])
  renderEnvironment(<EntryPage />)
  const user = userEvent.setup()

  await screen.findByLabelText(monthCell(1))
  await user.selectOptions(screen.getByLabelText(t('environment.entry.category')), 'water')

  expect(screen.queryByLabelText(monthCell(1))).toBeNull()
  expect(screen.getByLabelText(yearCell())).toBeInTheDocument()
})

it('explains that there is nothing to load before variables exist', async () => {
  mockApi('get', `${BASE}/values`, [])
  renderEnvironment(<EntryPage />, { variables: [] })

  expect(await screen.findByText(t('environment.entry.empty'))).toBeInTheDocument()
})
