import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import ComplaintsRoutes from './routes'
import { makeSummary } from './testData'
import { BASE, renderComplaints } from './testRender'

function renderRoutes(level: AccessLevel, route = '/d/complaints') {
  mockApi('get', `${BASE}/summary`, makeSummary())
  return renderComplaints(
    <Routes>
      <Route path="/d/complaints/*" element={<ComplaintsRoutes />} />
    </Routes>,
    { level, route },
  )
}

const tab = (key: string) => screen.queryByRole('tab', { name: t(`complaints.tabs.${key}`) })

it('shows the reading tabs to everyone and parameters only to admins', async () => {
  const viewer = renderRoutes('viewer')
  expect(await screen.findByRole('heading', { name: t('complaints.title') })).toBeInTheDocument()
  for (const key of ['summary', 'complaints', 'queues']) expect(tab(key)).toBeInTheDocument()
  expect(tab('parameters')).not.toBeInTheDocument()
  viewer.unmount()

  renderRoutes('admin')

  expect(
    await screen.findByRole('tab', { name: t('complaints.tabs.parameters') }),
  ).toBeInTheDocument()
})

it('keeps an editor out of parameters', async () => {
  renderRoutes('editor', '/d/complaints/parameters')

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
  expect(screen.queryByText(t('complaints.parameters.types'))).not.toBeInTheDocument()
})
