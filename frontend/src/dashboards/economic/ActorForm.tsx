import {
  Alert,
  Button,
  Group,
  NativeSelect,
  SimpleGrid,
  Stack,
  Textarea,
  TextInput,
} from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction, useActorTypes, useSectors } from './api'
import { formatCuit } from './format'
import type { Actor } from './types'

/** Create an economic actor, or edit an existing one. */
export function ActorForm(props: { actor?: Actor; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const actorTypes = useActorTypes()
  const sectors = useSectors()
  const editing = props.actor
  const [values, setValues] = useState({
    name: editing?.name ?? '',
    actor_type_id: editing?.actor_type?.id ?? '',
    sector_id: editing?.sector?.id ?? '',
    cuit: editing ? formatCuit(editing.cuit) : '',
    address: editing?.address ?? '',
    phone: editing?.phone ?? '',
    email: editing?.email ?? '',
    employee_count: editing?.employee_count?.toString() ?? '',
    notes: editing?.notes ?? '',
  })
  const [cuitInvalid, setCuitInvalid] = useState(false)
  const label = (key: string) => t(`economic.actors.${key}`)
  const set = (field: keyof typeof values) => (event: { currentTarget: { value: string } }) => {
    // Read now: the event is gone by the time the state updater runs.
    const value = event.currentTarget.value
    setValues((current) => ({ ...current, [field]: value }))
  }
  const options = (items: { id: string; name: string }[] | undefined, none: string) => [
    { value: '', label: none },
    ...(items ?? []).map((item) => ({ value: item.id, label: item.name })),
  ]

  async function submit(event: FormEvent) {
    event.preventDefault()
    const cuit = values.cuit.replace(/[-\s]/g, '')
    const invalid = cuit !== '' && !/^\d{11}$/.test(cuit)
    setCuitInvalid(invalid)
    if (invalid) return
    const body = {
      ...values,
      cuit,
      actor_type_id: values.actor_type_id || null,
      sector_id: values.sector_id || null,
      employee_count: values.employee_count === '' ? null : Number(values.employee_count),
    }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/actors/${editing.id}`, body) : send('POST', '/actors', body),
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
          value={values.name}
          onChange={set('name')}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NativeSelect
            label={label('type')}
            value={values.actor_type_id}
            onChange={set('actor_type_id')}
            data={options(actorTypes.data, label('noType'))}
          />
          <NativeSelect
            label={label('sector')}
            value={values.sector_id}
            onChange={set('sector_id')}
            data={options(sectors.data, label('noSector'))}
          />
          <TextInput
            label={label('cuit')}
            description={label('cuitHint')}
            inputMode="numeric"
            maxLength={13}
            error={cuitInvalid ? label('cuitInvalid') : undefined}
            value={values.cuit}
            onChange={set('cuit')}
          />
          <TextInput
            label={label('employees')}
            type="number"
            min={0}
            step={1}
            value={values.employee_count}
            onChange={set('employee_count')}
          />
          <TextInput
            label={label('phone')}
            maxLength={50}
            value={values.phone}
            onChange={set('phone')}
          />
          <TextInput
            label={label('email')}
            type="email"
            maxLength={200}
            value={values.email}
            onChange={set('email')}
          />
        </SimpleGrid>
        <TextInput
          label={label('address')}
          maxLength={200}
          value={values.address}
          onChange={set('address')}
        />
        <Textarea label={label('notes')} rows={3} value={values.notes} onChange={set('notes')} />
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
