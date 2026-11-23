import {
  Alert,
  Button,
  Group,
  Loader,
  Paper,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { EmailTemplatesPanel } from './EmailTemplatesPanel'
import { type MunicipalitySettings, SETTINGS_KEY } from './types'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** Addresses typed in a list separated by commas (or semicolons, spaces, new lines). */
function parseEmails(text: string): string[] {
  return text
    .split(/[\s,;]+/)
    .map((email) => email.trim())
    .filter(Boolean)
}

function useSaveSettings() {
  const queryClient = useQueryClient()
  return async (body: Omit<MunicipalitySettings, 'sso_available'>) => {
    const saved = await api<MunicipalitySettings>('/admin/settings', { method: 'PUT', body })
    queryClient.setQueryData(SETTINGS_KEY, saved)
    return saved
  }
}

function RecipientsForm({ settings }: { settings: MunicipalitySettings }) {
  const { t } = useTranslation()
  const save = useSaveSettings()
  const [text, setText] = useState(settings.notification_emails.join(', '))
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    const emails = parseEmails(text)
    const invalid = emails.filter((email) => !EMAIL.test(email))
    if (invalid.length > 0) {
      setError(t('settings.recipients.invalid', { emails: invalid.join(', ') }))
      return
    }
    setPending(true)
    setError(null)
    try {
      const result = await save({ notification_emails: emails, sso_enabled: settings.sso_enabled })
      setText(result.notification_emails.join(', '))
      setSaved(true)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack>
        <Title order={3}>{t('settings.recipients.title')}</Title>
        {saved && <Alert color="green">{t('settings.saved')}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        <Textarea
          label={t('settings.recipients.label')}
          description={t('settings.recipients.hint')}
          placeholder="intendencia@municipio.gob.ar, prensa@municipio.gob.ar"
          autosize
          minRows={2}
          value={text}
          onChange={(event) => {
            setText(event.currentTarget.value)
            setSaved(false)
          }}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={pending}>
            {t('settings.recipients.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

function SsoForm({ settings }: { settings: MunicipalitySettings }) {
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

/** Configuración: what the municipality's administrators set for it. */
export function SettingsPage() {
  const { t } = useTranslation()
  const settings = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => api<MunicipalitySettings>('/admin/settings'),
  })

  return (
    <Stack maw={860}>
      <Title order={2}>{t('settings.title')}</Title>
      <Text c="dimmed">{t('settings.intro')}</Text>
      {settings.isLoading && <Loader aria-label={t('app.loading')} />}
      {settings.isError && <Alert color="red">{errorMessage(settings.error)}</Alert>}
      {settings.data && (
        <>
          <Paper withBorder p="md">
            <RecipientsForm settings={settings.data} />
          </Paper>
          <Paper withBorder p="md">
            <SsoForm settings={settings.data} />
          </Paper>
        </>
      )}
      <Paper withBorder p="md">
        <EmailTemplatesPanel />
      </Paper>
    </Stack>
  )
}
