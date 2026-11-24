import {
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Paper,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { dashboardLabelKey } from '../dashboards/registry'
import { errorMessage } from './errorMessage'
import { formatDateTime } from './format'
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

/** Whether people can work in the municipality; suspending it keeps its data. */
function SuspensionPanel({ municipality }: { municipality: MunicipalityDetail }) {
  const { t } = useTranslation()
  const action = useAction(['platform', 'me'])
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState('')
  const label = (key: string, options = {}) => t(`platform.suspension.${key}`, options)
  const path = `/platform/municipalities/${municipality.id}/suspension`
  const { suspension } = municipality

  async function suspend(event: FormEvent) {
    event.preventDefault()
    if (!reason.trim()) return
    const done = await action.run(() =>
      api(path, { method: 'POST', body: { reason: reason.trim() } }),
    )
    if (done) {
      setAsking(false)
      setReason('')
    }
  }

  return (
    <Stack gap="sm">
      {action.error && !asking && <Alert color="red">{action.error}</Alert>}
      {suspension ? (
        <>
          <Alert color="red" title={label('suspendedTitle')}>
            <Text size="sm">
              {label(suspension.by ? 'since' : 'sinceUnknown', {
                at: formatDateTime(suspension.at),
                by: suspension.by,
              })}
            </Text>
            <Text size="sm">{label('reasonShown', { reason: suspension.reason })}</Text>
          </Alert>
          <Group>
            <Button
              loading={action.pending}
              onClick={() => void action.run(() => api(path, { method: 'DELETE' }))}
            >
              {label('resume')}
            </Button>
          </Group>
        </>
      ) : (
        <>
          <Text size="sm">{label('active')}</Text>
          <Group>
            <Button color="red" variant="light" onClick={() => setAsking(true)}>
              {label('suspend')}
            </Button>
          </Group>
        </>
      )}
      <Modal
        opened={asking}
        onClose={() => setAsking(false)}
        title={label('confirmTitle', { name: municipality.name })}
      >
        <form onSubmit={(event) => void suspend(event)}>
          <Stack>
            {action.error && <Alert color="red">{action.error}</Alert>}
            <Text size="sm">{label('confirmBody', { name: municipality.name })}</Text>
            <Textarea
              label={label('reason')}
              description={label('reasonHint')}
              required
              withAsterisk={false}
              maxLength={500}
              rows={3}
              value={reason}
              onChange={(event) => setReason(event.currentTarget.value)}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setAsking(false)}>
                {t('app.cancel')}
              </Button>
              <Button type="submit" color="red" loading={action.pending}>
                {label('suspend')}
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
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
          <Group gap="sm">
            <Title order={2}>{municipality.name}</Title>
            {municipality.suspension && (
              <Badge color="red" variant="light" style={{ textTransform: 'none' }}>
                {t('platform.suspension.badge')}
              </Badge>
            )}
          </Group>
          <Paper withBorder p="md">
            <Title order={3} mb="sm">
              {t('platform.suspension.title')}
            </Title>
            <SuspensionPanel municipality={municipality} />
          </Paper>
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
