import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { mockApi, mockApiError } from '../../test/server'
import { GeographyForm } from './GeographyForm'
import { SettingsScopeContext } from './scope'
import { MAP_SETTINGS } from './testData'
import type { MunicipalitySettings } from './types'

const label = (key: string) => t(`settings.geography.${key}`)
const LAYER = 'Localidades:Cordoba_Noetinger_2023'
const SETTINGS: MunicipalitySettings = {
  notification_emails: [],
  sso_enabled: false,
  sso_available: false,
  ...MAP_SETTINGS,
}
const URL = '/platform/municipalities/m-1/settings/geography'

function renderAsOperator(settings: Partial<MunicipalitySettings> = {}) {
  const scope = {
    base: '/platform/municipalities/m-1',
    path: '/platform/municipalities/m-1/settings',
    key: ['platform', 'm-1'],
  }
  renderApp(
    <SettingsScopeContext.Provider value={scope}>
      <GeographyForm settings={{ ...SETTINGS, ...settings }} />
    </SettingsScopeContext.Provider>,
    { me: makeMe({ isOperator: true, municipalities: [], active: null }) },
  )
  return userEvent.setup()
}

const keyField = () => screen.getByRole('textbox', { name: label('idecorKey') })
const layerField = () => screen.getByRole('textbox', { name: label('conaeLayer') })
const save = () => screen.getByRole('button', { name: label('save') })

it('lets the operator say where the municipality is', async () => {
  const saved = mockApi('put', URL, SETTINGS as never)
  const user = renderAsOperator()

  await user.type(keyField(), ' 360124 ')
  await user.type(layerField(), LAYER)
  await user.click(save())

  expect(await screen.findByText(t('settings.saved'))).toBeInTheDocument()
  expect(saved[0].body).toEqual({ idecor_key: '360124', conae_layer: LAYER })
  await user.type(keyField(), '{Backspace}')
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('clears them', async () => {
  const saved = mockApi('put', URL, SETTINGS as never)
  const user = renderAsOperator({ idecor_key: '360124', conae_layer: LAYER })

  await user.clear(keyField())
  await user.clear(layerField())
  await user.click(save())

  await waitFor(() => expect(saved[0]?.body).toEqual({ idecor_key: null, conae_layer: null }))
})

it('says what is not a key or a layer before sending it', async () => {
  const user = renderAsOperator()

  await user.type(keyField(), '36012')
  expect(screen.getByText(label('idecorKeyInvalid'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
  await user.type(keyField(), '4')
  expect(screen.queryByText(label('idecorKeyInvalid'))).toBeNull()
  expect(save()).toBeEnabled()
  await user.type(layerField(), 'una capa')
  expect(screen.getByText(label('conaeLayerInvalid'))).toBeInTheDocument()
  expect(save()).toBeDisabled()
})

it('says why they were not saved', async () => {
  mockApiError('put', URL, 403, 'forbidden')
  const user = renderAsOperator()

  await user.click(save())

  expect(await screen.findByText(t('errors.forbidden'))).toBeInTheDocument()
  expect(screen.queryByText(t('settings.saved'))).toBeNull()
})

it('shows them to the administrator, who cannot change them', () => {
  renderApp(<GeographyForm settings={{ ...SETTINGS, idecor_key: '360124' }} />, {
    me: makeMe({ isAdmin: true }),
  })

  expect(keyField()).toHaveValue('360124')
  expect(keyField()).toHaveAttribute('readonly')
  expect(layerField()).toHaveAttribute('readonly')
  expect(layerField()).toHaveAttribute('placeholder', label('notSet'))
  expect(screen.getByText(label('introReadOnly'))).toBeInTheDocument()
  expect(screen.queryByRole('button')).toBeNull()
})
