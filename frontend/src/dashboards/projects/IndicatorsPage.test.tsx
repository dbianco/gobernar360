import { screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'

import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import { IndicatorsPage } from './IndicatorsPage'
import { makeIndicator } from './testData'
import { BASE, renderProjects } from './testRender'

it('shows the current value against the target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('150 / 200 cuadras')).toBeInTheDocument()
  expect(row.getByText('75 %')).toBeInTheDocument()
})

it('shows a dash when the indicator has no target', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator({ target: null })])
  renderProjects(<IndicatorsPage />)

  const row = within(await screen.findByRole('row', { name: /Cuadras pavimentadas/ }))

  expect(row.getByText('—')).toBeInTheDocument()
})

it('hides editing from viewers', async () => {
  mockApi('get', `${BASE}/indicators`, [makeIndicator()])
  renderProjects(<IndicatorsPage />, { level: 'viewer' })

  await screen.findByRole('row', { name: /Cuadras pavimentadas/ })

  expect(screen.queryByRole('button', { name: t('projects.indicators.add') })).toBeNull()
})
