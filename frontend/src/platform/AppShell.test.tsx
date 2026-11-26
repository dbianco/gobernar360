import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { AppShell } from './AppShell'
import { MunicipalitySwitcher } from './MunicipalitySwitcher'
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
  expect(nav.getByRole('link', { name: t('commitments.section') })).toHaveAttribute(
    'href',
    '/commitments',
  )
  // Only the overview, the commitments, the one dashboard this build knows about, and help.
  expect(nav.getAllByRole('link')).toHaveLength(4)
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

  expect(nav.queryByRole('link', { name: t('nav.settings') })).not.toBeInTheDocument()
  expect(nav.queryByRole('link', { name: t('nav.settings') })).not.toBeInTheDocument()
  expect(nav.queryByRole('link', { name: t('nav.platform') })).not.toBeInTheDocument()
})

it('shows the configuration link to municipality admins, with the users and zones inside it', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe({ isAdmin: true }) })

  const nav = await navigation()

  expect(nav.queryByRole('link', { name: 'Usuarios' })).toBeNull()
  expect(nav.queryByRole('link', { name: 'Zonas' })).toBeNull()
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

  // Overview, commitments, four dashboards, settings, reports, public page, platform and help.
  expect(links).toHaveLength(11)
  for (const link of links) expect(link.querySelector('svg')).not.toBeNull()
})

it('signs out from an icon that says what it does on hover', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe() })

  const logout = await screen.findByRole('button', { name: t('app.logout') })
  expect(logout).not.toHaveTextContent(t('app.logout'))
  await userEvent.hover(logout)

  expect(await screen.findByRole('tooltip')).toHaveTextContent(t('app.logout'))
})

it('offers reports and the public page to municipality admins only', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe({ dashboards: { projects: 'admin' } }) })

  const links = (await navigation()).getAllByRole('link').map((link) => link.textContent)

  expect(links).not.toContain(t('nav.reports'))
  expect(links).not.toContain(t('nav.publication'))
})

it.each(['/admin/reports', '/admin/publication'])(
  'sends a member who is not an administrator from %s to the overview',
  async (route) => {
    mockApi('get', '/overview', [])
    renderApp(<App />, { me: makeMe({ dashboards: { projects: 'admin' } }), route })

    expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  },
)

it.each([
  ['/admin/reports', 'reports.title', '/reports'],
  ['/admin/publication', 'publication.title', '/publication'],
])('opens %s for a municipality administrator', async (route, title, path) => {
  const publication = { enabled: false, slug: 'x', small_count_threshold: 5, dashboards: [] }
  mockApi('get', path, path === '/reports' ? [] : publication)
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route })

  expect(await screen.findByRole('heading', { name: t(title), level: 2 })).toBeInTheDocument()
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

it('opens the configuration at /admin, and the old addresses of users and zones in it', async () => {
  mockApi('get', '/admin/settings', {} as never)
  mockApi('get', '/admin/email-templates', [])
  mockApi('get', '/admin/users', { items: [], total: 0 })
  mockApi('get', '/admin/dashboards', [])
  const home = renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin' })

  expect(await screen.findByRole('tab', { name: t('settings.tabs.emails') })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  home.unmount()

  const users = renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/users' })
  expect(await screen.findByRole('tab', { name: t('settings.tabs.users') })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  users.unmount()

  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/zones' })
  expect(await screen.findByRole('tab', { name: t('settings.tabs.maps') })).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

it('has a help link for everyone, which opens the guide', async () => {
  const { unmount } = renderApp(<App />, { me: makeMe(), route: '/help' })
  expect(await screen.findByRole('heading', { name: t('guide.title') })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: t('nav.help') })).toHaveAttribute('href', '/help')
  unmount()
})

it('shows what one owes and follows beside the name, and their pages', async () => {
  mockApi('get', '/commitments', { items: [], total: 0 })
  mockApi('get', '/notifications', { mine: [], others: [] })
  renderApp(<App />, { me: makeMe() })
  const user = userEvent.setup()

  await user.click(
    await screen.findByRole('link', { name: t('notices.newsLabel', { count: 0 }) }),
  )
  expect(await screen.findByRole('heading', { name: t('notices.title') })).toBeInTheDocument()
  await user.click((await navigation()).getByRole('link', { name: t('commitments.section') }))
  expect(
    await screen.findByRole('heading', { name: t('commitments.section') }),
  ).toBeInTheDocument()
})

it('has no notices without a municipality to have them in', async () => {
  renderApp(<App />, { me: makeMe({ municipalities: [], active: null }) })

  expect(await screen.findByText(t('municipality.noneTitle'))).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: t('notices.newsLabel', { count: 0 }) })).toBeNull()
  expect(screen.queryByRole('link', { name: t('commitments.section') })).toBeNull()
})

it('shows nothing of the frame to whoever is signed out', async () => {
  renderApp(
    <>
      <AppShell />
      <MunicipalitySwitcher />
      <p>signed out</p>
    </>,
    { me: null },
  )

  expect(await screen.findByText('signed out')).toBeInTheDocument()
  expect(screen.queryByRole('navigation')).toBeNull()
  expect(screen.queryByRole('button', { name: t('app.logout') })).toBeNull()
  expect(screen.queryByRole('combobox')).toBeNull()
})
