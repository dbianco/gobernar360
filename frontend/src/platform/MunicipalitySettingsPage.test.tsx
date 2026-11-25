import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../App'
import { makeMe, NOETINGER } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { mockApi, mockApiError } from '../test/server'
import type { EmailTemplate, MunicipalitySettings } from './settings/types'

const OPERATOR = makeMe({ isOperator: true, municipalities: [] })
const BASE = `/platform/municipalities/${NOETINGER.id}`
const SETTINGS: MunicipalitySettings = {
  notification_emails: ['jefa@noetinger.test'],
  sso_enabled: false,
  sso_available: true,
}
const RESET: EmailTemplate = {
  key: 'password_reset',
  subject: 'Elegí una contraseña nueva',
  html: '<p>{{link}}</p>',
  customized: true,
  variables: ['name', 'link', 'expires'],
  required: ['link'],
}

function renderPage(options: { me?: ReturnType<typeof makeMe>; id?: string } = {}) {
  mockApi('get', '/platform/municipalities', [{ ...NOETINGER, dashboards: ['projects'] }])
  mockApi('get', `${BASE}/settings`, SETTINGS)
  mockApi('get', `${BASE}/email-templates`, [RESET])
  return renderApp(<App />, {
    me: options.me ?? OPERATOR,
    route: `/platform/municipalities/${options.id ?? NOETINGER.id}/settings`,
  })
}

it('shows the operator the configuration of the municipality, with a way back', async () => {
  renderPage()

  expect(await screen.findByLabelText(t('settings.recipients.label'))).toHaveValue(
    'jefa@noetinger.test',
  )
  expect(screen.getByRole('heading', { name: 'Noetinger' })).toBeInTheDocument()
  expect(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
  ).toHaveValue(RESET.subject)
  expect(screen.getByRole('link', { name: t('platform.backToMunicipality') })).toHaveAttribute(
    'href',
    `/platform/municipalities/${NOETINGER.id}`,
  )
})

it('saves what the operator changes in that municipality', async () => {
  const settings = mockApi('put', `${BASE}/settings`, { ...SETTINGS, sso_enabled: true })
  const template = mockApi('put', `${BASE}/email-templates/password_reset`, {
    ...RESET,
    subject: 'Elegí una contraseña nueva ya',
  })
  renderPage()
  const user = userEvent.setup()

  const toggle = await screen.findByRole('switch', {
    name: (name) => name.startsWith(t('settings.sso.label')),
  })
  await user.click(toggle)
  await waitFor(() => expect(settings).toHaveLength(1))
  expect(settings[0].body).toEqual({
    notification_emails: ['jefa@noetinger.test'],
    sso_enabled: true,
  })
  await waitFor(() => expect(toggle).toBeChecked())

  await user.type(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
    ' ya',
  )
  await user.click(screen.getByRole('button', { name: t('settings.templates.save') }))
  await waitFor(() => expect(template).toHaveLength(1))
  expect(template[0].body).toEqual({ subject: 'Elegí una contraseña nueva ya', html: RESET.html })
})

it('says so when the municipality does not exist', async () => {
  renderPage({ id: 'missing' })

  expect(await screen.findByText(t('platform.notFound'))).toBeInTheDocument()
  expect(screen.queryByLabelText(t('settings.recipients.label'))).toBeNull()
})

it('keeps the configuration of a municipality away from non-operators', async () => {
  mockApi('get', '/overview', [])
  renderPage({ me: makeMe({ isAdmin: true }) })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
})

it('says when the municipality cannot be loaded', async () => {
  renderPage()
  mockApiError('get', '/platform/municipalities', 500, 'boom')

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('platform.notFound'))).toBeNull()
  expect(screen.getByRole('link', { name: t('platform.backToMunicipality') })).toBeInTheDocument()
})
