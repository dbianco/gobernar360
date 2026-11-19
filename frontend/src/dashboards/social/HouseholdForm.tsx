import { Alert, Button, Group, Stack, TextInput } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { send, useAction } from './api'
import type { Household } from './types'

/** Create a household, or edit its name and where it lives. */
export function HouseholdForm(props: { household?: Household; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.household
  const [name, setName] = useState(editing?.name ?? '')
  const [address, setAddress] = useState(editing?.address ?? '')
  const [neighborhood, setNeighborhood] = useState(editing?.neighborhood ?? '')
  const label = (key: string) => t(`social.households.${key}`)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const body = { name, address, neighborhood }
    const saved = await action.run(() =>
      editing ? send('PATCH', `/households/${editing.id}`, body) : send('POST', '/households', body),
    )
    if (saved) props.onDone()
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        {action.error && <Alert color="red">{action.error}</Alert>}
        <TextInput
          label={label('name')}
          placeholder={label('nameHint')}
          required
          withAsterisk={false}
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        <TextInput
          label={label('address')}
          maxLength={200}
          value={address}
          onChange={(event) => setAddress(event.currentTarget.value)}
        />
        <TextInput
          label={label('neighborhood')}
          maxLength={100}
          value={neighborhood}
          onChange={(event) => setNeighborhood(event.currentTarget.value)}
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
