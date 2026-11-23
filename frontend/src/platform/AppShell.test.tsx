import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER, SAIRA } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'

const navigation = async () => within(await screen.findByRole('navigation'))

it('lists only the dashboards granted to the user', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe({ dashboards: { projects: 'viewer', unknown: 'admin' } }) })

  const nav = await navigation()

  expect(nav.getByRole('link', { name: t('nav.overview') })).toBeInTheDocument()
  expect(nav.getByRole('link', { name: t('projects.title') })).toBeInTheDocument()
  // Only the overview and the one dashboard this build knows about.
  expect(nav.getAllByRole('link')).toHaveLength(2)
})

it('does not list dashboards the user has no access to', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe() })

  const nav = await navigation()

  expect(nav.queryByRole('link', { name: t('projects.title') })).not.toBeInTheDocument()
})

it('hides the users link from non-admin members', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe() })

  const nav = await navigation()

  expect(nav.queryByRole('link', { name: t('nav.users') })).not.toBeInTheDocument()
  expect(nav.queryByRole('link', { name: t('nav.settings') })).not.toBeInTheDocument()
  expect(nav.queryByRole('link', { name: t('nav.platform') })).not.toBeInTheDocument()
})

it('shows the users and configuration links to municipality admins', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe({ isAdmin: true }) })

  const nav = await navigation()

  expect(nav.getByRole('link', { name: t('nav.users') })).toHaveAttribute('href', '/admin/users')
  expect(nav.getByRole('link', { name: t('nav.settings') })).toHaveAttribute(
    'href',
    '/admin/settings',
  )
})

it('shows the municipality switcher only with several memberships', async () => {
  mockApi('get', '/overview', [])
  const single = renderApp(<App />, { me: makeMe() })
  await navigation()
  expect(screen.queryByDisplayValue(NOETINGER.name)).not.toBeInTheDocument()
  expect(screen.getByText(NOETINGER.name)).toBeInTheDocument()
  single.unmount()

  renderApp(<App />, { me: makeMe({ municipalities: [NOETINGER, SAIRA] }) })

  expect(await screen.findByDisplayValue(NOETINGER.name)).toBeInTheDocument()
})

it('asks which municipality to work with when none is active', async () => {
  const me = makeMe({ municipalities: [NOETINGER, SAIRA], active: null })
  const requests = mockApi('post', '/auth/active-municipality', {
    ...me,
    active_municipality_id: SAIRA.id,
  })
  mockApi('get', '/overview', [])
  renderApp(<App />, { me })

  expect(await screen.findByText(t('municipality.choose'))).toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: SAIRA.name }))

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(requests[0].body).toEqual({ municipality_id: SAIRA.id })
})

it('explains the situation to a user without any municipality', async () => {
  renderApp(<App />, { me: makeMe({ municipalities: [] }) })

  expect(await screen.findByText(t('municipality.noneTitle'))).toBeInTheDocument()
})

it('blocks direct navigation to a dashboard the user cannot see', async () => {
  renderApp(<App />, { me: makeMe(), route: '/d/projects' })

  expect(await screen.findByText(t('dashboards.forbiddenTitle'))).toBeInTheDocument()
})

it('signs the user out', async () => {
  mockApi('get', '/overview', [])
  const requests = mockApi('post', '/auth/logout', null, 204)
  renderApp(<App />, { me: makeMe() })

  await userEvent.setup().click(await screen.findByRole('button', { name: t('app.logout') }))

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
  expect(requests).toHaveLength(1)
})

it('returns to the login page when the session has expired', async () => {
  mockApiError('get', '/overview', 401, 'not_authenticated')
  renderApp(<App />, { me: makeMe() })

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
})

it('signs out locally even when the request fails', async () => {
  mockApi('get', '/overview', [])
  mockApiError('post', '/auth/logout', 500, 'generic')
  renderApp(<App />, { me: makeMe() })

  await userEvent.setup().click(await screen.findByRole('button', { name: t('app.logout') }))

  expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument()
})

it('gives every navigation link an icon', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, {
    me: makeMe({
      isAdmin: true,
      isOperator: true,
      dashboards: { projects: 'admin', environment: 'admin', economic: 'admin', social: 'admin' },
    }),
  })

  const links = (await navigation()).getAllByRole('link')

  expect(links).toHaveLength(8)
  for (const link of links) expect(link.querySelector('svg')).not.toBeNull()
})

it('changes the municipality from the switcher', async () => {
  const me = makeMe({ municipalities: [NOETINGER, SAIRA] })
  const requests = mockApi('post', '/auth/active-municipality', {
    ...me,
    active_municipality_id: SAIRA.id,
  })
  renderApp(<App />, { me })
  const user = userEvent.setup()

  await user.click(await screen.findByDisplayValue(NOETINGER.name))
  await user.click(await screen.findByRole('option', { name: SAIRA.name }))

  expect(await screen.findByDisplayValue(SAIRA.name)).toBeInTheDocument()
  expect(requests[0].body).toEqual({ municipality_id: SAIRA.id })
})

it('opens the users of the municipality at /admin', async () => {
  mockApi('get', '/admin/users', { items: [], total: 0 })
  mockApi('get', '/admin/dashboards', [])
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin' })

  expect(await screen.findByRole('tab', { name: t('admin.tabs.users') })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})
