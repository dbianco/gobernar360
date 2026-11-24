import {
  Alert,
  Button,
  Divider,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError } from '../api/client'
import { useAuth } from './authContext'
import { errorMessage } from './errorMessage'
import type { Me } from './types'
import { useAction } from './useAction'

const MIN_PASSWORD_LENGTH = 10
// Same rule as the API: digits and the usual separators.
const PHONE = /^[0-9+()\-. ]*$/

interface NotificationSetting {
  kind: string
  enabled: boolean
}

/** Name, contact phone and password. Every change needs the current password; a new
 * password is optional and, left empty, the current one stays. */
function AccountForm({ me }: { me: Me }) {
  const { t } = useTranslation()
  const { updateMe } = useAuth()
  const [fullName, setFullName] = useState(me.user.full_name)
  const [phone, setPhone] = useState(me.user.phone)
  const [next, setNext] = useState('')
  const [current, setCurrent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<'done' | 'donePassword' | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setDone(null)
    if (!PHONE.test(phone.trim())) {
      setError(t('account.phoneInvalid'))
      return
    }
    if (next !== '' && next.length < MIN_PASSWORD_LENGTH) {
      setError(t('users.passwordTooShort'))
      return
    }
    setPending(true)
    setError(null)
    try {
      const updated = await api<Me>('/auth/account', {
        method: 'PUT',
        body: {
          current_password: current,
          full_name: fullName,
          phone,
          new_password: next === '' ? null : next,
        },
      })
      updateMe(updated)
      setFullName(updated.user.full_name)
      setPhone(updated.user.phone)
      setDone(next === '' ? 'done' : 'donePassword')
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
        {done && <Alert color="green">{t(`account.${done}`)}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        <TextInput
          label={t('account.email')}
          description={t('account.emailHint')}
          value={me.user.email}
          readOnly
          variant="filled"
        />
        <TextInput
          label={t('account.fullName')}
          required
          maxLength={200}
          autoComplete="name"
          value={fullName}
          onChange={(event) => setFullName(event.currentTarget.value)}
        />
        <TextInput
          label={t('account.phone')}
          description={t('account.phoneHint')}
          type="tel"
          maxLength={50}
          autoComplete="tel"
          value={phone}
          onChange={(event) => setPhone(event.currentTarget.value)}
        />
        <Divider label={t('account.passwordSection')} labelPosition="left" />
        <PasswordInput
          label={t('account.new')}
          description={t('account.newHint')}
          autoComplete="new-password"
          value={next}
          onChange={(event) => setNext(event.currentTarget.value)}
        />
        <Divider label={t('account.confirmSection')} labelPosition="left" />
        <PasswordInput
          label={t('account.current')}
          description={t('account.currentHint')}
          required
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.currentTarget.value)}
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

/** The signed-in user's own account and email notifications. */
export function AccountPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  return (
    <Stack maw={520}>
      <Title order={2}>{t('account.title')}</Title>
      {/* The form starts from the user's data, so it waits for them. */}
      {me && (
        <Paper withBorder p="md">
          <AccountForm me={me} />
        </Paper>
      )}
      <Paper withBorder p="md">
        <NotificationSettings />
      </Paper>
    </Stack>
  )
}
