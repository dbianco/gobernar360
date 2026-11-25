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
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { PostponedBadge } from '../../platform/commitments/PostponedBadge'
import { errorMessage } from '../../platform/errorMessage'
import { Field } from '../../platform/Field'
import { formatDate } from '../../platform/format'
import { hasLevel } from '../../platform/access'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { BASE_PATH, KEY, send, useAction, useCommitment } from './api'
import { CommitmentForm } from './CommitmentForm'
import { CommitmentHistory } from './CommitmentHistory'
import { StateBadge } from './StateBadge'
import { StateForm } from './StateForm'

/** Adds a progress note to a commitment. */
function NoteForm({ commitmentId }: { commitmentId: string }) {
  const { t } = useTranslation()
  const action = useAction()
  const [note, setNote] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() =>
      send('POST', `/commitments/${commitmentId}/notes`, { note }),
    )
    if (saved) setNote('')
  }

  return (
    <form onSubmit={submit}>
      <Stack gap="xs">
        {action.error && <Alert color="red">{action.error}</Alert>}
        <Textarea
          label={t('cabinet.commitment.newNote')}
          rows={2}
          maxLength={5000}
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button type="submit" loading={action.pending} disabled={!note.trim()}>
            {t('cabinet.commitment.addNote')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

/** One commitment: what was agreed, how it is going and everything that happened to it. */
export function CommitmentPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const { id = '' } = useParams()
  const commitment = useCommitment(id)
  const action = useAction()
  const [dialog, setDialog] = useState<'edit' | 'done' | 'dropped' | null>(null)
  const label = (key: string, options = {}) => t(`cabinet.commitment.${key}`, options)
  const data = commitment.data?.id === id ? commitment.data : undefined
  const close = () => setDialog(null)
  const back = (
    <Anchor component={Link} to={`${BASE_PATH}/commitments`} size="sm">
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

  const canEdit = hasLevel(me, KEY, 'editor')
  const isPending = data.state === 'open' || data.state === 'overdue'
  const titles = { edit: 'editTitle', done: 'markDone', dropped: 'drop' }

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
        {canEdit && (
          <Group gap="xs">
            {isPending ? (
              <>
                <Button onClick={() => setDialog('done')}>{label('markDone')}</Button>
                <Button variant="default" onClick={() => setDialog('edit')}>
                  {t('app.edit')}
                </Button>
                <Button variant="subtle" color="red" onClick={() => setDialog('dropped')}>
                  {label('drop')}
                </Button>
              </>
            ) : (
              <Button
                variant="default"
                loading={action.pending}
                onClick={() =>
                  void action.run(() =>
                    send('POST', `/commitments/${id}/state`, { state: 'open' }),
                  )
                }
              >
                {label('reopen')}
              </Button>
            )}
          </Group>
        )}
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
        <Field label={label('owner')}>{data.owner.full_name}</Field>
        <Field label={label('dueDate')}>{formatDate(data.due_date)}</Field>
        <Field label={label('completedOn')}>{formatDate(data.completed_on)}</Field>
        <Field label={label('meeting')}>
          <Anchor component={Link} to={`${BASE_PATH}/meetings/${data.meeting.id}`}>
            {formatDate(data.meeting.date)}
          </Anchor>
        </Field>
      </SimpleGrid>
      {data.subject && (
        <Group gap="xs">
          <span>{t('subjects.about')}:</span>
          <SubjectLabel subject={data.subject} />
        </Group>
      )}
      <Stack gap="sm" component="section" aria-label={label('history')}>
        <Title order={4}>{label('history')}</Title>
        {(canEdit || me?.user.id === data.owner.id) && <NoteForm commitmentId={id} />}
        <CommitmentHistory history={data.history} />
      </Stack>
      <Modal opened={dialog !== null} onClose={close} title={dialog && label(titles[dialog])} size="lg">
        {dialog === 'edit' && <CommitmentForm commitment={data} onDone={close} />}
        {(dialog === 'done' || dialog === 'dropped') && (
          <StateForm commitment={data} state={dialog} onDone={close} />
        )}
      </Modal>
    </Stack>
  )
}
