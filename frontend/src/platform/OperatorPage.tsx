import {
  Alert,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { errorMessage } from './errorMessage'
import type { Municipality } from './types'
import { useAction } from './useAction'
import { UserForm } from './UserForm'

interface MunicipalityDetail extends Municipality {
  dashboards: string[]
}

/** Platform operator: municipalities, the dashboards each one has, and their administrators. */
export function OperatorPage() {
  const { t } = useTranslation()
  const municipalities = useQuery({
    queryKey: ['platform', 'municipalities'],
    queryFn: () => api<MunicipalityDetail[]>('/platform/municipalities'),
  })
  const registered = useQuery({
    queryKey: ['platform', 'dashboards'],
    queryFn: () => api<string[]>('/platform/dashboards'),
  })
  const action = useAction(['platform', 'me'])
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [kind, setKind] = useState('municipality')
  const [adminFor, setAdminFor] = useState<MunicipalityDetail | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const dashboardName = (key: string) => t(dashboardLabelKey(key) ?? key)

  async function create(event: FormEvent) {
    event.preventDefault()
    const created = await action.run(() =>
      api('/platform/municipalities', {
        method: 'POST',
        body: { name: name.trim(), slug: slug.trim(), kind },
      }),
    )
    if (created) {
      setName('')
      setSlug('')
    }
  }

  function toggle(municipality: MunicipalityDetail, key: string, enabled: boolean) {
    const keys = enabled
      ? [...municipality.dashboards, key]
      : municipality.dashboards.filter((existing) => existing !== key)
    void action.run(() =>
      api(`/platform/municipalities/${municipality.id}/dashboards`, {
        method: 'PUT',
        body: { keys },
      }),
    )
  }

  return (
    <Stack>
      <Title order={2}>{t('platform.title')}</Title>
      {action.error && (
        <Alert color="red" withCloseButton onClose={action.clearError}>
          {action.error}
        </Alert>
      )}
      {notice && (
        <Alert color="green" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      {municipalities.isLoading && <Loader aria-label={t('app.loading')} />}
      {municipalities.isError && <Alert color="red">{errorMessage(municipalities.error)}</Alert>}
      {municipalities.data?.length === 0 && <Text c="dimmed">{t('platform.empty')}</Text>}
      {municipalities.data?.map((municipality) => (
        <Paper key={municipality.id} withBorder p="md">
          <Group justify="space-between" align="flex-start">
            <Stack gap={4}>
              <Title order={4}>{municipality.name}</Title>
              <Text size="sm" c="dimmed">
                {t(`platform.kinds.${municipality.kind}`)} · {municipality.slug}
              </Text>
            </Stack>
            <Button
              variant="default"
              size="xs"
              aria-label={t('platform.createAdminFor', { name: municipality.name })}
              onClick={() => setAdminFor(municipality)}
            >
              {t('platform.createAdmin')}
            </Button>
          </Group>
          <Text size="sm" mt="sm" mb={4}>
            {t('platform.dashboardsFor')}
          </Text>
          <Group>
            {registered.data?.map((key) => (
              <Checkbox
                key={key}
                label={dashboardName(key)}
                aria-label={t('platform.dashboardIn', {
                  dashboard: dashboardName(key),
                  name: municipality.name,
                })}
                checked={municipality.dashboards.includes(key)}
                onChange={(event) => toggle(municipality, key, event.currentTarget.checked)}
              />
            ))}
          </Group>
        </Paper>
      ))}

      <Paper withBorder p="md">
        <form onSubmit={(event) => void create(event)}>
          <Group align="flex-end" gap="sm">
            <TextInput
              label={t('platform.name')}
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <TextInput
              label={t('platform.slug')}
              description={t('platform.slugHint')}
              required
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              maxLength={100}
              value={slug}
              onChange={(event) => setSlug(event.currentTarget.value)}
            />
            <NativeSelect
              label={t('platform.kind')}
              value={kind}
              onChange={(event) => setKind(event.currentTarget.value)}
              data={[
                { value: 'municipality', label: t('platform.kinds.municipality') },
                { value: 'commune', label: t('platform.kinds.commune') },
              ]}
            />
            <Button type="submit" loading={action.pending}>
              {t('platform.add')}
            </Button>
          </Group>
        </form>
      </Paper>

      <Modal
        opened={adminFor !== null}
        onClose={() => setAdminFor(null)}
        title={adminFor ? t('platform.createAdminFor', { name: adminFor.name }) : ''}
      >
        {adminFor && (
          <UserForm
            dashboards={[]}
            adminOf={adminFor.id}
            onCancel={() => setAdminFor(null)}
            onDone={(email) => {
              setAdminFor(null)
              setNotice(t('platform.adminCreated', { email }))
            }}
          />
        )}
      </Modal>
    </Stack>
  )
}
