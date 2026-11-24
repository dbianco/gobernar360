import {
  Alert,
  Button,
  Divider,
  PasswordInput,
  Stack,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError } from '../api/client'
import { useAuth } from './authContext'
import { errorMessage } from './errorMessage'
import type { Me } from './types'

const MIN_PASSWORD_LENGTH = 10
// Same rule as the API: digits and the usual separators.
const PHONE = /^[0-9+()\-. ]*$/

/**
 * The signed-in user's own account: name, contact phone and password. Every change needs
 * the current password; a new password is optional and, left empty, the current one stays.
 */
export function AccountPage() {
  const { me } = useAuth()
  // The form starts from the user's data, so it waits for them.
  return me ? <AccountForm me={me} /> : null
}

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
      <Stack maw={460}>
        <Title order={2}>{t('account.title')}</Title>
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
