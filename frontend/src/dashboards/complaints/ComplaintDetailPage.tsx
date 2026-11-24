import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  Paper,
  SimpleGrid,
  Stack,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatDate, formatDni } from '../../platform/format'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, KEY, useAreas, useComplaint, useTypes, useZones } from './api'
import { ClockBadge, StateBadge } from './Badges'
import { CommentForm, EditForm, MoveForm, ReassignForm } from './ComplaintActions'
import { clockText, formatDateTime } from './format'
import { moveLabelKey } from './moves'
import { Timeline } from './Timeline'
import { type ComplaintDetail, OPEN_STATES, type State } from './types'

type Dialog = { move: State } | 'reassign' | 'comment' | 'edit' | null

const MOVE_STYLES: Partial<Record<State, { variant: string; color?: string }>> = {
  resolved: { variant: 'filled', color: 'teal' },
  rejected: { variant: 'subtle', color: 'red' },
  reopened: { variant: 'light', color: 'orange' },
}

function ClockPanel({ complaint }: { complaint: ComplaintDetail }) {
  const { t } = useTranslation()
  const { clock, state } = complaint
  const label = (key: string, options = {}) => t(`complaints.detail.${key}`, options)
  const days = (count: number) => label('days', { count })
  const open = OPEN_STATES.includes(state)

  return (
    <Paper withBorder p="md" component="section" aria-label={label('clock')}>
      <Group justify="space-between" mb="sm">
        <Title order={4}>{label('clock')}</Title>
        <ClockBadge clock={clock} state={state} />
      </Group>
      {clock.paused && (
        <Alert color="grape" mb="sm">
          {label('pausedHint')}
        </Alert>
      )}
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <Field label={label('target')}>{days(clock.target_days)}</Field>
        <Field label={label('used')}>{days(clock.used_days)}</Field>
        {open ? (
          <>
            <Field label={label('left')}>{clockText(clock, state, t)}</Field>
            <Field label={label('deadline')}>{formatDate(clock.deadline)}</Field>
          </>
        ) : (
          <>
            <Field label={label('outcome')}>{clockText(clock, state, t)}</Field>
            <Field label={label('resolvedOn')}>{formatDate(clock.resolved_on)}</Field>
          </>
        )}
      </SimpleGrid>
    </Paper>
  )
}

/** One complaint: what and where, who complained, its clock, what can be done next and its history. */
export function ComplaintDetailPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { id = '' } = useParams()
  const complaint = useComplaint(id)
  const areas = useAreas()
  const types = useTypes()
  const zones = useZones()
  const [dialog, setDialog] = useState<Dialog>(null)
  const canAct = hasLevel(me, KEY, 'editor')
  const label = (key: string, options = {}) => t(`complaints.detail.${key}`, options)
  const close = () => setDialog(null)

  if (complaint.isError) return <Alert color="red">{errorMessage(complaint.error)}</Alert>
  const data = complaint.data
  if (!data) return <Loader aria-label={t('app.loading')} />
  const open = OPEN_STATES.includes(data.state)
  const move = typeof dialog === 'object' && dialog !== null ? dialog.move : null

  return (
    <Stack>
      <Anchor component={Link} to={`${BASE_PATH}/complaints`} size="sm">
        {label('back')}
      </Anchor>
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <Title order={3}>{label('title', { number: data.number })}</Title>
          <StateBadge state={data.state} />
        </Group>
      </Group>
      {canAct && (
        <Group gap="xs" component="section" aria-label={label('actions')}>
          {data.moves.map((to) => (
            <Button
              key={to}
              variant={MOVE_STYLES[to]?.variant ?? 'default'}
              color={MOVE_STYLES[to]?.color}
              onClick={() => setDialog({ move: to })}
            >
              {t(`complaints.moves.${moveLabelKey(data.state, to)}`)}
            </Button>
          ))}
          {open && (
            <Button variant="default" onClick={() => setDialog('reassign')}>
              {t('complaints.actions.reassign')}
            </Button>
          )}
          {open && (
            <Button variant="default" onClick={() => setDialog('edit')}>
              {t('complaints.actions.edit')}
            </Button>
          )}
          <Button variant="subtle" onClick={() => setDialog('comment')}>
            {t('complaints.actions.comment')}
          </Button>
        </Group>
      )}
      <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
        <Field label={label('type')}>{data.type.name}</Field>
        <Field label={label('area')}>{data.area.name}</Field>
        <Field label={label('received')}>{formatDateTime(data.received_at)}</Field>
        <Field label={label('address')}>{data.address}</Field>
        <Field label={label('zone')}>{data.zone.name}</Field>
        <Field label={label('complainant')}>
          {data.person
            ? [
                data.person.full_name,
                data.person.dni && `DNI ${formatDni(data.person.dni)}`,
                data.person.phone,
              ]
                .filter(Boolean)
                .join(' · ')
            : label('anonymous')}
        </Field>
      </SimpleGrid>
      {data.description && <Field label={label('description')}>{data.description}</Field>}
      <ClockPanel complaint={data} />
      <Stack gap="xs" component="section" aria-label={label('timeline')}>
        <Title order={4}>{label('timeline')}</Title>
        <Timeline events={data.timeline} />
      </Stack>

      <Modal
        opened={move !== null}
        onClose={close}
        title={move ? t(`complaints.moves.${moveLabelKey(data.state, move)}`) : ''}
      >
        {move && <MoveForm complaint={data} to={move} onDone={close} />}
      </Modal>
      <Modal
        opened={dialog === 'reassign'}
        onClose={close}
        title={t('complaints.actions.reassignTitle')}
      >
        {dialog === 'reassign' && (
          <ReassignForm complaint={data} areas={areas.data ?? []} onDone={close} />
        )}
      </Modal>
      <Modal opened={dialog === 'comment'} onClose={close} title={t('complaints.actions.comment')}>
        {dialog === 'comment' && <CommentForm complaint={data} onDone={close} />}
      </Modal>
      <Modal
        opened={dialog === 'edit'}
        onClose={close}
        title={t('complaints.actions.editTitle')}
        size="lg"
      >
        {dialog === 'edit' && (
          <EditForm
            complaint={data}
            types={types.data ?? []}
            zones={zones.data ?? []}
            onDone={close}
          />
        )}
      </Modal>
    </Stack>
  )
}
