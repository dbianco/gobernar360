import { Alert, Button, PasswordInput, Stack, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError } from '../api/client'
import { errorMessage } from './errorMessage'

const MIN_PASSWORD_LENGTH = 10

/** Lets the signed-in user replace their password, e.g. the initial one an administrator chose. */
export function AccountPage() {
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
      <Stack maw={420}>
        <Title order={2}>{t('account.title')}</Title>
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
