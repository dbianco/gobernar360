import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { currentYear } from '../years'
import { IndicatorTargets } from './IndicatorTargets'
import type { IndicatorTarget } from './types'

const URL = '/dashboards/projects/targets'
const YEAR = currentYear()

const TARGETS: IndicatorTarget[] = [
  {
    key: 'projects.delayed',
    unit: null,
    higher_is_better: false,
    reconstructible: false,
    target: 4,
  },
  {
    key: 'projects.budget_executed_ratio',
    unit: 'ratio',
    higher_is_better: true,
    reconstructible: false,
    target: null,
  },
]

const input = (key: string, year = YEAR) =>
  screen.getByRole('spinbutton', {
    name: t('indicators.targets.inputLabel', { name: t(`overview.indicators.${key}`), year }),
  })
const row = (key: string) =>
  within(screen.getByRole('row', { name: new RegExp(t(`overview.indicators.${key}`)) }))
const save = (key: string) => row(key).getByRole('button', { name: t('indicators.targets.save') })

function renderTargets() {
  renderApp(<IndicatorTargets dashboardKey="projects" />, {
    me: makeMe({ dashboards: { projects: 'admin' } }),
  })
}

it("lists the dashboard's indicators with this year's targets and their direction", async () => {
  const requests = mockApi('get', URL, TARGETS)
  renderTargets()

  await screen.findByRole('table')
  expect(input('projects.delayed')).toHaveValue(4)
  expect(input('projects.budget_executed_ratio')).toHaveValue(null)
  expect(
    row('projects.delayed').getByText(t('indicators.detail.lowerIsBetter')),
  ).toBeInTheDocument()
  expect(requests[0].url.searchParams.get('year')).toBe(String(YEAR))
})

it('saves a changed target', async () => {
  mockApi('get', URL, TARGETS)
  const puts = mockApi('put', `${URL}/${YEAR}/projects.delayed`, null, 204)
  renderTargets()
  const user = userEvent.setup()

  await screen.findByRole('table')
  expect(save('projects.delayed')).toBeDisabled()
  await user.clear(input('projects.delayed'))
  await user.type(input('projects.delayed'), '2')
  await user.click(save('projects.delayed'))

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ value: 2 })
})

it('takes ratio targets as percentages', async () => {
  mockApi('get', URL, TARGETS)
  const puts = mockApi('put', `${URL}/${YEAR}/projects.budget_executed_ratio`, null, 204)
  renderTargets()
  const user = userEvent.setup()

  await screen.findByRole('table')
  await user.type(input('projects.budget_executed_ratio'), '60{Enter}')

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ value: 0.6 })
})

it('removes a target left empty', async () => {
  mockApi('get', URL, TARGETS)
  const puts = mockApi('put', `${URL}/${YEAR}/projects.delayed`, null, 204)
  renderTargets()
  const user = userEvent.setup()

  await screen.findByRole('table')
  await user.clear(input('projects.delayed'))
  await user.click(save('projects.delayed'))

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ value: null })
})

it('shows the targets of another year', async () => {
  const requests = mockApi('get', URL, TARGETS)
  renderTargets()
  const user = userEvent.setup()

  await screen.findByRole('table')
  await user.selectOptions(screen.getByLabelText(t('app.year')), String(YEAR - 1))

  await waitFor(() => expect(requests.at(-1)?.url.searchParams.get('year')).toBe(String(YEAR - 1)))
  expect(
    await screen.findByText(t('indicators.targets.target', { year: YEAR - 1 })),
  ).toBeInTheDocument()
})

it('shows the error when a target is refused', async () => {
  mockApi('get', URL, TARGETS)
  mockApiError('put', `${URL}/${YEAR}/projects.delayed`, 403, 'forbidden')
  renderTargets()
  const user = userEvent.setup()

  await screen.findByRole('table')
  await user.type(input('projects.delayed'), '0{Enter}')

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})
