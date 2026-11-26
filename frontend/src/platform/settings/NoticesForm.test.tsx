import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError, NO_NOTICE_SETTINGS } from '../../test/server'
import { NoticesForm } from './NoticesForm'
import { SettingsScopeContext } from './scope'
import type { NoticeSettings } from './types'

const label = (key: string, options = {}) => t(`settings.notices.${key}`, options)
const EMPTY = NO_NOTICE_SETTINGS as NoticeSettings
const CONNECTED: NoticeSettings = {
  ...EMPTY,
  adhesion_state: 'approved',
  adhesion_date: '2026-08-01',
  adhesion_file: '0423-1/2026',
  system_name: 'gobernar360 – Noetinger',
  publication_url: 'https://noetinger.example',
  contact: 'sistemas@noetinger.test',
  secrets: [{ name: 'api_key', set_at: '2026-08-02T12:00:00Z' }],
  missing: [],
}

async function renderForm(settings: NoticeSettings = CONNECTED) {
  let current = settings
  mockApi('get', '/admin/settings/notices', () => current as never)
  const saved = mockApi('put', '/admin/settings/notices', (request) => {
    const { secrets, removed_secrets, ...fields } = request.body as {
      secrets: { name: string }[]
      removed_secrets: string[]
    }
    current = {
      ...current,
      ...fields,
      secrets: [
        ...current.secrets.filter(({ name }) => !removed_secrets.includes(name)),
        ...secrets.map(({ name }) => ({ name, set_at: '2026-11-23T12:00:00Z' })),
      ],
    }
    return current as never
  })
  renderApp(<NoticesForm />, { me: makeMe({ isAdmin: true }) })
  await screen.findByRole('combobox', { name: label('channel') })
  return { user: userEvent.setup(), saved }
}

const channel = () => screen.getByRole('combobox', { name: label('channel') })
const field = (key: string) => screen.getByRole('textbox', { name: label(key) })
const secretValue = () => screen.getByLabelText(label('secretValue'))
const save = () => screen.getByRole('button', { name: label('save') })
const missing = (...names: string[]) =>
  label('missing', { fields: names.map((name) => label(`missingFields.${name}`)).join(', ') })

it('chooses how residents are told, once the adhesion is complete', async () => {
  const { user, saved } = await renderForm()
  expect(channel()).toHaveValue('email')

  await user.selectOptions(channel(), label('channels.cidi_then_email'))
  await user.type(field('ordinance'), 'Ordenanza 12.985')
  await user.click(save())

  expect(await screen.findByText(t('settings.saved'))).toBeInTheDocument()
  expect(saved[0].body).toEqual({
    resident_notice_channel: 'cidi_then_email',
    cidi_ordinance: 'Ordenanza 12.985',
    adhesion_state: 'approved',
    adhesion_date: '2026-08-01',
    adhesion_file: '0423-1/2026',
    system_name: 'gobernar360 – Noetinger',
    publication_url: 'https://noetinger.example',
    contact: 'sistemas@noetinger.test',
    secrets: [],
    removed_secrets: [],
  })
  await user.type(field('ordinance'), '!')
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('says what is missing before CiDi can be chosen, and offers it when nothing is', async () => {
  const { user } = await renderForm(EMPTY)
  const offered = () =>
    within(channel())
      .getAllByRole('option')
      .filter((option) => !(option as HTMLOptionElement).disabled)
      .map((option) => option.textContent)

  expect(
    screen.getByText(missing('adhesion', 'system_name', 'publication_url', 'contact')),
  ).toBeInTheDocument()
  expect(offered()).toEqual([label('channels.email')])
  await user.selectOptions(
    screen.getByRole('combobox', { name: label('adhesionState') }),
    label('adhesionStates.approved'),
  )
  await user.type(field('systemName'), 'gobernar360 – Noetinger')
  await user.type(field('publicationUrl'), 'https://noetinger.example')
  expect(screen.getByText(missing('contact'))).toBeInTheDocument()
  await user.type(field('contact'), 'Ana')

  expect(offered()).toEqual([
    label('channels.email'),
    label('channels.cidi_then_email'),
    label('channels.cidi'),
  ])
})

it('does not save CiDi without what it needs', async () => {
  const { user } = await renderForm({ ...CONNECTED, resident_notice_channel: 'cidi' })
  expect(channel()).toHaveValue('cidi')

  await user.clear(field('contact'))

  expect(screen.getByText(missing('contact'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.selectOptions(channel(), label('channels.email'))
  expect(save()).toBeEnabled()
})

it('saves a secret and never shows it again', async () => {
  const { user, saved } = await renderForm({ ...CONNECTED, secrets: [] })
  expect(screen.getByText(label('noSecrets'))).toBeInTheDocument()

  await user.type(field('secretName'), 'token')
  expect(save()).toBeDisabled()
  await user.type(secretValue(), 's3cr3t')
  expect(secretValue()).toHaveAttribute('type', 'password')
  await user.click(save())

  expect(
    await screen.findByText(label('secretSet', { date: '23/11/2026 09:00' })),
  ).toBeInTheDocument()
  expect(saved[0].body).toMatchObject({ secrets: [{ name: 'token', value: 's3cr3t' }] })
  expect(field('secretName')).toHaveValue('')
  expect(secretValue()).toHaveValue('')
  expect(document.body.innerHTML).not.toContain('s3cr3t')
})

it('removes a secret when saving, and not before', async () => {
  const { user, saved } = await renderForm()
  const remove = () =>
    screen.getByRole('button', { name: label('removeSecretNamed', { name: 'api_key' }) })

  await user.click(remove())
  expect(screen.getByText(label('secretRemoved'))).toBeInTheDocument()
  await user.click(
    screen.getByRole('button', { name: label('keepSecretNamed', { name: 'api_key' }) }),
  )
  expect(screen.getByText(label('secretSet', { date: '02/08/2026 09:00' }))).toBeInTheDocument()
  await user.click(remove())
  await user.click(save())

  expect(await screen.findByText(label('noSecrets'))).toBeInTheDocument()
  expect(saved[0].body).toMatchObject({ secrets: [], removed_secrets: ['api_key'] })
})

it('says what is not a name for a secret, and which already have their field', async () => {
  const { user } = await renderForm()

  await user.type(secretValue(), 'x')
  expect(save()).toBeDisabled()
  await user.type(field('secretName'), 'Api Key')
  expect(screen.getByText(label('secretNameInvalid'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.clear(field('secretName'))
  await user.type(field('secretName'), 'contact')
  expect(screen.getByText(label('secretNamePlain'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.clear(field('secretName'))
  await user.type(field('secretName'), 'api_key')
  expect(save()).toBeEnabled()
})

it('says what is not an address', async () => {
  const { user } = await renderForm()

  await user.clear(field('publicationUrl'))
  await user.type(field('publicationUrl'), 'noetinger.example')

  expect(screen.getByText(label('urlInvalid'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
})

it('says when the installation reaches no CiDi and keeps no secrets', async () => {
  await renderForm({ ...EMPTY, cidi_available: false, secrets_available: false })

  expect(screen.getByText(label('unavailable'))).toBeInTheDocument()
  expect(screen.getByText(label('secretsUnavailable'))).toBeInTheDocument()
  expect(field('secretName')).toBeDisabled()
  expect(secretValue()).toBeDisabled()
})

it('says neither when it does', async () => {
  await renderForm()

  expect(screen.queryByText(label('unavailable'))).toBeNull()
  expect(screen.queryByText(label('secretsUnavailable'))).toBeNull()
})

it('changes how far the adhesion is', async () => {
  const { user, saved } = await renderForm({ ...EMPTY })

  await user.selectOptions(
    screen.getByRole('combobox', { name: label('adhesionState') }),
    label('adhesionStates.requested'),
  )
  await user.type(screen.getByLabelText(label('adhesionDate')), '15/11/2026')
  await user.type(field('adhesionFile'), '0423-9/2026')
  await user.click(save())

  await waitFor(() =>
    expect(saved[0]?.body).toMatchObject({
      adhesion_state: 'requested',
      adhesion_date: '2026-11-15',
      adhesion_file: '0423-9/2026',
    }),
  )
})

it('clears the date of the adhesion', async () => {
  const { user, saved } = await renderForm()

  await user.clear(screen.getByLabelText(label('adhesionDate')))
  await user.click(save())

  await waitFor(() => expect(saved[0]?.body).toMatchObject({ adhesion_date: null }))
})

it('keeps what was typed and says why it was not saved', async () => {
  const { user } = await renderForm()
  mockApiError('put', '/admin/settings/notices', 409, 'secrets_key_missing')

  await user.type(field('secretName'), 'token')
  await user.type(secretValue(), 'x')
  await user.click(save())

  expect(await screen.findByText(t('errors.secrets_key_missing'))).toBeInTheDocument()
  expect(field('secretName')).toHaveValue('token')
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('offers the request to the Province to print', async () => {
  await renderForm()

  const link = screen.getByRole('link', { name: label('adhesionRequest') })
  expect(link).toHaveAttribute('href', '/api/admin/settings/notices/adhesion-request')
  expect(link).toHaveAttribute('target', '_blank')
})

it('says why it cannot be read', async () => {
  mockApiError('get', '/admin/settings/notices', 403, 'forbidden')
  renderApp(<NoticesForm />, { me: makeMe({ isAdmin: true }) })

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
})

it('is the same for the operator, of the municipality in the address', async () => {
  const url = '/platform/municipalities/m-1/settings/notices'
  mockApi('get', url, CONNECTED as never)
  const saved = mockApi('put', url, CONNECTED as never)
  const scope = {
    base: '/platform/municipalities/m-1',
    path: '/platform/municipalities/m-1/settings',
    key: ['platform', 'm-1'],
    own: false,
  }
  renderApp(
    <SettingsScopeContext.Provider value={scope}>
      <NoticesForm />
    </SettingsScopeContext.Provider>,
    { me: makeMe({ isOperator: true, municipalities: [], active: null }) },
  )
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: label('save') }))

  await waitFor(() => expect(saved).toHaveLength(1))
})
