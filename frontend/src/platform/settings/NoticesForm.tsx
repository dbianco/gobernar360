import {
  Alert,
  Anchor,
  Button,
  Group,
  List,
  Loader,
  NativeSelect,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, downloadUrl } from '../../api/client'
import { DateField } from '../DateField'
import { errorMessage } from '../errorMessage'
import { formatDateTime } from '../format'
import { useSettingsScope } from './scope'
import { ADHESION_STATES, NOTICE_CHANNELS, type NoticeSettings } from './types'

// The same rules the API has.
const PLAIN = ['system_name', 'publication_url', 'contact'] as const
const SECRET_NAME = /^[a-z][a-z0-9_]{0,49}$/
const ADDRESS = /^https?:\/\/\S+$/

type Fields = Omit<
  NoticeSettings,
  'secrets' | 'missing' | 'cidi_available' | 'secrets_available'
>

const fieldsOf = (settings: NoticeSettings): Fields => ({
  resident_notice_channel: settings.resident_notice_channel,
  cidi_ordinance: settings.cidi_ordinance,
  adhesion_state: settings.adhesion_state,
  adhesion_date: settings.adhesion_date,
  adhesion_file: settings.adhesion_file,
  system_name: settings.system_name,
  publication_url: settings.publication_url,
  contact: settings.contact,
})

/** What is needed before CiDi can be chosen, as the form stands. */
function missingFrom(fields: Fields): string[] {
  const lacking = fields.adhesion_state === 'approved' ? [] : ['adhesion']
  return [...lacking, ...PLAIN.filter((name) => fields[name].trim() === '')]
}

function Form({ settings }: { settings: NoticeSettings }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { base, noticesKey } = useSettingsScope()
  const [fields, setFields] = useState(() => fieldsOf(settings))
  const [removed, setRemoved] = useState<string[]>([])
  const [secret, setSecret] = useState({ name: '', value: '' })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [pending, setPending] = useState(false)
  const label = (name: string, options = {}) => t(`settings.notices.${name}`, options)

  const missing = missingFrom(fields)
  const usesCidi = fields.resident_notice_channel !== 'email'
  const secretName = secret.name.trim()
  const namesPlain = (PLAIN as readonly string[]).includes(secretName)
  const secretNameError =
    secretName === ''
      ? null
      : namesPlain
        ? 'secretNamePlain'
        : SECRET_NAME.test(secretName)
          ? null
          : 'secretNameInvalid'
  // One without the other is half typed.
  const halfSecret = (secretName === '') !== (secret.value === '')
  const url = fields.publication_url.trim()
  const urlInvalid = url !== '' && !ADDRESS.test(url)
  const invalid = secretNameError !== null || halfSecret || urlInvalid || (usesCidi && missing.length > 0)

  function set<K extends keyof Fields>(name: K, value: Fields[K]) {
    setFields((current) => ({ ...current, [name]: value }))
    setSaved(false)
  }
  const text = (name: keyof Fields) => ({
    value: fields[name] ?? '',
    onChange: (event: { currentTarget: { value: string } }) =>
      set(name, event.currentTarget.value),
  })

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    setPending(true)
    setError(null)
    try {
      const result = await api<NoticeSettings>(`${base}/settings/notices`, {
        method: 'PUT',
        body: {
          ...fields,
          secrets: secretName === '' ? [] : [{ name: secretName, value: secret.value }],
          removed_secrets: removed,
        },
      })
      queryClient.setQueryData(noticesKey, result)
      setFields(fieldsOf(result))
      setRemoved([])
      // It is not kept on the screen either.
      setSecret({ name: '', value: '' })
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
        <Title order={3}>{label('title')}</Title>
        <Text size="sm">{label('intro')}</Text>
        {saved && <Alert color="green">{t('settings.saved')}</Alert>}
        {error && <Alert color="red">{error}</Alert>}
        {!settings.cidi_available && <Alert color="yellow">{label('unavailable')}</Alert>}
        <NativeSelect
          label={label('channel')}
          description={label('channelHint')}
          value={fields.resident_notice_channel}
          onChange={(event) =>
            set(
              'resident_notice_channel',
              event.currentTarget.value as Fields['resident_notice_channel'],
            )
          }
          error={
            usesCidi &&
            missing.length > 0 &&
            label('missing', {
              fields: missing.map((name) => label(`missingFields.${name}`)).join(', '),
            })
          }
          data={NOTICE_CHANNELS.map((value) => ({
            value,
            label: label(`channels.${value}`),
            // The one in use stays, so that the form says what it lacks.
            disabled:
              value !== 'email' && missing.length > 0 && value !== fields.resident_notice_channel,
          }))}
        />
        {missing.length > 0 && !usesCidi && (
          <Text size="sm" c="dimmed">
            {label('missing', {
              fields: missing.map((name) => label(`missingFields.${name}`)).join(', '),
            })}
          </Text>
        )}
        <TextInput
          label={label('ordinance')}
          description={label('ordinanceHint')}
          maxLength={200}
          {...text('cidi_ordinance')}
        />

        <Title order={4}>{label('connection')}</Title>
        <Text size="sm">
          {label('adhesionIntro')}{' '}
          <Anchor
            href={downloadUrl(`${base}/settings/notices/adhesion-request`)}
            target="_blank"
            rel="noopener noreferrer"
          >
            {label('adhesionRequest')}
          </Anchor>
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <NativeSelect
            label={label('adhesionState')}
            value={fields.adhesion_state}
            onChange={(event) =>
              set('adhesion_state', event.currentTarget.value as Fields['adhesion_state'])
            }
            data={ADHESION_STATES.map((value) => ({
              value,
              label: label(`adhesionStates.${value}`),
            }))}
          />
          <DateField
            label={label('adhesionDate')}
            value={fields.adhesion_date ?? ''}
            onChange={(value) => set('adhesion_date', value || null)}
          />
          <TextInput label={label('adhesionFile')} maxLength={100} {...text('adhesion_file')} />
        </SimpleGrid>
        <TextInput
          label={label('systemName')}
          description={label('systemNameHint')}
          maxLength={200}
          {...text('system_name')}
        />
        <TextInput
          label={label('publicationUrl')}
          maxLength={500}
          error={urlInvalid && label('urlInvalid')}
          {...text('publication_url')}
        />
        <TextInput
          label={label('contact')}
          description={label('contactHint')}
          maxLength={200}
          {...text('contact')}
        />

        <Title order={4}>{label('secrets')}</Title>
        <Text size="sm">{label('secretsHint')}</Text>
        {!settings.secrets_available && (
          <Alert color="yellow">{label('secretsUnavailable')}</Alert>
        )}
        {settings.secrets.length === 0 ? (
          <Text size="sm" c="dimmed">
            {label('noSecrets')}
          </Text>
        ) : (
          <List listStyleType="none" spacing="xs" aria-label={label('secrets')}>
            {settings.secrets.map(({ name, set_at }) => {
              const leaving = removed.includes(name)
              return (
                <List.Item key={name}>
                  <Group gap="sm">
                    <Text size="sm" fw={600}>
                      {name}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {leaving
                        ? label('secretRemoved')
                        : label('secretSet', { date: formatDateTime(set_at) })}
                    </Text>
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      color={leaving ? undefined : 'red'}
                      aria-label={label(leaving ? 'keepSecretNamed' : 'removeSecretNamed', {
                        name,
                      })}
                      onClick={() => {
                        setRemoved(
                          leaving ? removed.filter((other) => other !== name) : [...removed, name],
                        )
                        setSaved(false)
                      }}
                    >
                      {label(leaving ? 'keepSecret' : 'removeSecret')}
                    </Button>
                  </Group>
                </List.Item>
              )
            })}
          </List>
        )}
        <SimpleGrid cols={{ base: 1, sm: 2 }} style={{ alignItems: 'end' }}>
          <TextInput
            label={label('secretName')}
            description={label('secretNameHint')}
            maxLength={50}
            disabled={!settings.secrets_available}
            error={secretNameError && label(secretNameError)}
            value={secret.name}
            onChange={(event) => {
              setSecret({ ...secret, name: event.currentTarget.value })
              setSaved(false)
            }}
          />
          <PasswordInput
            label={label('secretValue')}
            maxLength={20_000}
            autoComplete="off"
            disabled={!settings.secrets_available}
            value={secret.value}
            onChange={(event) => {
              setSecret({ ...secret, value: event.currentTarget.value })
              setSaved(false)
            }}
          />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button type="submit" loading={pending} disabled={invalid}>
            {label('save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

/** How residents are told what happened to what they asked for. */
export function NoticesForm() {
  const { t } = useTranslation()
  const { base, noticesKey } = useSettingsScope()
  const settings = useQuery({
    queryKey: noticesKey,
    queryFn: () => api<NoticeSettings>(`${base}/settings/notices`),
  })

  if (settings.isError) return <Alert color="red">{errorMessage(settings.error)}</Alert>
  if (!settings.data) return <Loader aria-label={t('app.loading')} />
  return <Form settings={settings.data} />
}
