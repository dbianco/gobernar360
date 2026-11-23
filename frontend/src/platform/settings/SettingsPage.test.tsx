import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import App from '../../App'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import type { EmailTemplate, MunicipalitySettings } from './types'
import { answerConfirm } from '../../test/confirm'

const SETTINGS: MunicipalitySettings = {
  notification_emails: ['jefa@noetinger.test'],
  sso_enabled: false,
  sso_available: true,
}

const INVITATION: EmailTemplate = {
  key: 'invitation',
  subject: 'Te dieron acceso a {{municipality}}',
  html: '<p>Hola, {{name}}: <a href="{{link}}">elegí tu contraseña</a></p>',
  customized: false,
  variables: ['name', 'inviter', 'municipality', 'link', 'expires'],
  required: ['link'],
}
const RESET: EmailTemplate = {
  key: 'password_reset',
  subject: 'Elegí una contraseña nueva',
  html: '<p>{{link}}</p>',
  customized: true,
  variables: ['name', 'link', 'expires'],
  required: ['link'],
}

afterEach(() => vi.restoreAllMocks())

function renderSettings(settings = SETTINGS, templates = [INVITATION, RESET]) {
  mockApi('get', '/admin/settings', settings)
  mockApi('get', '/admin/email-templates', templates)
  return renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/settings' })
}

it('is a tab next to the users of the municipality', async () => {
  mockApi('get', '/overview', [])
  mockApi('get', '/admin/users', { items: [], total: 0 })
  mockApi('get', '/admin/dashboards', [])
  renderSettings()
  const user = userEvent.setup()

  expect(await screen.findByRole('heading', { name: t('settings.title') })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: t('admin.tabs.users') }))

  expect(await screen.findByRole('heading', { name: t('users.title') })).toBeInTheDocument()
})

it('is not reachable for members who are not administrators', async () => {
  mockApi('get', '/overview', [])
  renderApp(<App />, { me: makeMe({ isAdmin: false }), route: '/admin/settings' })

  expect(await screen.findByRole('heading', { name: t('overview.title') })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: t('settings.title') })).toBeNull()
})

it('saves the list of recipients typed with commas', async () => {
  const requests = mockApi('put', '/admin/settings', {
    ...SETTINGS,
    notification_emails: ['jefa@noetinger.test', 'prensa@example.test'],
  })
  renderSettings()
  const user = userEvent.setup()

  const field = await screen.findByLabelText(t('settings.recipients.label'))
  expect(field).toHaveValue('jefa@noetinger.test')
  await user.clear(field)
  await user.type(field, 'jefa@noetinger.test,  prensa@example.test ,')
  await user.click(screen.getByRole('button', { name: t('settings.recipients.save') }))

  expect(await screen.findByText(t('settings.saved'))).toBeInTheDocument()
  expect(requests[0].body).toEqual({
    notification_emails: ['jefa@noetinger.test', 'prensa@example.test'],
    sso_enabled: false,
  })
  expect(field).toHaveValue('jefa@noetinger.test, prensa@example.test')
})

it('points out malformed addresses without saving', async () => {
  const requests = mockApi('put', '/admin/settings', SETTINGS)
  renderSettings()
  const user = userEvent.setup()

  const field = await screen.findByLabelText(t('settings.recipients.label'))
  await user.type(field, ', no-es-un-email')
  await user.click(screen.getByRole('button', { name: t('settings.recipients.save') }))

  expect(
    await screen.findByText(t('settings.recipients.invalid', { emails: 'no-es-un-email' })),
  ).toBeInTheDocument()
  expect(requests).toHaveLength(0)
})

it('turns single sign-on on for the municipality', async () => {
  const requests = mockApi('put', '/admin/settings', { ...SETTINGS, sso_enabled: true })
  renderSettings()
  const user = userEvent.setup()

  const toggle = await screen.findByRole('switch', {
    name: (name) => name.startsWith(t('settings.sso.label')),
  })
  expect(toggle).not.toBeChecked()
  await user.click(toggle)

  await waitFor(() => expect(toggle).toBeChecked())
  expect(requests[0].body).toEqual({
    notification_emails: ['jefa@noetinger.test'],
    sso_enabled: true,
  })
})

it('explains that single sign-on needs a provider the platform does not have', async () => {
  renderSettings({ ...SETTINGS, sso_available: false })

  expect(await screen.findByText(t('settings.sso.unavailable'))).toBeInTheDocument()
  expect(
    screen.getByRole('switch', { name: (name) => name.startsWith(t('settings.sso.label')) }),
  ).toBeDisabled()
})

it('shows each email with its text, and whether it is the default', async () => {
  renderSettings()
  const user = userEvent.setup()

  expect(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
  ).toHaveValue(INVITATION.subject)
  expect(screen.getByText(t('settings.templates.default'))).toBeInTheDocument()
  expect(await screen.findByText('elegí tu contraseña')).toBeInTheDocument()

  await user.selectOptions(
    screen.getByRole('combobox', { name: t('settings.templates.choose') }),
    t('settings.templates.keys.password_reset.label'),
  )

  expect(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
  ).toHaveValue(RESET.subject)
  expect(screen.getByText(t('settings.templates.customized'))).toBeInTheDocument()
})

it('inserts a variable in the subject and saves the text', async () => {
  const requests = mockApi('put', '/admin/email-templates/invitation', {
    ...INVITATION,
    subject: 'Hola {{name}}',
    customized: true,
  })
  renderSettings()
  const user = userEvent.setup()
  const save = () => screen.getByRole('button', { name: t('settings.templates.save') })

  const subject = await screen.findByLabelText(t('settings.templates.subject'), { exact: false })
  expect(save()).toBeDisabled()
  await user.clear(subject)
  await user.type(subject, 'Hola ')
  await user.click(
    screen.getByRole('button', {
      name: t('settings.templates.insertNamed', { name: t('settings.variables.name') }),
    }),
  )
  await waitFor(() => expect(subject).toHaveValue('Hola {{name}}'))
  await user.click(save())

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(requests[0].body).toEqual({ subject: 'Hola {{name}}', html: INVITATION.html })
})

it('says which required variable a text lost', async () => {
  mockApi(
    'put',
    '/admin/email-templates/invitation',
    {
      error: {
        code: 'template_missing_variable',
        message: 'The text lacks required variables.',
        details: [{ field: 'html', message: 'link' }],
      },
    },
    422,
  )
  renderSettings()
  const user = userEvent.setup()

  await user.type(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
    '!',
  )
  await user.click(screen.getByRole('button', { name: t('settings.templates.save') }))

  expect(
    await screen.findByText(t('settings.templates.missingVariables', { variables: '{{link}}' })),
  ).toBeInTheDocument()
})

it('sends the administrator a test of the text being edited', async () => {
  const requests = mockApi('post', '/admin/email-templates/invitation/test', null, 204)
  renderSettings()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('settings.templates.test') }))

  expect(
    await screen.findByText(t('settings.templates.testSent', { email: 'ana@noetinger.test' })),
  ).toBeInTheDocument()
  expect(requests[0].body).toEqual({ subject: INVITATION.subject, html: INVITATION.html })
})

it('goes back to the default text after confirming', async () => {
  const requests = mockApi('delete', '/admin/email-templates/password_reset', RESET)
  renderSettings(SETTINGS, [{ ...RESET }])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('settings.templates.restore') }))
  const question = await answerConfirm(user, true, t('settings.templates.restore'))

  await waitFor(() => expect(requests).toHaveLength(1))
  expect(question).toContain(t('settings.templates.restoreConfirm'))
})

it('offers the formatting tools of the editor', async () => {
  renderSettings()

  const toolbar = await screen.findByRole('toolbar', { name: t('settings.editor.toolbar') })

  for (const tool of ['bold', 'italic', 'bulletList', 'link']) {
    expect(
      within(toolbar).getByRole('button', { name: t(`settings.editor.${tool}`) }),
    ).toBeInTheDocument()
  }
})

it('shows an error when the texts cannot be loaded', async () => {
  mockApi('get', '/admin/settings', SETTINGS)
  mockApiError('get', '/admin/email-templates', 500, 'generic')
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/settings' })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

const MILESTONES: EmailTemplate = {
  key: 'milestone_overdue',
  subject: 'Hitos vencidos en {{municipality}}',
  html: '<p>Hola:</p>{{items}}',
  customized: false,
  variables: ['municipality', 'month', 'items', 'account_link'],
  required: ['items'],
}
const insertButton = (variable: string) =>
  screen.getByRole('button', {
    name: t('settings.templates.insertNamed', { name: t(`settings.variables.${variable}`) }),
  })

it('inserts a variable in the body by default, and saves it', async () => {
  const saved = mockApi('put', '/admin/email-templates/invitation', {
    ...INVITATION,
    customized: true,
  })
  renderSettings()
  const user = userEvent.setup()
  await screen.findByText('elegí tu contraseña')

  await user.click(insertButton('inviter'))
  expect(await screen.findByText(t('settings.templates.unsaved'))).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('settings.templates.save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
  expect((saved[0].body as { html: string }).html).toContain('{{inviter}}')
  expect((saved[0].body as { subject: string }).subject).toBe(INVITATION.subject)
})

it('never puts the list of alerts in the subject', async () => {
  renderSettings(SETTINGS, [MILESTONES])
  const user = userEvent.setup()
  const subject = await screen.findByLabelText(t('settings.templates.subject'), { exact: false })

  await user.click(subject)
  await user.click(insertButton('items'))

  expect(subject).toHaveValue(MILESTONES.subject)
  expect(screen.getByText(t('settings.templates.requiredHint'))).toBeInTheDocument()
})

it('asks before leaving an email with unsaved changes', async () => {
  renderSettings()
  const user = userEvent.setup()
  const subject = await screen.findByLabelText(t('settings.templates.subject'), { exact: false })
  await user.type(subject, ' ya')
  const chooser = screen.getByRole('combobox', { name: t('settings.templates.choose') })

  await user.selectOptions(chooser, t('settings.templates.keys.password_reset.label'))
  await answerConfirm(user, false, t('settings.templates.discardTitle'))
  expect(subject).toHaveValue(`${INVITATION.subject} ya`)

  await user.selectOptions(chooser, t('settings.templates.keys.password_reset.label'))
  await answerConfirm(user, true, t('settings.templates.discardTitle'))
  expect(await screen.findByDisplayValue(RESET.subject)).toBeInTheDocument()
})

it('keeps the text when going back to the default is not confirmed', async () => {
  const restored = mockApi('delete', '/admin/email-templates/password_reset', RESET)
  renderSettings(SETTINGS, [{ ...RESET }])
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('settings.templates.restore') }))
  await answerConfirm(user, false, t('settings.templates.restore'))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(restored).toHaveLength(0)
})

it('shows other errors of saving or testing as they come', async () => {
  mockApiError('post', '/admin/email-templates/invitation/test', 500, 'generic')
  renderSettings()
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: t('settings.templates.test') }))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('says why the recipients could not be saved', async () => {
  mockApiError('put', '/admin/settings', 500, 'generic')
  renderSettings()
  const user = userEvent.setup()

  await screen.findByLabelText(t('settings.recipients.label'))
  await user.click(screen.getByRole('button', { name: t('settings.recipients.save') }))

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('says why single sign-on could not be changed, and leaves it as it was', async () => {
  mockApiError('put', '/admin/settings', 500, 'generic')
  renderSettings()
  const user = userEvent.setup()

  const toggle = await screen.findByRole('switch', {
    name: (name) => name.startsWith(t('settings.sso.label')),
  })
  await user.click(toggle)

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
  expect(toggle).not.toBeChecked()
})

it('says why the settings cannot be loaded', async () => {
  mockApiError('get', '/admin/settings', 500, 'generic')
  mockApi('get', '/admin/email-templates', [INVITATION])
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/settings' })

  expect(await screen.findByText(t('errors.generic'))).toBeInTheDocument()
})

it('lets the notice and the error of an email be closed', async () => {
  mockApi('post', '/admin/email-templates/invitation/test', null, 204)
  renderSettings()
  const user = userEvent.setup()
  const closeOf = (text: string) =>
    within(screen.getByText(text).closest('[role="alert"]') as HTMLElement).getByRole('button')

  await user.click(await screen.findByRole('button', { name: t('settings.templates.test') }))
  const notice = t('settings.templates.testSent', { email: 'ana@noetinger.test' })
  await screen.findByText(notice)
  await user.click(closeOf(notice))
  expect(screen.queryByText(notice)).toBeNull()

  mockApiError('post', '/admin/email-templates/invitation/test', 500, 'generic')
  await user.click(screen.getByRole('button', { name: t('settings.templates.test') }))
  await screen.findByText(t('errors.generic'))
  await user.click(closeOf(t('errors.generic')))
  expect(screen.queryByText(t('errors.generic'))).toBeNull()
})

it('names no variable when the server does not say which ones a text lacks', async () => {
  mockApi(
    'put',
    '/admin/email-templates/invitation',
    { error: { code: 'template_unknown_variable', message: 'Unknown variables.' } },
    422,
  )
  renderSettings()
  const user = userEvent.setup()

  await user.type(
    await screen.findByLabelText(t('settings.templates.subject'), { exact: false }),
    '!',
  )
  await user.click(screen.getByRole('button', { name: t('settings.templates.save') }))

  expect(
    await screen.findByText(t('settings.templates.unknownVariables', { variables: '' })),
  ).toBeInTheDocument()
})

it('stays on the email already shown when it is chosen again', async () => {
  renderSettings()
  const user = userEvent.setup()
  const subject = await screen.findByLabelText(t('settings.templates.subject'), { exact: false })
  await user.type(subject, ' ya')

  await user.selectOptions(
    screen.getByRole('combobox', { name: t('settings.templates.choose') }),
    t('settings.templates.keys.invitation.label'),
  )

  expect(screen.queryByRole('dialog')).toBeNull()
  expect(subject).toHaveValue(`${INVITATION.subject} ya`)
})
