import { Alert, Anchor, Button, Stack, Text, TextInput, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import { api } from '../api/client'
import { errorMessage } from './errorMessage'
import type { LoginState } from './LoginPage'
import { PublicCard } from './PublicCard'

/**
 * "Forgot my password": asks for a recovery link. The answer is the same whether or not
 * the email has an account, so the page never tells which addresses exist.
 */
export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const [email, setEmail] = useState((location.state as LoginState | null)?.email ?? '')
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await api('/auth/password-reset', { method: 'POST', body: { email: email.trim() } })
      setSentTo(email.trim())
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <PublicCard>
      <form onSubmit={(event) => void submit(event)}>
        <Stack>
          <Title order={2}>{t('passwordReset.title')}</Title>
          {sentTo ? (
            <Alert color="green">{t('passwordReset.sent', { email: sentTo })}</Alert>
          ) : (
            <>
              <Text size="sm">{t('passwordReset.intro')}</Text>
              {error && <Alert color="red">{error}</Alert>}
              <TextInput
                label={t('passwordReset.email')}
                type="email"
                autoComplete="username"
                required
                withAsterisk={false}
                value={email}
                onChange={(event) => setEmail(event.currentTarget.value)}
              />
              <Button type="submit" loading={pending}>
                {t('passwordReset.submit')}
              </Button>
            </>
          )}
          <Anchor component={Link} to="/login" size="sm" ta="center">
            {t('passwordReset.backToLogin')}
          </Anchor>
        </Stack>
      </form>
    </PublicCard>
  )
}
