import { Alert, Button, Group, Stack, Textarea, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../errorMessage'
import type { MunicipalitySettings } from './types'
import { useSaveSettings } from './useSaveSettings'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** Addresses typed in a list separated by commas (or semicolons, spaces, new lines). */
function parseEmails(text: string): string[] {
  return text
    .split(/[\s,;]+/)
    .map((email) => email.trim())
    .filter(Boolean)
}

/** Who receives the notification emails. */
export function RecipientsForm({ settings }: { settings: MunicipalitySettings }) {
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
          placeholder={t('settings.recipients.placeholder')}
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
