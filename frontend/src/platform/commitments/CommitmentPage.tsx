import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Textarea,
  Title,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { errorMessage } from '../errorMessage'
import { Field } from '../Field'
import { formatDate } from '../format'
import { SubjectLabel } from '../subjects/SubjectLabel'
import {
  PATH,
  send,
  useCommitment,
  useCommitmentAction,
  useNotifications,
  useReadOnOpen,
} from './api'
import { CommitmentForm } from './CommitmentForm'
import { CommitmentHistory } from './CommitmentHistory'
import { Origin } from './Origin'
import { PostponedBadge } from './PostponedBadge'
import { StateBadge } from './StateBadge'
import { StateForm } from './StateForm'
import type { CommitmentDetail } from './types'

/** Adds a progress note to a commitment. */
function NoteForm({ commitmentId }: { commitmentId: string }) {
  const { t } = useTranslation()
  const action = useCommitmentAction()
  const [note, setNote] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() => send('POST', `${PATH}/${commitmentId}/notes`, { note }))
    if (saved) setNote('')
  }

  return (
    <form onSubmit={submit}>
      <Stack gap="xs">
        {action.error && <Alert color="red">{action.error}</Alert>}
        <Textarea
          label={t('commitments.detail.newNote')}
          rows={2}
          maxLength={5000}
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={action.pending} disabled={!note.trim()}>
            {t('commitments.detail.addNote')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

/** One commitment: what was agreed, how it is going and everything that happened to it. */
export function CommitmentPage() {
  const { t } = useTranslation()
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const commitment = useCommitment(id)
  const notifications = useNotifications()
  const action = useCommitmentAction()
  const [dialog, setDialog] = useState<'edit' | 'done' | 'dropped' | null>(null)
  const label = (key: string, options = {}) => t(`commitments.detail.${key}`, options)
  const data = commitment.data
  const rows = [...(notifications.data?.mine ?? []), ...(notifications.data?.others ?? [])]
  const hasNews = rows.some((row) => row.id === id && row.news.length > 0)
  useReadOnOpen(id, hasNews && data !== undefined)
  const close = () => setDialog(null)
  const back = (
    <Anchor component={Link} to={PATH} size="sm">
      {label('back')}
    </Anchor>
  )

  if (!data) {
    return (
      <Stack>
        {back}
        {commitment.isError ? (
          <Alert color="red">{errorMessage(commitment.error)}</Alert>
        ) : (
          <Loader aria-label={t('app.loading')} />
        )}
      </Stack>
    )
  }

  const { rights } = data
  const isPending = data.state === 'open' || data.state === 'overdue'
  const titles = { edit: 'editTitle', done: 'markDone', dropped: 'drop' }

  async function save(body: Record<string, unknown>) {
    const saved = await send<CommitmentDetail>('PATCH', `${PATH}/${id}`, body)
    // Given to somebody else: it is no longer theirs to look at.
    if (!saved.rights.see) navigate(PATH)
  }

  return (
    <Stack>
      {back}
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Title order={3}>{data.description}</Title>
          <Group gap="xs">
            <StateBadge state={data.state} />
            <PostponedBadge times={data.times_postponed} />
          </Group>
        </Stack>
        <Group gap="xs">
          {isPending && rights.finish && (
            <Button onClick={() => setDialog('done')}>{label('markDone')}</Button>
          )}
          {isPending && rights.reschedule && (
            <Button variant="default" onClick={() => setDialog('edit')}>
              {t('app.edit')}
            </Button>
          )}
          {isPending && rights.manage && (
            <Button variant="subtle" color="red" onClick={() => setDialog('dropped')}>
              {label('drop')}
            </Button>
          )}
          {!isPending && rights.manage && (
            <Button
              variant="default"
              loading={action.pending}
              onClick={() =>
                void action.run(() => send('POST', `${PATH}/${id}/state`, { state: 'open' }))
              }
            >
              {label('reopen')}
            </Button>
          )}
        </Group>
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
        <Field label={label('owner')}>{data.owner.full_name}</Field>
        <Field label={label('dueDate')}>{formatDate(data.due_date)}</Field>
        {data.completed_on && (
          <Field label={label('completedOn')}>{formatDate(data.completed_on)}</Field>
        )}
        {data.creator && <Field label={label('creator')}>{data.creator.full_name}</Field>}
        <Field label={label('followers')}>
          {data.followers.map((person) => person.full_name).join(', ')}
        </Field>
      </SimpleGrid>
      <Group gap="xs">
        <span>{label('origin')}:</span>
        <Origin commitment={data} />
      </Group>
      {data.subject && (
        <Group gap="xs">
          <span>{t('subjects.about')}:</span>
          <SubjectLabel subject={data.subject} />
        </Group>
      )}
      <Stack gap="sm" component="section" aria-label={label('history')}>
        <Title order={4}>{label('history')}</Title>
        {rights.note && <NoteForm commitmentId={id} />}
        <CommitmentHistory history={data.history} />
      </Stack>
      <Modal opened={dialog !== null} onClose={close} title={dialog && label(titles[dialog])} size="lg">
        {dialog === 'edit' && (
          <CommitmentForm
            editing={data}
            textFixed={rights.edit ? undefined : label(data.source ? 'textOfMeeting' : 'textOfCreator')}
            save={save}
            onDone={close}
          />
        )}
        {(dialog === 'done' || dialog === 'dropped') && (
          <StateForm commitmentId={id} state={dialog} onDone={close} />
        )}
      </Modal>
    </Stack>
  )
}
