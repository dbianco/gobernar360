import {
  Alert,
  Anchor,
  Button,
  Divider,
  PasswordInput,
  Stack,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { useAuth } from './authContext'
import { errorMessage } from './errorMessage'
import { PublicCard } from './PublicCard'

/** What another page may tell the sign-in page, e.g. after a password was chosen. */
export interface LoginState {
  notice?: 'passwordSet'
  email?: string
}

const SSO_ERRORS = [
  'failed',
  'no_account',
  'not_allowed',
  'unverified_email',
  'cancelled',
  'disabled',
]

export function LoginPage() {
  const { t } = useTranslation()
  const { me, login } = useAuth()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const state = (location.state ?? {}) as LoginState
  const [email, setEmail] = useState(state.email ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const sso = useQuery({
    queryKey: ['sso'],
    queryFn: () => api<{ enabled: boolean }>('/auth/sso'),
    staleTime: Infinity,
  })

  if (me) return <Navigate to="/" replace />

  // The single sign-on callback sends the browser back here with what went wrong.
  const ssoError = searchParams.get('sso_error')
  const ssoMessage = ssoError
    ? t(`login.ssoErrors.${SSO_ERRORS.includes(ssoError) ? ssoError : 'failed'}`)
    : null

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
    } catch (caught) {
      setError(errorMessage(caught))
      setSubmitting(false)
    }
  }

  return (
    <PublicCard>
      <form onSubmit={submit}>
        <Stack>
          <Title order={2}>{t('login.title')}</Title>
          {state.notice === 'passwordSet' && !error && (
            <Alert color="green">{t('login.passwordSet')}</Alert>
          )}
          {ssoMessage && !error && <Alert color="red">{ssoMessage}</Alert>}
          {error && <Alert color="red">{error}</Alert>}
          <TextInput
            label={t('login.email')}
            type="email"
            autoComplete="username"
            required
            withAsterisk={false}
            value={email}
            onChange={(event) => setEmail(event.currentTarget.value)}
          />
          <PasswordInput
            label={t('login.password')}
            autoComplete="current-password"
            required
            withAsterisk={false}
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
          />
          <Button type="submit" loading={submitting}>
            {t('login.submit')}
          </Button>
          <Anchor component={Link} to="/forgot-password" state={{ email }} size="sm" ta="center">
            {t('login.forgot')}
          </Anchor>
          {sso.data?.enabled && (
            <>
              <Divider label={t('login.or')} labelPosition="center" />
              {/* A full page load: the browser leaves for the identity provider. */}
              <Button component="a" href="/api/auth/sso/start" variant="default">
                {t('login.sso')}
              </Button>
            </>
          )}
        </Stack>
      </form>
    </PublicCard>
  )
}
