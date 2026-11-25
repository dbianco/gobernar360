import { Alert, Button, Group, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SubjectLabel } from '../../platform/subjects/SubjectLabel'
import { SubjectPicker } from '../../platform/subjects/SubjectPicker'
import { refOf, type SubjectRef } from '../../platform/subjects/types'
import { send, useAction } from './api'
import type { AgendaItem } from './types'

/** Adds an item to the agenda of an open meeting, or renames one a person typed. */
export function ItemForm(props: { meetingId: string; item?: AgendaItem; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.item
  const [title, setTitle] = useState(editing?.title ?? '')
  const [subject, setSubject] = useState<SubjectRef | null>(() => refOf(editing?.subject))
  const [subjectTouched, setSubjectTouched] = useState(false)
  const hidden = editing?.subject && !refOf(editing.subject) ? editing.subject : null

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/items/${editing.id}`, { title, ...(subjectTouched && { subject }) })
        : send('POST', `/meetings/${props.meetingId}/items`, { title, subject }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={t('cabinet.agenda.itemTitle')}
          required
          withAsterisk={false}
          maxLength={200}
          value={title}
          onChange={(event) => setTitle(event.currentTarget.value)}
        />
        {hidden && !subjectTouched && <SubjectLabel subject={hidden} />}
        <SubjectPicker
          initial={editing?.subject}
          onChange={(value) => {
            setSubject(value)
            setSubjectTouched(true)
          }}
        />
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
