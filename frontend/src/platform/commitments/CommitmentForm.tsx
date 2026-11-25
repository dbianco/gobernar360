import { Alert, Button, Group, Stack, Text, Textarea } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../DateField'
import { type UserRef, useMembers, withFormer } from '../directory'
import { errorMessage } from '../errorMessage'
import { PeopleSelect, PersonSelect } from '../PersonSelect'
import { SubjectLabel } from '../subjects/SubjectLabel'
import { SubjectPicker } from '../subjects/SubjectPicker'
import { refOf, type Subject, type SubjectRef } from '../subjects/types'
import { useCommitmentAction } from './api'

/** What the form can change of a commitment that exists. */
export interface EditedCommitment {
  description: string
  owner: UserRef
  due_date: string
  subject: Subject | null
  followers: UserRef[]
}

const sameIds = (a: string[], b: string[]) =>
  a.length === b.length && a.every((id) => b.includes(id))

/**
 * Gives a commitment or changes one. `save` gets all of a new one; of one that exists, only
 * what changed.
 */
export function CommitmentForm(props: {
  editing?: EditedCommitment
  /** What was agreed can no longer be changed, and why. */
  textFixed?: string
  /** What a new one starts being about. */
  subject?: Subject | null
  save: (body: Record<string, unknown>) => Promise<unknown>
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useCommitmentAction()
  const members = useMembers()
  const { editing } = props
  const initialSubject = editing ? editing.subject : (props.subject ?? null)
  const initialFollowers = editing?.followers.map((person) => person.id) ?? []
  const [description, setDescription] = useState(editing?.description ?? '')
  const [ownerId, setOwnerId] = useState(editing?.owner.id ?? '')
  const [dueDate, setDueDate] = useState(editing?.due_date ?? '')
  const [followerIds, setFollowerIds] = useState(initialFollowers)
  const [subject, setSubject] = useState<SubjectRef | null>(() => refOf(initialSubject))
  // A link this person cannot read is kept as it is unless they choose another.
  const [subjectTouched, setSubjectTouched] = useState(false)
  const label = (key: string, options = {}) => t(`commitments.form.${key}`, options)
  const hidden = editing?.subject && !refOf(editing.subject) ? editing.subject : null

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = editing
      ? {
          ...(ownerId !== editing.owner.id && { owner_id: ownerId }),
          ...(dueDate !== editing.due_date && { due_date: dueDate }),
          ...(!sameIds(followerIds, initialFollowers) && { follower_ids: followerIds }),
          ...(!props.textFixed && description !== editing.description && { description }),
          ...(!props.textFixed && subjectTouched && { subject }),
        }
      : {
          description,
          owner_id: ownerId,
          due_date: dueDate,
          follower_ids: followerIds,
          subject,
        }
    const saved = await action.run(async () => {
      await props.save(body)
      return true
    })
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {members.isError && <Alert color="red">{errorMessage(members.error)}</Alert>}
        {props.textFixed && (
          <Text size="sm" c="dimmed">
            {props.textFixed}
          </Text>
        )}
        <Textarea
          label={label('description')}
          required
          withAsterisk={false}
          rows={2}
          maxLength={500}
          disabled={Boolean(props.textFixed)}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <Group grow align="flex-start">
          <PersonSelect
            label={label('owner')}
            required
            value={ownerId}
            onChange={setOwnerId}
            people={withFormer(members.data, editing ? [editing.owner] : [])}
          />
          <DateField label={label('dueDate')} required value={dueDate} onChange={setDueDate} />
        </Group>
        <PeopleSelect
          label={label('followers')}
          description={label('followersHint')}
          value={followerIds}
          onChange={setFollowerIds}
          people={withFormer(members.data, editing?.followers ?? [])}
        />
        {!props.textFixed && (
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
