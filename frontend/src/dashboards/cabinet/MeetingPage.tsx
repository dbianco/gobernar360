import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { type FormEvent, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { useConfirm } from '../../platform/confirmContext'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatDate } from '../../platform/format'
import { hasLevel } from '../../platform/access'
import { AgendaItemCard, type ItemActions } from './AgendaItemCard'
import { BASE, BASE_PATH, done, KEY, send, useAction, useMeeting, useMembers } from './api'
import { CommitmentForm } from './CommitmentForm'
import { CommitmentLine } from './CommitmentLine'
import { ItemForm } from './ItemForm'
import { MeetingFields } from './MeetingFields'
import { moved } from './order'
import { SavedTextarea } from './SavedTextarea'
import type { AgendaItem, Commitment, MeetingDetail } from './types'

type Dialog =
  | { kind: 'data' }
  | { kind: 'item'; item?: AgendaItem }
  | { kind: 'commitment'; item: AgendaItem; commitment?: Commitment }

function MeetingDataForm({ meeting, onDone }: { meeting: MeetingDetail; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const members = useMembers()
  const [values, setValues] = useState({
    date: meeting.date,
    attendee_ids: meeting.attendees.map((attendee) => attendee.id),
    guests: meeting.guests,
  })

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() => send('PATCH', `/meetings/${meeting.id}`, values))
    if (saved) onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {members.isError && <Alert color="red">{errorMessage(members.error)}</Alert>}
        <MeetingFields
          values={values}
          onChange={setValues}
          members={members.data ?? []}
          attendees={meeting.attendees}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

/** A meeting: worked on while it is open, only read once it is closed. */
export function MeetingPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const confirm = useConfirm()
  const meeting = useMeeting(id)
  const action = useAction()
  const [dialog, setDialog] = useState<Dialog | null>(null)
  // The last text being saved: closing waits for it, since a closed meeting takes no more.
  const saving = useRef<Promise<unknown>>(Promise.resolve(true))
  const label = (key: string, options = {}) => t(`cabinet.meeting.${key}`, options)
  const list = `${BASE_PATH}/meetings`
  const data = meeting.data?.id === id ? meeting.data : undefined
  const close = () => setDialog(null)

  if (!data) {
    return (
      <Stack>
        <Anchor component={Link} to={list} size="sm">
          {label('back')}
        </Anchor>
        {meeting.isError ? (
          <Alert color="red">{errorMessage(meeting.error)}</Alert>
        ) : (
          <Loader aria-label={t('app.loading')} />
        )}
      </Stack>
    )
  }

  const canWrite = !data.closed && hasLevel(me, KEY, 'editor')
  const taken = data.items.flatMap((item) => item.commitments)
  const save = (path: string, changes: object) => {
    saving.current = action.run(() => send('PATCH', path, changes))
  }

  async function closeMeeting() {
    const sure = await confirm({
      title: label('closeTitle'),
      message: label('closeMessage'),
      confirmLabel: label('close'),
      danger: true,
    })
    // If what was typed could not be saved the error is on screen, and nothing is closed.
    if (!sure || !(await saving.current)) return
    await action.run(() => send('POST', `/meetings/${id}/close`))
  }

  async function discard() {
    const sure = await confirm({
      message: label('discardMessage'),
      confirmLabel: label('discard'),
      danger: true,
    })
    if (!sure) return
    if (await action.run(() => done(send('DELETE', `/meetings/${id}`)))) navigate(list)
  }

  async function remove(path: string, name: string) {
    const sure = await confirm({
      message: label('removeMessage', { name }),
      confirmLabel: t('app.delete'),
      danger: true,
    })
    if (sure) await action.run(() => done(send('DELETE', path)))
  }

  const actionsFor = (item: AgendaItem, index: number): ItemActions => ({
    move: (by) =>
      void action.run(() =>
        send('PUT', `/meetings/${id}/items/order`, {
          item_ids: moved(
            data.items.map((other) => other.id),
            index,
            by,
          ),
        }),
      ),
    saveNotes: (notes) => save(`/items/${item.id}`, { notes }),
    setDiscussed: (discussed) => save(`/items/${item.id}`, { discussed }),
    edit: () => setDialog({ kind: 'item', item }),
    remove: () => void remove(`/items/${item.id}`, item.title),
    addCommitment: () => setDialog({ kind: 'commitment', item }),
    editCommitment: (commitment) => setDialog({ kind: 'commitment', item, commitment }),
    removeCommitment: (commitment) =>
      void remove(`/commitments/${commitment.id}`, commitment.description),
  })

  const dialogTitle = (open: Dialog) => {
    if (open.kind === 'data') return label('editTitle')
    if (open.kind === 'item') return t(`cabinet.agenda.${open.item ? 'editTitle' : 'addTitle'}`)
    return t(`cabinet.commitment.${open.commitment ? 'editTitle' : 'addTitle'}`)
  }

  return (
    <Stack>
      <Anchor component={Link} to={list} size="sm">
        {label('back')}
      </Anchor>
      <Group justify="space-between" align="flex-start">
        <Group gap="sm">
          <Title order={3}>{label('title', { date: formatDate(data.date) })}</Title>
          <Badge variant="light" tt="none" color={data.closed ? 'gray' : 'blue'}>
            {label(data.closed ? 'closed' : 'open')}
          </Badge>
        </Group>
        <Group gap="xs">
          {data.closed && (
            <Button
              component="a"
              variant="default"
              href={downloadUrl(`${BASE}/meetings/${id}/minutes.html`)}
            >
              {label('download')}
            </Button>
          )}
          {canWrite && (
            <>
              <Button variant="default" onClick={() => setDialog({ kind: 'data' })}>
                {label('edit')}
              </Button>
              {taken.length === 0 && (
                <Button variant="subtle" color="red" onClick={() => void discard()}>
                  {label('discard')}
                </Button>
              )}
              <Button onClick={() => void closeMeeting()}>
                {label('close')}
              </Button>
            </>
          )}
        </Group>
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Field label={label('attendees')}>
          {data.attendees.map((attendee) => attendee.full_name).join(', ')}
        </Field>
        <Field label={label('guests')}>{data.guests}</Field>
      </SimpleGrid>

      {data.carried_over.length > 0 && (
        <Stack gap="xs" component="section" aria-label={label('carriedOver')}>
          <Title order={4}>{label('carriedOver')}</Title>
          <Text size="sm" c="dimmed">
            {label('carriedOverHint')}
          </Text>
          {data.carried_over.map((commitment) => (
            <CommitmentLine key={commitment.id} commitment={commitment} />
          ))}
        </Stack>
      )}

      <Stack gap="sm" component="section" aria-label={label('agenda')}>
        <Group justify="space-between">
          <Title order={4}>{label('agenda')}</Title>
          {canWrite && (
            <Button variant="default" onClick={() => setDialog({ kind: 'item' })}>
              {t('cabinet.agenda.add')}
            </Button>
          )}
        </Group>
        {data.items.length === 0 && <Text c="dimmed">{label('emptyAgenda')}</Text>}
        {data.items.map((item, index) => (
          <AgendaItemCard
            key={item.id}
            item={item}
            number={index + 1}
            last={index === data.items.length - 1}
            actions={canWrite ? actionsFor(item, index) : null}
          />
        ))}
      </Stack>

      {canWrite ? (
        <SavedTextarea
          label={label('notes')}
          autosize
          minRows={3}
          maxLength={10000}
          saved={data.notes}
          onSave={(notes) => save(`/meetings/${id}`, { notes })}
        />
      ) : (
        data.notes && <Field label={label('notes')}>{data.notes}</Field>
      )}

      <Modal opened={dialog !== null} onClose={close} title={dialog && dialogTitle(dialog)} size="lg">
        {dialog?.kind === 'data' && <MeetingDataForm meeting={data} onDone={close} />}
        {dialog?.kind === 'item' && (
          <ItemForm meetingId={id} item={dialog.item} onDone={close} />
        )}
        {dialog?.kind === 'commitment' && (
          <CommitmentForm item={dialog.item} commitment={dialog.commitment} onDone={close} />
        )}
      </Modal>
    </Stack>
  )
}
