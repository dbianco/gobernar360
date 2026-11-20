import { Alert, Button, Group, NativeSelect, Stack, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import type { Requirement, Source } from './types'

/** Add a requirement to the municipality's list, or edit one. */
export function RequirementForm(props: {
  sources: Source[]
  requirement?: Requirement
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.requirement
  const [name, setName] = useState(editing?.name ?? '')
  const [description, setDescription] = useState(editing?.description ?? '')
  const [sourceId, setSourceId] = useState(editing?.source?.id ?? '')
  const label = (key: string) => t(`procedures.requirements.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { name, description, source_id: sourceId || null }
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/requirements/${editing.id}`, body)
        : send('POST', '/requirements', body),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={label('name')}
          required
          withAsterisk={false}
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={2}
          maxLength={5000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <NativeSelect
          label={label('sourceField')}
          description={label('sourceHint')}
          value={sourceId}
          onChange={(event) => setSourceId(event.currentTarget.value)}
          data={[
            { value: '', label: label('noSource') },
            ...props.sources.map((source) => ({
              value: source.id,
              label: `${source.name} (${t(`procedures.levels.${source.level}`)})`,
            })),
          ]}
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
