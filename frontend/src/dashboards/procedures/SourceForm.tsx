import { Alert, Button, Group, NativeSelect, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import { type Named, SOURCE_LEVELS, type Source } from './types'

/** Create a source, or edit an existing one. Only municipal sources belong to an area. */
export function SourceForm(props: { areas: Named[]; source?: Source; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.source
  const [name, setName] = useState(editing?.name ?? '')
  const [level, setLevel] = useState<string>(editing?.level ?? 'municipal')
  const [areaId, setAreaId] = useState(editing?.area?.id ?? '')
  const label = (key: string) => t(`procedures.parameters.${key}`)
  const isMunicipal = level === 'municipal'

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { name, level, area_id: isMunicipal && areaId ? areaId : null }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/sources/${editing.id}`, body) : send('POST', '/sources', body),
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
          label={label('level')}
          value={level}
          onChange={(event) => setLevel(event.currentTarget.value)}
          data={SOURCE_LEVELS.map((value) => ({ value, label: t(`procedures.levels.${value}`) }))}
        />
        {isMunicipal && (
          <NativeSelect
            label={label('area')}
            value={areaId}
            onChange={(event) => setAreaId(event.currentTarget.value)}
            data={[
              { value: '', label: label('noArea') },
              ...props.areas.map((area) => ({ value: area.id, label: area.name })),
            ]}
          />
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
