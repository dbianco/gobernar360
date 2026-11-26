import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import App from '../../App'
import locale from '../../locales/es-AR.json'
import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { MapSettingsForm } from './MapSettingsForm'
import { SettingsScopeContext } from './scope'
import { CENTRO } from '../geo/testData'
import { BACKGROUNDS, MAP_SETTINGS, SATELLITE } from './testData'
import type { MapSettings, MunicipalitySettings } from './types'

const label = (key: string, options = {}) => t(`settings.map.${key}`, options)
const name = (key: string) => label(`backgrounds.${key}.name`)
const SETTINGS: MunicipalitySettings = {
  notification_emails: [],
  sso_enabled: false,
  sso_available: false,
  ...MAP_SETTINGS,
}

function renderForm(settings: Partial<MunicipalitySettings> = {}) {
  const current = { ...SETTINGS, ...settings }
  mockApi('get', '/admin/settings', () => current as never)
  mockApi('get', '/admin/email-templates', [])
  const saved = mockApi('put', '/admin/settings/map', (request) => {
    Object.assign(current, request.body)
    return current as never
  })
  renderApp(<App />, { me: makeMe({ isAdmin: true }), route: '/admin/settings/maps' })
  return { user: userEvent.setup(), saved }
}

const select = () => screen.findByRole('combobox', { name: label('background') })
const save = () => screen.getByRole('button', { name: label('save') })
const keyField = (provider: string) =>
  screen.getByRole('textbox', { name: label('apiKey', { provider }) })
const threshold = () => screen.getByRole('textbox', { name: label('threshold') })
const tile = async () =>
  (await screen.findByRole('region', { name: label('preview') }))
    .querySelector('img.leaflet-tile')
    ?.getAttribute('src')

it('offers every background of the list, with and without key', async () => {
  renderForm()

  const groups = within(await select())
  const offered = (group: string) =>
    within(groups.getByRole('group', { name: label(group) }))
      .getAllByRole('option')
      .map((option) => option.textContent)
  expect(offered('withoutKey')).toEqual(
    BACKGROUNDS.filter((b) => !b.provider).map((b) => name(b.key)),
  )
  expect(offered('withKey')).toEqual(BACKGROUNDS.filter((b) => b.provider).map((b) => name(b.key)))
  // Each with a name and a description of its own, not the key of a missing text.
  const texts = locale.settings.map.backgrounds
  const all = [...BACKGROUNDS, SATELLITE]
  expect(Object.keys(texts).sort()).toEqual(all.map((b) => b.key).sort())
  expect(new Set(Object.values(texts).map((text) => text.name)).size).toBe(all.length)
})

it('offers the satellite image where there is one, and says whose servers it uses', async () => {
  const { user, saved } = renderForm({ map_backgrounds: [...BACKGROUNDS, SATELLITE] })

  await user.selectOptions(await select(), name('satellite'))

  expect(screen.getByText(label('backgrounds.satellite.description'))).toBeInTheDocument()
  const frame = await screen.findByRole('region', { name: label('preview') })
  await waitFor(async () => expect(await tile()).toContain('satellite.test'))
  expect(within(frame).getByText(/Pleiades Neo 2023/)).toBeInTheDocument()
  // Around the town there is no image, which is not a failure.
  fireEvent.error(frame.querySelector('img.leaflet-tile')!)
  expect(await screen.findByText(t('geo.map.noSatellite'))).toBeInTheDocument()
  expect(screen.queryByText(t('geo.map.noBackground'))).toBeNull()
  await user.click(save())
  await waitFor(() =>
    expect(saved[0]?.body).toEqual({
      small_zone_threshold: 5,
      map_background: 'satellite',
      map_api_key: null,
    }),
  )
})

it('shows how the map looks before saving it, and saves it', async () => {
  mockApi('get', '/zones', [CENTRO])
  const { user, saved } = renderForm()
  await select()
  await waitFor(async () => expect(await tile()).toContain('tile.openstreetmap.org'))
  // Over the municipality's own zones, to recognise the place.
  expect(
    within(screen.getByRole('region', { name: label('preview') })).getByText('Centro'),
  ).toBeInTheDocument()

  await user.selectOptions(await select(), name('topographic'))
  expect(screen.getByText(label('backgrounds.topographic.description'))).toBeInTheDocument()
  await waitFor(async () => expect(await tile()).toContain('topographic.test'))
  await user.click(save())

  expect(await screen.findByText(t('settings.saved'))).toBeInTheDocument()
  expect(saved[0].body).toEqual({
    small_zone_threshold: 5,
    map_background: 'topographic',
    map_api_key: null,
  })
  await user.selectOptions(await select(), name('france'))
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('asks for the key of the provider, and tries the map with it', async () => {
  const { user, saved } = renderForm()
  await user.selectOptions(await select(), name('cycle'))

  expect(screen.getByText(label('previewNeedsKey'))).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: label('preview') })).toBeNull()
  expect(save()).toBeDisabled()
  await user.type(keyField('Thunderforest'), 'a&b')
  expect(screen.getByText(label('apiKeyInvalid'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.clear(keyField('Thunderforest'))
  await user.type(keyField('Thunderforest'), ' abc123 ')
  await waitFor(async () => expect(await tile()).toMatch(/cycle\.test.*key=abc123$/))
  await user.click(save())

  await waitFor(() => expect(saved).toHaveLength(1))
  expect((saved[0].body as MapSettings).map_api_key).toBe('abc123')
})

it('keeps a key for other maps of its provider, and no other', async () => {
  const { user } = renderForm({ map_background: 'cycle', map_api_key: 'abc123' })
  await select()
  expect(keyField('Thunderforest')).toHaveValue('abc123')

  await user.selectOptions(await select(), name('transport'))
  expect(keyField('Thunderforest')).toHaveValue('abc123')
  await user.selectOptions(await select(), name('maptiler'))
  expect(keyField('MapTiler')).toHaveValue('')
})

it('sends no key with a background that needs none', async () => {
  const { user, saved } = renderForm({ map_background: 'cycle', map_api_key: 'abc123' })
  await user.selectOptions(await select(), name('standard'))
  expect(screen.queryByRole('textbox', { name: /Thunderforest/ })).toBeNull()

  await user.click(save())

  await waitFor(() => expect(saved).toHaveLength(1))
  expect((saved[0].body as MapSettings).map_api_key).toBeNull()
})

it('sets from how many a zone is shown, within its limits', async () => {
  const { user, saved } = renderForm()
  await select()
  expect(threshold()).toHaveValue('5')

  for (const wrong of ['1', '101', '']) {
    await user.clear(threshold())
    if (wrong) await user.type(threshold(), wrong)
    expect(screen.getByText(label('thresholdInvalid', { min: 2, max: 100 }))).toBeInTheDocument()
    expect(save()).toBeDisabled()
  }
  await user.clear(threshold())
  await user.type(threshold(), '10')
  await user.click(save())

  await waitFor(() => expect(saved).toHaveLength(1))
  expect((saved[0].body as MapSettings).small_zone_threshold).toBe(10)
})

it('says why it was not saved', async () => {
  const { user } = renderForm()
  mockApiError('put', '/admin/settings/map', 422, 'map_api_key_required')
  await select()

  await user.click(save())

  expect(await screen.findByText(t('errors.map_api_key_required'))).toBeInTheDocument()
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('says when the background being tried does not load', async () => {
  renderForm()
  await select()
  const frame = await screen.findByRole('region', { name: label('preview') })
  await waitFor(() => expect(frame.querySelector('img.leaflet-tile')).not.toBeNull())

  fireEvent.error(frame.querySelector('img.leaflet-tile')!)

  expect(await screen.findByText(t('geo.map.noBackground'))).toBeInTheDocument()
})

it('lets the operator choose without seeing anything of the municipality', async () => {
  const zones = mockApi('get', '/zones', [])
  const own = mockApi('get', '/map-background', {})
  const facilities = mockApi('get', '/geo/reference-layers', [])
  const saved = mockApi('put', '/platform/municipalities/m-1/settings/map', SETTINGS as never)
  const scope = {
    base: '/platform/municipalities/m-1',
    path: '/platform/municipalities/m-1/settings',
    key: ['platform', 'm-1'],
  }
  renderApp(
    <SettingsScopeContext.Provider value={scope}>
      <MapSettingsForm settings={SETTINGS} />
    </SettingsScopeContext.Provider>,
    { me: makeMe({ isOperator: true, municipalities: [], active: null }) },
  )
  const user = userEvent.setup()
  await waitFor(async () => expect(await tile()).toContain('tile.openstreetmap.org'))

  await user.click(save())

  await waitFor(() => expect(saved).toHaveLength(1))
  expect([zones.length, own.length, facilities.length]).toEqual([0, 0, 0])
})
