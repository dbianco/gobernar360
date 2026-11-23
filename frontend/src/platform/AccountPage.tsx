import {
  Alert,
  Button,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError } from '../api/client'
import { useAuth } from './authContext'
import { errorMessage } from './errorMessage'
import { useAction } from './useAction'

const MIN_PASSWORD_LENGTH = 10

interface NotificationSetting {
  kind: string
  enabled: boolean
}

/** Lets the signed-in user replace their password. */
function PasswordForm() {
  const { t } = useTranslation()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setDone(false)
    if (next.length < MIN_PASSWORD_LENGTH) {
      setError(t('users.passwordTooShort'))
      return
    }
    setPending(true)
    setError(null)
    try {
      await api('/auth/password', {
        method: 'POST',
        body: { current_password: current, new_password: next },
      })
      setDone(true)
      setCurrent('')
      setNext('')
    } catch (caught) {
      const wrongCurrent = caught instanceof ApiError && caught.code === 'invalid_credentials'
      setError(wrongCurrent ? t('account.wrongCurrent') : errorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack>
        <Title order={3}>{t('account.passwordTitle')}</Title>
        {done && <Alert color="green">{t('account.done')}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        <PasswordInput
          label={t('account.current')}
          required
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.currentTarget.value)}
        />
        <PasswordInput
          label={t('account.new')}
          description={t('account.newHint')}
          required
          autoComplete="new-password"
          value={next}
          onChange={(event) => setNext(event.currentTarget.value)}
        />
        <Button type="submit" loading={pending}>
          {t('account.submit')}
        </Button>
      </Stack>
    </form>
  )
}

/** One switch per kind of email notification. */
function NotificationSettings() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const settings = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<NotificationSetting[]>('/auth/notifications'),
  })
  const action = useAction(['notifications'])

  return (
    <Stack>
      <Title order={3}>{t('account.notifications.title')}</Title>
      <Text size="sm" c="dimmed">
        {t('account.notifications.hint', { email: me?.user.email })}
      </Text>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {settings.isLoading && <Loader aria-label={t('app.loading')} />}
      {settings.isError && <Alert color="red">{errorMessage(settings.error)}</Alert>}
      {settings.data?.map((setting) => (
        <Switch
          key={setting.kind}
          label={t([`account.notifications.kinds.${setting.kind}.label`, setting.kind])}
          description={t(`account.notifications.kinds.${setting.kind}.description`, {
            defaultValue: '',
          })}
          checked={setting.enabled}
          disabled={action.pending}
          onChange={(event) => {
            const enabled = event.currentTarget.checked
            void action.run(() =>
              api(`/auth/notifications/${setting.kind}`, { method: 'PUT', body: { enabled } }),
            )
          }}
        />
      ))}
    </Stack>
  )
}

/** The signed-in user's password and email notifications. */
export function AccountPage() {
  const { t } = useTranslation()
  return (
    <Stack maw={520}>
      <Title order={2}>{t('account.title')}</Title>
      <Paper withBorder p="md">
        <PasswordForm />
      </Paper>
      <Paper withBorder p="md">
        <NotificationSettings />
      </Paper>
    </Stack>
  )
}
