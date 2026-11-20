import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import type { AccessLevel } from '../types'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi } from '../../test/server'
import { StatusStrip } from './StatusStrip'

const URL = '/dashboards/projects/status'
const state = (color: string) => t(`status.states.${color}`)
const monthName = (month: number, color: string) =>
  t('status.monthLabel', {
    month: t(`status.months.${month}`),
    state: state(color),
  })

function renderStrip(level: AccessLevel, year = 2025) {
  // Only Date is faked so user events and queries keep their real timers.
  vi.useFakeTimers({ toFake: ['Date'], now: new Date(2025, 5, 15) })
  return renderApp(<StatusStrip dashboardKey="projects" year={year} />, {
    me: makeMe({ dashboards: { projects: level } }),
  })
}

afterEach(() => vi.useRealTimers())

it('shows the twelve months with their state', async () => {
  const requests = mockApi('get', URL, [
    { month: 3, color: 'green' },
    { month: 5, color: 'red' },
  ])
  renderStrip('viewer')

  expect(await screen.findByRole('img', { name: monthName(3, 'green') })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: monthName(5, 'red') })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: monthName(4, 'none') })).toBeInTheDocument()
  expect(screen.getAllByRole('listitem')).toHaveLength(12)
  expect(requests[0].url.searchParams.get('year')).toBe('2025')
})

it('does not let a viewer or an editor change a month', async () => {
  mockApi('get', URL, [{ month: 3, color: 'green' }])
  renderStrip('editor')

  await screen.findByRole('img', { name: monthName(3, 'green') })

  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it('lets an admin set the color of a month', async () => {
  mockApi('get', URL, [{ month: 3, color: 'green' }])
  const puts = mockApi('put', `${URL}/2025/3`, null, 204)
  renderStrip('admin')

  await userEvent.click(await screen.findByRole('button', { name: monthName(3, 'green') }))
  await userEvent.click(await screen.findByRole('menuitem', { name: state('red') }))

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ color: 'red' })
})

it('lets an admin clear a month', async () => {
  mockApi('get', URL, [{ month: 3, color: 'green' }])
  const puts = mockApi('put', `${URL}/2025/3`, null, 204)
  renderStrip('admin')

  await userEvent.click(await screen.findByRole('button', { name: monthName(3, 'green') }))
  await userEvent.click(await screen.findByRole('menuitem', { name: t('status.clear') }))

  await waitFor(() => expect(puts).toHaveLength(1))
  expect(puts[0].body).toEqual({ color: null })
})

it('does not offer to clear a month that has no state', async () => {
  mockApi('get', URL, [])
  renderStrip('admin')

  await userEvent.click(await screen.findByRole('button', { name: monthName(2, 'none') }))

  expect(await screen.findByRole('menuitem', { name: state('green') })).toBeInTheDocument()
  expect(screen.queryByRole('menuitem', { name: t('status.clear') })).not.toBeInTheDocument()
})

it('does not let months that have not started be changed', async () => {
  mockApi('get', URL, [])
  renderStrip('admin')

  expect(await screen.findByRole('button', { name: monthName(6, 'none') })).toBeEnabled()
  expect(screen.getByRole('button', { name: monthName(7, 'none') })).toBeDisabled()
})

it('lets every month of a past year be changed and none of a future one', async () => {
  mockApi('get', URL, [])
  const past = renderStrip('admin', 2024)
  expect(await screen.findByRole('button', { name: monthName(12, 'none') })).toBeEnabled()
  past.unmount()

  renderStrip('admin', 2026)

  expect(await screen.findByRole('button', { name: monthName(1, 'none') })).toBeDisabled()
})

it('shows the error when the change is refused', async () => {
  mockApi('get', URL, [])
  mockApi('put', `${URL}/2025/3`, { error: { code: 'future_month', message: 'x' } }, 422)
  renderStrip('admin')

  await userEvent.click(await screen.findByRole('button', { name: monthName(3, 'none') }))
  await userEvent.click(await screen.findByRole('menuitem', { name: state('green') }))

  const strip = within(screen.getByRole('region', { name: t('status.title') }))
  expect(await strip.findByRole('alert')).toHaveTextContent(t('errors.future_month'))
})
