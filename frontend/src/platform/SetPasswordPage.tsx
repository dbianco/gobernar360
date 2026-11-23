import {
  Alert,
  Anchor,
  Button,
  Center,
  Loader,
  PasswordInput,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import { errorMessage } from './errorMessage'
import type { LoginState } from './LoginPage'
import { PublicCard } from './PublicCard'

const MIN_PASSWORD_LENGTH = 10

interface TokenInfo {
  purpose: 'invitation' | 'password_reset'
  email: string
  full_name: string
}

/**
 * Where invitation and recovery emails lead: the person chooses their password.
 * The token travels in the URL fragment, which browsers never send to a server.
 */
export function SetPasswordPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const token = location.hash.replace(/^#/, '')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const info = useQuery({
    queryKey: ['token', token],
    queryFn: () => api<TokenInfo>('/auth/tokens/inspect', { method: 'POST', body: { token } }),
    enabled: token !== '',
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setFormError(t('users.passwordTooShort'))
      return
    }
    if (password !== confirmation) {
      setFormError(t('setPassword.mismatch'))
      return
    }
    setPending(true)
    setFormError(null)
    try {
      await api('/auth/tokens/redeem', { method: 'POST', body: { token, password } })
    } catch (caught) {
      setPending(false)
      if (caught instanceof ApiError && caught.code === 'invalid_token') {
        // Used or expired meanwhile: show the same screen as an old link.
        await info.refetch()
      } else {
        setFormError(errorMessage(caught))
      }
      return
    }
    // Every session of the account was closed; forget the one this browser may have had.
    await queryClient.invalidateQueries({ queryKey: ['me'] })
    const state: LoginState = { notice: 'passwordSet', email: info.data?.email }
    navigate('/login', { replace: true, state })
  }

  const invalid =
    token === '' || (info.error instanceof ApiError && info.error.code === 'invalid_token')

  let content
  if (invalid) {
    content = (
      <>
        <Title order={2}>{t('setPassword.invalidTitle')}</Title>
        <Text>{t('setPassword.invalid')}</Text>
        <Button component={Link} to="/forgot-password">
          {t('setPassword.requestNew')}
        </Button>
      </>
    )
  } else if (info.isError) {
    content = <Alert color="red">{errorMessage(info.error)}</Alert>
  } else if (!info.data) {
    content = (
      <Center>
        <Loader aria-label={t('app.loading')} />
      </Center>
    )
  } else {
    const invitation = info.data.purpose === 'invitation'
    content = (
      <form onSubmit={(event) => void submit(event)}>
        <Stack>
          <Title order={2}>
            {t(invitation ? 'setPassword.invitationTitle' : 'setPassword.resetTitle')}
          </Title>
          <Text size="sm">
            {t(invitation ? 'setPassword.invitationIntro' : 'setPassword.resetIntro', {
              name: info.data.full_name,
              email: info.data.email,
            })}
          </Text>
          {formError && <Alert color="red">{formError}</Alert>}
          {/* Lets password managers store the new password under the right account. */}
          <input type="hidden" name="username" autoComplete="username" value={info.data.email} />
          <PasswordInput
            label={t('setPassword.password')}
            description={t('setPassword.hint')}
            required
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
          />
          <PasswordInput
            label={t('setPassword.confirm')}
            required
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.currentTarget.value)}
          />
          <Button type="submit" loading={pending}>
            {t('setPassword.submit')}
          </Button>
        </Stack>
      </form>
    )
  }

  return (
    <PublicCard>
      <Stack>
        {content}
        <Anchor component={Link} to="/login" size="sm" ta="center">
          {t('passwordReset.backToLogin')}
        </Anchor>
      </Stack>
    </PublicCard>
  )
}
