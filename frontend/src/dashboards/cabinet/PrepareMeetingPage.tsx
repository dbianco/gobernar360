import {
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { errorMessage } from '../../platform/errorMessage'
import { formatDate, todayIso } from '../../platform/format'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { BASE_PATH, send, useAction, useAgendaProposal, useMembers, useOpenMeeting } from './api'
import { CommitmentLine } from './CommitmentLine'
import { MeetingFields } from './MeetingFields'
import { MoveButtons } from './MoveButtons'
import { moved } from './order'
import type { MeetingDetail, Proposal } from './types'

interface Row {
  key: string
  title: string
  /** Null for an item typed here. */
  proposal: Proposal | null
}

/** Prepares the next meeting: its date and people, and the agenda the system proposes. */
export function PrepareMeetingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useAction()
  const members = useMembers()
  const latest = useOpenMeeting()
  const [values, setValues] = useState({ date: todayIso(), attendee_ids: [] as string[], guests: '' })
  const proposal = useAgendaProposal(values.date)
  const [typed, setTyped] = useState<Row[]>([])
  const [newTitle, setNewTitle] = useState('')
  // Decisions are kept by key, so they outlive a change of date that proposes anew.
  const [dropped, setDropped] = useState<string[]>([])
  const [order, setOrder] = useState<string[]>([])
  const label = (key: string, options = {}) => t(`cabinet.prepare.${key}`, options)

  const rows: Row[] = [
    ...(proposal.data?.proposals ?? []).map((p) => ({ key: p.key, title: p.title, proposal: p })),
    ...typed,
  ]
  const place = (row: Row) => (order.includes(row.key) ? order.indexOf(row.key) : Infinity)
  // Stable: rows nobody moved keep the order they were proposed in, after those arranged.
  rows.sort((a, b) => (place(a) === place(b) ? 0 : place(a) - place(b)))
  const accepted = rows.filter((row) => !dropped.includes(row.key))

  function add() {
    const title = newTitle.trim()
    if (!title) return
    setTyped([...typed, { key: `typed:${typed.length}`, title, proposal: null }])
    setNewTitle('')
  }

  function toggle(key: string) {
    setDropped(dropped.includes(key) ? dropped.filter((other) => other !== key) : [...dropped, key])
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const created = await action.run(() =>
      send<MeetingDetail>('POST', '/meetings', {
        ...values,
        agenda: accepted.map((row) =>
          row.proposal ? { key: row.key } : { title: row.title },
        ),
      }),
    )
    if (created) navigate(`${BASE_PATH}/meetings/${created.id}`)
    // It may have failed because what is proposed changed: show it as it is now.
    else void proposal.refetch()
  }

  if (latest.open) {
    return (
      <Alert>
        <Text size="sm">{label('alreadyOpen')}</Text>
        <Anchor component={Link} size="sm" to={`${BASE_PATH}/meetings/${latest.open.id}`}>
          {t('cabinet.meetings.continue', { date: formatDate(latest.open.date) })}
        </Anchor>
      </Alert>
    )
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        <Anchor component={Link} to={`${BASE_PATH}/meetings`} size="sm">
          {t('cabinet.meeting.back')}
        </Anchor>
        <Title order={3}>{label('title')}</Title>
        {members.isError && <Alert color="red">{errorMessage(members.error)}</Alert>}
        <MeetingFields
          values={values}
          onChange={setValues}
          members={members.data ?? []}
          minDate={proposal.data?.previous_meeting_date}
        />
        <Stack gap="xs" component="section" aria-label={label('agenda')}>
          <Title order={4}>{label('agenda')}</Title>
          <Text size="sm" c="dimmed">
            {label('agendaHint')}
          </Text>
          {proposal.isLoading && <Loader aria-label={t('app.loading')} />}
          {proposal.isError && <Alert color="red">{errorMessage(proposal.error)}</Alert>}
          {proposal.data && rows.length === 0 && <Text c="dimmed">{label('nothing')}</Text>}
          <Stack gap="xs" role="list">
            {rows.map((row, index) => (
              <Paper key={row.key} withBorder p="sm" role="listitem">
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Checkbox
                    checked={!dropped.includes(row.key)}
                    onChange={() => toggle(row.key)}
                    label={row.title}
                    miw={0}
                  />
                  <Group gap="xs" wrap="nowrap">
                    <Badge variant="outline" color="gray" tt="none">
                      {t(`cabinet.agenda.sources.${row.proposal?.source ?? 'manual'}`)}
                    </Badge>
                    {row.proposal?.carried && (
                      <Badge variant="light" color="orange" tt="none">
                        {t('cabinet.agenda.carried')}
                      </Badge>
                    )}
                    <MoveButtons
                      name={row.title}
                      first={index === 0}
                      last={index === rows.length - 1}
                      onMove={(by) =>
                        setOrder(moved(rows.map((other) => other.key), index, by))
                      }
                    />
                  </Group>
                </Group>
                {row.proposal?.commitment && (
                  <Stack pl={32} mt={4}>
                    <CommitmentLine commitment={row.proposal.commitment} hideName />
                  </Stack>
                )}
                {row.proposal?.subject && (
                  <Stack pl={32} mt={4}>
                    <SubjectLabel
                      subject={row.proposal.subject}
                      stateOnly={row.proposal.source === 'light'}
                    />
                  </Stack>
                )}
              </Paper>
            ))}
          </Stack>
          {proposal.data && proposal.data.dashboards_not_considered > 0 && (
            <Text size="sm" c="dimmed">
              {label('notConsidered', { count: proposal.data.dashboards_not_considered })}
            </Text>
          )}
          <Group align="flex-end">
            <TextInput
              label={label('newItem')}
              maxLength={200}
              miw={280}
              value={newTitle}
              onChange={(event) => setNewTitle(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter') return
                // Enter adds the item instead of preparing the meeting.
                event.preventDefault()
                add()
              }}
            />
            <Button variant="default" onClick={add} disabled={!newTitle.trim()}>
              {t('app.add')}
            </Button>
          </Group>
        </Stack>
        {proposal.data && proposal.data.to_carry_over > 0 && (
          <Text size="sm">{label('carryOver', { count: proposal.data.to_carry_over })}</Text>
        )}
        {action.error && <Alert color="red">{action.error}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" component={Link} to={`${BASE_PATH}/meetings`}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending} disabled={!proposal.data || proposal.isPlaceholderData}>
            {label('submit')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
