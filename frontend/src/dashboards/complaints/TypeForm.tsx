import { Alert, Button, Checkbox, Group, NativeSelect, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import type { ComplaintType, Named } from './types'

/** Create a complaint type or change one: its area, target and whether it is offered. */
export function TypeForm(props: { areas: Named[]; type?: ComplaintType; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.type
  const [name, setName] = useState(editing?.name ?? '')
  const [areaId, setAreaId] = useState(editing?.area.id ?? props.areas[0]?.id ?? '')
  const [target, setTarget] = useState(String(editing?.target_days ?? ''))
  const [isActive, setIsActive] = useState(editing?.is_active ?? true)
  const label = (key: string) => t(`complaints.parameters.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { name, area_id: areaId, target_days: Number(target), is_active: isActive }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/types/${editing.id}`, body) : send('POST', '/types', body),
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
        <NativeSelect
          label={label('area')}
          description={label('areaHint')}
          value={areaId}
          onChange={(event) => setAreaId(event.currentTarget.value)}
          data={props.areas.map((area) => ({ value: area.id, label: area.name }))}
        />
        <TextInput
          label={label('targetField')}
          description={label('targetHint')}
          required
          withAsterisk={false}
          inputMode="numeric"
          pattern="[0-9]{1,3}"
          maxLength={3}
          value={target}
          onChange={(event) => setTarget(event.currentTarget.value)}
        />
        <Checkbox
          label={label('isActive')}
          checked={isActive}
          onChange={(event) => setIsActive(event.currentTarget.checked)}
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
