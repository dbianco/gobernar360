import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  Loader,
  NativeSelect,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconSettings } from '@tabler/icons-react'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { errorMessage } from './errorMessage'
import { MembersPanel } from './MembersPanel'
import {
  KINDS,
  type MunicipalityDetail,
  useMunicipalities,
  useRegisteredDashboards,
} from './operatorApi'
import { useAction } from './useAction'

function DetailsForm({ municipality }: { municipality: MunicipalityDetail }) {
  const { t } = useTranslation()
  const action = useAction(['platform', 'me'])
  const [name, setName] = useState(municipality.name)
  const [kind, setKind] = useState(municipality.kind)
  const [saved, setSaved] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaved(false)
    if (!name.trim()) return
    const result = await action.run(() =>
      api(`/platform/municipalities/${municipality.id}`, {
        method: 'PATCH',
        body: { name: name.trim(), kind },
      }),
    )
    if (result) setSaved(true)
  }

  return (
    <form onSubmit={(event) => void submit(event)}>
      <Stack gap="sm">
        {action.error && <Alert color="red">{action.error}</Alert>}
        {saved && <Alert color="green">{t('platform.detailsSaved')}</Alert>}
        <Group align="flex-end" gap="sm">
          <TextInput
            label={t('platform.name')}
            required
            withAsterisk={false}
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
          <NativeSelect
            label={t('platform.kind')}
            value={kind}
            onChange={(event) => setKind(event.currentTarget.value)}
            data={KINDS.map((value) => ({
              value,
              label: t(`platform.kinds.${value}`),
            }))}
          />
          <Button type="submit" loading={action.pending}>
            {t('platform.saveDetails')}
          </Button>
        </Group>
        <Text size="sm" c="dimmed">
          {t('platform.slug')}: {municipality.slug}
        </Text>
      </Stack>
    </form>
  )
}

function DashboardsForm({ municipality }: { municipality: MunicipalityDetail }) {
  const { t } = useTranslation()
  const registered = useRegisteredDashboards()
  const action = useAction(['platform', 'me'])

  function toggle(key: string, enabled: boolean) {
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
    <Stack gap="sm">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <Group>
        {registered.data?.map((key) => (
          <Checkbox
            key={key}
            label={t(dashboardLabelKey(key) ?? key)}
            checked={municipality.dashboards.includes(key)}
            onChange={(event) => toggle(key, event.currentTarget.checked)}
          />
        ))}
      </Group>
      <Text size="sm" c="dimmed">
        {t('platform.dashboardsHint')}
      </Text>
    </Stack>
  )
}

/** Platform operator: everything configurable about one municipality. */
export function MunicipalityPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const municipalities = useMunicipalities()
  const municipality = municipalities.data?.find((item) => item.id === id)

  return (
    <Stack>
      <Anchor component={Link} to="/platform">
        {t('platform.back')}
      </Anchor>
      {municipalities.isLoading && <Loader aria-label={t('app.loading')} />}
      {municipalities.isError && <Alert color="red">{errorMessage(municipalities.error)}</Alert>}
      {municipalities.data && !municipality && (
        <Alert color="yellow">{t('platform.notFound')}</Alert>
      )}
      {municipality && (
        <>
          <Group justify="space-between">
            <Title order={2}>{municipality.name}</Title>
            <Button
              component={Link}
              to={`/platform/municipalities/${municipality.id}/settings`}
              variant="default"
              leftSection={<IconSettings size={18} stroke={1.5} aria-hidden />}
            >
              {t('platform.settings')}
            </Button>
          </Group>
          <Paper withBorder p="md">
            <Title order={3} mb="sm">
              {t('platform.details')}
            </Title>
            {/* Remounted when another municipality is opened, so the fields start from its data. */}
            <DetailsForm key={municipality.id} municipality={municipality} />
          </Paper>
          <Paper withBorder p="md">
            <Title order={3} mb="sm">
              {t('platform.dashboardsFor')}
            </Title>
            <DashboardsForm municipality={municipality} />
          </Paper>
          <Paper withBorder p="md">
            <MembersPanel
              base={`/platform/municipalities/${municipality.id}`}
              scope={['platform', 'municipalities', municipality.id]}
              title={t('platform.users')}
              canSetPassword
            />
          </Paper>
        </>
      )}
    </Stack>
  )
}
