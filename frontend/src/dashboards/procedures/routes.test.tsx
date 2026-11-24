import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import ProceduresRoutes from './routes'
import { makeSummary } from './testData'
import { BASE, renderProcedures } from './testRender'

function renderRoutes(level: AccessLevel, route = '/d/procedures') {
  mockApi('get', `${BASE}/summary`, makeSummary())
  return renderProcedures(
    <Routes>
      <Route path="/d/procedures/*" element={<ProceduresRoutes />} />
    </Routes>,
    { level, route },
  )
}

const tab = (key: string) => screen.queryByRole('tab', { name: t(`procedures.tabs.${key}`) })

it('shows the reading tabs to everyone and parameters only to admins', async () => {
  const viewer = renderRoutes('viewer')
  expect(await screen.findByRole('heading', { name: t('procedures.title') })).toBeInTheDocument()
  for (const key of ['summary', 'procedures', 'requirements', 'opportunities']) {
    expect(tab(key)).toBeInTheDocument()
  }
  expect(tab('parameters')).not.toBeInTheDocument()
  viewer.unmount()

  renderRoutes('admin')

  expect(
    await screen.findByRole('tab', { name: t('procedures.tabs.parameters') }),
  ).toBeInTheDocument()
})

it('keeps an editor out of parameters', async () => {
  renderRoutes('editor', '/d/procedures/parameters')

  expect(await screen.findByRole('heading', { name: t('procedures.title') })).toBeInTheDocument()
  expect(screen.queryByText(t('procedures.parameters.areas'))).not.toBeInTheDocument()
})

it('moves between sections with the tabs', async () => {
  renderRoutes('admin')
  const user = userEvent.setup()

  await user.click(await screen.findByRole('tab', { name: t('procedures.tabs.parameters') }))
  await waitFor(() => expect(tab('parameters')).toHaveAttribute('aria-selected', 'true'))
  await user.click(screen.getByRole('tab', { name: t('procedures.tabs.summary') }))

  await waitFor(() => expect(tab('summary')).toHaveAttribute('aria-selected', 'true'))
})
