import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { send, useAction, useTools } from './api'
import { todayIso } from './format'
import type { Assignment } from './types'

export type AssignmentTarget = { actor_id: string } | { person_id: string }

/**
 * Assign one of the tools offered to this kind of recipient, or correct the date
 * and the note of an existing assignment.
 */
export function AssignmentForm(props: {
  target: AssignmentTarget
  assignment?: Assignment
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const tools = useTools()
  const [toolId, setToolId] = useState('')
  const editing = props.assignment
  const [date, setDate] = useState(() => editing?.date ?? todayIso())
  const [note, setNote] = useState(editing?.note ?? '')
  const label = (key: string) => t(`economic.assignments.${key}`)
  const audience = 'actor_id' in props.target ? 'actors' : 'people'
  const offered = (tools.data ?? [])
    .filter((tool) => tool.audience === 'both' || tool.audience === audience)
    .sort((a, b) => a.name.localeCompare(b.name, 'es'))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() =>
      editing
        ? send('PATCH', `/assignments/${editing.id}`, { date, note })
        : send('POST', '/assignments', { tool_id: toolId, ...props.target, date, note }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {tools.isError && <Alert color="red">{errorMessage(tools.error)}</Alert>}
        {!editing && tools.data && offered.length === 0 && (
          <Text c="dimmed">{label('noTools')}</Text>
        )}
        {editing ? (
          <TextInput
            label={label('tool')}
            description={label('toolFixed')}
            disabled
            value={editing.tool.name}
            readOnly
          />
        ) : (
          <NativeSelect
            label={label('tool')}
            required
            withAsterisk={false}
            value={toolId}
            onChange={(event) => setToolId(event.currentTarget.value)}
            data={[
              { value: '', label: label('chooseTool') },
              ...offered.map((tool) => ({ value: tool.id, label: tool.name })),
            ]}
          />
        )}
        <TextInput
          label={label('date')}
          type="date"
          required
          withAsterisk={false}
          value={date}
          onChange={(event) => setDate(event.currentTarget.value)}
        />
        <Textarea
          label={label('note')}
          rows={2}
          value={note}
          onChange={(event) => setNote(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onDone}>
            {t('app.cancel')}
          </Button>
          <Button
            type="submit"
            loading={action.pending}
            disabled={!editing && offered.length === 0}
          >
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
