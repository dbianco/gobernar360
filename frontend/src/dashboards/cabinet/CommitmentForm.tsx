import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { errorMessage } from '../../platform/errorMessage'
import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { SubjectPicker } from '../../platform/subjects/SubjectPicker'
import { refOf, type Subject, type SubjectRef } from '../../platform/subjects/types'
import { send, useAction, useMembers } from './api'
import type { AgendaItem, Commitment } from './types'

/** The subject a new commitment starts with: what its item is about. */
function subjectOf(item: AgendaItem): Subject | null {
  return item.subject ?? item.topic?.subject ?? null
}

/**
 * Records a commitment taken on an agenda item, or changes one. What was agreed can be
 * changed only while its meeting is open; who owes it and by when, while it is open itself.
 */
export function CommitmentForm(props: {
  item?: AgendaItem
  commitment?: Commitment
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const members = useMembers()
  const editing = props.commitment
  const initialSubject = editing ? editing.subject : props.item ? subjectOf(props.item) : null
  const [description, setDescription] = useState(editing?.description ?? '')
  const [ownerId, setOwnerId] = useState(editing?.owner.id ?? '')
  const [dueDate, setDueDate] = useState(editing?.due_date ?? '')
  const [subject, setSubject] = useState<SubjectRef | null>(() => refOf(initialSubject))
  // A link this person cannot read is kept as it is unless they choose another.
  const [subjectTouched, setSubjectTouched] = useState(false)
  const textFixed = editing?.meeting.closed ?? false
  const label = (key: string, options = {}) => t(`cabinet.commitment.${key}`, options)
  const hidden = editing?.subject && !refOf(editing.subject) ? editing.subject : null
  const owners = members.data ?? []
  // Someone who left the municipality still owes what they owed.
  const formerOwner =
    editing && !owners.some((member) => member.id === editing.owner.id) ? editing.owner : null

  async function submit(event: FormEvent) {
    event.preventDefault()
    const who = { owner_id: ownerId, due_date: dueDate }
    const saved = await action.run(() => {
      if (!editing) {
        return send('POST', `/items/${props.item?.id}/commitments`, {
          description,
          ...who,
          subject,
        })
      }
      const changes = {
        ...(ownerId !== editing.owner.id && { owner_id: ownerId }),
        ...(dueDate !== editing.due_date && { due_date: dueDate }),
        ...(!textFixed && description !== editing.description && { description }),
        ...(!textFixed && subjectTouched && { subject }),
      }
      return send('PATCH', `/commitments/${editing.id}`, changes)
    })
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {members.isError && <Alert color="red">{errorMessage(members.error)}</Alert>}
        {textFixed && (
          <Text size="sm" c="dimmed">
            {label('textFixed')}
          </Text>
        )}
        <Textarea
          label={label('description')}
          required
          withAsterisk={false}
          rows={2}
          maxLength={500}
          disabled={textFixed}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <Group grow align="flex-start">
          <NativeSelect
            label={label('owner')}
            required
            withAsterisk={false}
            value={ownerId}
            onChange={(event) => setOwnerId(event.currentTarget.value)}
            data={[
              ...(editing ? [] : [{ value: '', label: label('chooseOwner') }]),
              ...(formerOwner ? [{ value: formerOwner.id, label: formerOwner.full_name }] : []),
              ...owners.map((member) => ({
                value: member.id,
                label: member.has_access
                  ? member.full_name
                  : label('noAccess', { name: member.full_name }),
              })),
            ]}
          />
          <DateField label={label('dueDate')} required value={dueDate} onChange={setDueDate} />
        </Group>
        {!textFixed && (
          <>
            {hidden && !subjectTouched && <SubjectLabel subject={hidden} />}
            <SubjectPicker
              initial={initialSubject}
              onChange={(value) => {
                setSubject(value)
                setSubjectTouched(true)
              }}
            />
          </>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
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
