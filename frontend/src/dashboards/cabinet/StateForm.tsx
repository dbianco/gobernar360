import { Alert, Button, Group, Stack, Textarea } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { todayIso } from '../../platform/format'
import { send, useAction } from './api'
import type { Commitment } from './types'

/** Says a commitment was delivered, and when, or that it was dropped. */
export function StateForm(props: {
  commitment: Commitment
  state: 'done' | 'dropped'
  onDone: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [completedOn, setCompletedOn] = useState(todayIso)
  const [note, setNote] = useState('')
  const label = (key: string) => t(`cabinet.commitment.${key}`)
  const isDone = props.state === 'done'

  async function submit(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() =>
      send('POST', `/commitments/${props.commitment.id}/state`, {
        state: props.state,
        ...(isDone && { completed_on: completedOn }),
        note,
      }),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        {isDone && (
          <DateField
            label={label('completedOn')}
            required
            max={todayIso()}
            maw={220}
            value={completedOn}
            onChange={setCompletedOn}
          />
        )}
        <Textarea
          label={label('note')}
          rows={3}
          maxLength={5000}
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
