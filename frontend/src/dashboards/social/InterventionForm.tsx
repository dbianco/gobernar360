import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { todayIso } from '../../platform/format'
import { send, useAction, useInterventionTypes } from './api'
import { PersonPicker } from './PersonSearch'
import type { Intervention, PersonRef } from './types'

/**
 * Record what the team did with a person, or correct an existing record.
 * Without `personId` the form asks who it was with. Only members who may read
 * the reserved description reach this form.
 */
export function InterventionForm(props: {
  personId?: string
  intervention?: Intervention
  onDone: () => void
}) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const action = useAction()
  const types = useInterventionTypes()
  const editing = props.intervention
  const [person, setPerson] = useState<PersonRef | null>(null)
  const [typeId, setTypeId] = useState('')
  const [date, setDate] = useState(() => editing?.date ?? todayIso())
  const [description, setDescription] = useState(editing?.description ?? '')
  // Most interventions are loaded by whoever did them.
  const [performedBy, setPerformedBy] = useState(
    editing ? editing.performed_by : (me?.user.full_name ?? ''),
  )
  const label = (key: string) => t(`social.interventions.${key}`)
  const personId = props.personId ?? person?.id
  const offered = [...(types.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'es'))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const changes = { date, description, performed_by: performedBy }
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/interventions/${editing.id}`, changes)
        : send('POST', '/interventions', {
            intervention_type_id: typeId,
            person_id: personId,
            ...changes,
          }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {types.isError && <Alert color="red">{errorMessage(types.error)}</Alert>}
        {!editing && !props.personId && <PersonPicker value={person} onChange={setPerson} />}
        {!editing && types.data && offered.length === 0 && (
          <Text c="dimmed">{label('noTypes')}</Text>
        )}
        {editing ? (
          <TextInput
            label={label('type')}
            description={label('fixed')}
            disabled
            value={editing.intervention_type.name}
            readOnly
          />
        ) : (
          <NativeSelect
            label={label('type')}
            required
            withAsterisk={false}
            value={typeId}
            onChange={(event) => setTypeId(event.currentTarget.value)}
            data={[
              { value: '', label: label('chooseType') },
              ...offered.map((type) => ({ value: type.id, label: type.name })),
            ]}
          />
        )}
        <Group grow align="flex-start">
          <TextInput
            label={label('date')}
            type="date"
            required
            withAsterisk={false}
            value={date}
            onChange={(event) => setDate(event.currentTarget.value)}
          />
          <TextInput
            label={label('performedBy')}
            maxLength={200}
            value={performedBy}
            onChange={(event) => setPerformedBy(event.currentTarget.value)}
          />
        </Group>
        <Textarea
          label={label('description')}
          description={label('descriptionHint')}
          rows={4}
          maxLength={5000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button
            type="submit"
            loading={action.pending}
            disabled={!editing && (offered.length === 0 || !personId)}
          >
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
