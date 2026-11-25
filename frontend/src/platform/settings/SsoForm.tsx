import { Alert, Stack, Switch, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../errorMessage'
import type { MunicipalitySettings } from './types'
import { useSaveSettings } from './useSaveSettings'

/** Whether members may sign in with the platform's identity provider. */
export function SsoForm({ settings }: { settings: MunicipalitySettings }) {
  const { t } = useTranslation()
  const save = useSaveSettings()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function toggle(enabled: boolean) {
    setPending(true)
    setError(null)
    try {
      await save({ notification_emails: settings.notification_emails, sso_enabled: enabled })
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <Stack>
      <Title order={3}>{t('settings.sso.title')}</Title>
      {error && <Alert color="red">{error}</Alert>}
      {!settings.sso_available && <Alert color="yellow">{t('settings.sso.unavailable')}</Alert>}
      <Switch
        label={t('settings.sso.label')}
        description={t('settings.sso.hint')}
        checked={settings.sso_enabled}
        // It can always be turned off, even once the platform lost its provider.
        disabled={pending || (!settings.sso_available && !settings.sso_enabled)}
        onChange={(event) => void toggle(event.currentTarget.checked)}
      />
    </Stack>
  )
}
