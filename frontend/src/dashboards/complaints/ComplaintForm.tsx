import { Alert, Button, Group, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { lookupPerson, send, useAction } from './api'
import {
  type Complainant,
  currentLookup,
  EMPTY_COMPLAINANT,
  normaliseDni,
  validDni,
} from './complainant'
import { ComplainantPicker } from './ComplainantPicker'
import type { ComplaintDetail, ComplaintType, Named } from './types'

/** Register a complaint received now. It goes to its type's area, with the type's target. */
export function ComplaintForm(props: {
  types: ComplaintType[]
  zones: Named[]
  onDone: (created?: ComplaintDetail) => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const offered = props.types.filter((type) => type.is_active)
  const [typeId, setTypeId] = useState(offered[0]?.id ?? '')
  const [zoneId, setZoneId] = useState(props.zones[0]?.id ?? '')
  const [address, setAddress] = useState('')
  const [description, setDescription] = useState('')
  const [complainant, setComplainant] = useState<Complainant>(EMPTY_COMPLAINANT)
  const [looking, setLooking] = useState(false)
  const [lookupError, setLookupError] = useState<string | null>(null)
  const label = (key: string, options = {}) => t(`complaints.form.${key}`, options)
  const type = offered.find((item) => item.id === typeId)

  async function lookup(): Promise<void> {
    const dni = normaliseDni(complainant.dni)
    setLooking(true)
    setLookupError(null)
    try {
      const result = await lookupPerson(dni)
      setComplainant((current) => ({ ...current, lookup: { dni, result } }))
    } catch (error) {
      setLookupError(errorMessage(error))
    } finally {
      setLooking(false)
    }
  }

  function resident(): Record<string, unknown> | null {
    if (complainant.anonymous) return {}
    const known = currentLookup(complainant)
    if (!known) return null
    if (known.person) return { person_id: known.person.id }
    return {
      new_person: { ...complainant.newPerson, dni: normaliseDni(complainant.dni) },
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!complainant.anonymous && !validDni(complainant.dni)) return
    const who = resident()
    if (who === null) {
      // Show who the registry has before saving, so the complaint is not filed to a stranger.
      await lookup()
      return
    }
    const body = { type_id: typeId, zone_id: zoneId, address, description, ...who }
    const created = await action.run(() => send<ComplaintDetail>('POST', '/complaints', body))
    if (created) props.onDone(created)
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <NativeSelect
          label={label('type')}
          value={typeId}
          onChange={(event) => setTypeId(event.currentTarget.value)}
          data={offered.map((item) => ({ value: item.id, label: item.name }))}
        />
        {type && (
          <Text size="sm" c="dimmed">
            {label('routing', { area: type.area.name, count: type.target_days })}
          </Text>
        )}
        <NativeSelect
          label={label('zone')}
          value={zoneId}
          onChange={(event) => setZoneId(event.currentTarget.value)}
          data={props.zones.map((zone) => ({ value: zone.id, label: zone.name }))}
        />
        <TextInput
          label={label('address')}
          description={label('addressHint')}
          required
          withAsterisk={false}
          maxLength={200}
          value={address}
          onChange={(event) => setAddress(event.currentTarget.value)}
        />
        <Textarea
          label={label('description')}
          rows={3}
          maxLength={5000}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            {label('complainant')}
          </Text>
          <ComplainantPicker
            value={complainant}
            onChange={setComplainant}
            onLookup={() => void lookup()}
            looking={looking}
            error={lookupError}
          />
        </Stack>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => props.onDone()}>
            {t('app.cancel')}
          </Button>
          <Button type="submit" loading={action.pending || looking}>
            {t('app.save')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
