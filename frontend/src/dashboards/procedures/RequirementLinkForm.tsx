import { Alert, Button, Checkbox, Group, NativeSelect, Stack, Text, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { FORMATS, type Requirement, type RequirementLink } from './types'

/**
 * Add a requirement to a procedure, or change how one it already asks for is asked.
 * `available` are the requirements of the list the procedure does not ask for yet.
 */
export function RequirementLinkForm(props: {
  procedureId: string
  available: Requirement[]
  link?: RequirementLink
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.link
  const [requirementId, setRequirementId] = useState(props.available[0]?.id ?? '')
  const [mandatory, setMandatory] = useState(editing?.mandatory ?? true)
  const [format, setFormat] = useState(editing?.format ?? 'paper')
  const [note, setNote] = useState(editing?.note ?? '')
  const label = (key: string) => t(`procedures.detail.${key}`)
  const path = `/procedures/${props.procedureId}/requirements`

  async function submit(event: FormEvent) {
    event.preventDefault()
    const how = { mandatory, format, note }
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `${path}/${editing.id}`, how)
        : send('POST', path, { requirement_id: requirementId, ...how }),
    )
    if (saved) props.onDone()
  }

  if (!editing && props.available.length === 0) {
    return (
      <Stack>
        <Text>{label('allAdded')}</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
        </Group>
      </Stack>
    )
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {!editing && (
          <NativeSelect
            label={label('requirement')}
            value={requirementId}
            onChange={(event) => setRequirementId(event.currentTarget.value)}
            data={props.available.map((item) => ({ value: item.id, label: item.name }))}
          />
        )}
        <Checkbox
          label={label('mandatory')}
          checked={mandatory}
          onChange={(event) => setMandatory(event.currentTarget.checked)}
        />
        <NativeSelect
          label={label('format')}
          value={format}
          onChange={(event) => setFormat(event.currentTarget.value)}
          data={FORMATS.map((value) => ({ value, label: t(`procedures.formats.${value}`) }))}
        />
        <TextInput
          label={label('note')}
          maxLength={500}
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
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
