import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { expect, it } from 'vitest'

import App from '../../App'
import type { AccessLevel } from '../../platform/types'
import { t } from '../../test/render'
import { mockApi } from '../../test/server'
import CabinetRoutes from './routes'
import {
  makeAgendaProposal,
  makeCommitment,
  makeCommitmentDetail,
  makeMeeting,
  makeRow,
  makeSummary,
  page,
} from './testData'
import { BASE, renderCabinet } from './testRender'

function mockAll() {
  mockApi('get', `${BASE}/summary`, makeSummary())
  mockApi('get', `${BASE}/meetings`, page([makeRow({ closed: true })]))
  mockApi('get', `${BASE}/meetings/me-1`, makeMeeting())
  mockApi('get', `${BASE}/agenda-proposal`, makeAgendaProposal())
  mockApi('get', `${BASE}/commitments/co-1`, makeCommitmentDetail())
  return mockApi('get', `${BASE}/commitments`, page([makeCommitment()]))
}

function renderRoutes(level: AccessLevel, route = '/d/cabinet') {
  const commitments = mockAll()
  renderCabinet(
    <Routes>
      <Route path="/d/cabinet/*" element={<CabinetRoutes />} />
    </Routes>,
    { level, route },
  )
  return commitments
}

const tab = (key: string) => screen.getByRole('tab', { name: t(`cabinet.tabs.${key}`) })

it('moves between the sections with the tabs', async () => {
  const requests = renderRoutes('viewer')
  const user = userEvent.setup()
  expect(await screen.findByRole('heading', { name: t('cabinet.title') })).toBeInTheDocument()

  await user.click(tab('meetings'))
  await waitFor(() => expect(tab('meetings')).toHaveAttribute('aria-selected', 'true'))
  await user.click(tab('commitments'))
  await screen.findByRole('table', { name: t('cabinet.tabs.commitments') })
  await user.click(tab('mine'))
  await screen.findByRole('table', { name: t('cabinet.tabs.mine') })
  expect(requests[requests.length - 1].url.searchParams.get('mine')).toBe('true')
  await user.click(tab('summary'))

  expect(await screen.findByRole('table', { name: t('cabinet.summary.byOwner') })).toBeInTheDocument()
})

it.each([
  ['meetings/me-1', 'meetings', t('cabinet.meeting.title', { date: '23/11/2026' })],
  ['meetings/new', 'meetings', t('cabinet.prepare.title')],
  ['commitments/co-1', 'commitments', 'Certificar la obra'],
])('opens %s', async (path, section, title) => {
  renderRoutes('editor', `/d/cabinet/${path}`)

  expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
  expect(tab(section)).toHaveAttribute('aria-selected', 'true')
})

it('keeps viewers from preparing meetings', async () => {
  renderRoutes('viewer', '/d/cabinet/meetings/new')

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
})

it('leads unknown addresses to the summary', async () => {
  renderRoutes('viewer', '/d/cabinet/nowhere')

  expect(await screen.findByRole('table', { name: t('cabinet.summary.byOwner') })).toBeInTheDocument()
})

it('is reached from the app at its own address', async () => {
  mockAll()
  renderCabinet(<App />, { level: 'viewer', route: '/d/cabinet' })

  expect(await screen.findByRole('heading', { name: t('cabinet.title') })).toBeInTheDocument()
})
