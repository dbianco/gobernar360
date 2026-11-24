import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { api, setMunicipalitySuspendedHandler } from '../api/client'
import App from '../App'
import { makeMe, NOETINGER, SAIRA } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

const WORKING = makeMe({ dashboards: { projects: 'viewer' } })
const SUSPENDED = makeMe({ municipalities: [], active: null, suspended: [NOETINGER] })

/** Answer /auth/me with each profile in turn, the last one from then on. */
function mockProfiles(...profiles: ReturnType<typeof makeMe>[]) {
  let call = 0
  return mockApi('get', '/auth/me', () => profiles[Math.min(call++, profiles.length - 1)])
}

it('tells the client when the municipality was suspended', async () => {
  const suspended = vi.fn()
  setMunicipalitySuspendedHandler(suspended)
  mockApiError('get', '/overview', 403, 'municipality_suspended')
  mockApiError('get', '/other', 403, 'forbidden')

  await expect(api('/other')).rejects.toMatchObject({ code: 'forbidden' })
  expect(suspended).not.toHaveBeenCalled()
  await expect(api('/overview')).rejects.toMatchObject({ code: 'municipality_suspended' })

  expect(suspended).toHaveBeenCalledOnce()
  setMunicipalitySuspendedHandler(null)
})

it('a member working when the municipality is suspended sees it at the next action', async () => {
  mockProfiles(WORKING, SUSPENDED)
  mockApiError('get', '/overview', 403, 'municipality_suspended')
  renderApp(<App />)

  expect(
    await screen.findByRole('heading', {
      name: t('municipality.suspendedTitle', { names: NOETINGER.name, count: 1 }),
    }),
  ).toBeInTheDocument()
  // Nothing of the municipality stays on screen or in the menu.
  const menu = within(screen.getByRole('navigation'))
  expect(menu.queryByRole('link', { name: t('projects.title') })).not.toBeInTheDocument()
  expect(screen.getByText(t('municipality.suspendedBody'))).toBeInTheDocument()
})

it('checking again after the operator resumes it brings the member back', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: SUSPENDED })
  const user = userEvent.setup()
  const check = await screen.findByRole('button', { name: t('municipality.checkAgain') })

  // The operator resumes it: from now on the profile has the municipality again.
  const profiles = mockApi('get', '/auth/me', WORKING)
  await user.click(check)

  expect(
    await within(screen.getByRole('navigation')).findByRole('link', { name: t('projects.title') }),
  ).toBeInTheDocument()
  expect(profiles.length).toBeGreaterThan(0)
})

it('offers only the municipalities that are not suspended', async () => {
  renderApp(<App />, {
    me: makeMe({ municipalities: [SAIRA], active: null, suspended: [NOETINGER] }),
  })

  expect(
    await screen.findByText(t('municipality.suspendedOthers', { names: NOETINGER.name, count: 1 })),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: SAIRA.name })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: NOETINGER.name })).not.toBeInTheDocument()
})

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })
const BASE = `/platform/municipalities/${NOETINGER.id}`
const SUSPENSION = {
  at: '2026-11-23T13:05:00Z',
  reason: 'Cambio de gestión',
  by: 'Operador de la plataforma',
}
const label = (key: string, options = {}) => t(`platform.suspension.${key}`, options)

function renderMunicipality(suspension: typeof SUSPENSION | null) {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: [], suspension }])
  mockApi('get', '/platform/dashboards', ['projects'])
  mockApi('get', `${BASE}/users`, [])
  mockApi('get', `${BASE}/dashboards`, [])
  return renderApp(<App />, { me: OPERATOR, route: BASE })
}

it('the operator suspends a municipality giving a reason', async () => {
  const requests = mockApi('post', `${BASE}/suspension`, {}, 201)
  renderMunicipality(null)
  const user = userEvent.setup()

  expect(await screen.findByText(label('active'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('suspend') }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('button', { name: label('suspend') }))
  expect(requests).toHaveLength(0)
  await user.type(dialog.getByRole('textbox', { name: label('reason') }), '  Cambio de gestión ')
  await user.click(dialog.getByRole('button', { name: label('suspend') }))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ reason: 'Cambio de gestión' })
})

it('the operator sees who suspended it, when and why, and resumes it', async () => {
  const requests = mockApi('delete', `${BASE}/suspension`, {})
  renderMunicipality(SUSPENSION)
  const user = userEvent.setup()

  expect(await screen.findAllByText(label('badge'))).not.toHaveLength(0)
  expect(
    screen.getByText(label('since', { at: '23/11/2026 10:05', by: SUSPENSION.by })),
  ).toBeInTheDocument()
  expect(
    screen.getByText(label('reasonShown', { reason: 'Cambio de gestión' })),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: label('resume') }))

  await waitFor(() => expect(requests).toHaveLength(1))
})

it('marks suspended municipalities in the operator list', async () => {
  mockApi('get', '/platform/municipalities', [
    { ...NOETINGER, dashboards: [], suspension: SUSPENSION },
    { ...SAIRA, dashboards: [], suspension: null },
  ])
  renderApp(<App />, { me: OPERATOR, route: '/platform' })

  const noetinger = await screen.findByRole('row', { name: new RegExp(NOETINGER.name) })
  expect(within(noetinger).getByText(label('badge'))).toBeInTheDocument()
  const saira = screen.getByRole('row', { name: new RegExp(SAIRA.name) })
  expect(within(saira).queryByText(label('badge'))).not.toBeInTheDocument()
})
