import { NativeSelect, SimpleGrid, TextInput } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { RegistryPersonForm } from '../../platform/people/RegistryPersonForm'
import { BASE_PATH, get, send, useAction } from './api'
import { EMPLOYMENT_STATUSES, type EconomicPerson, type Lookup } from './types'

/** Add a person to the dashboard, or edit one, with the dashboard's own data about them. */
export function PersonForm(props: { person?: EconomicPerson; onDone: () => void }) {
  const { t } = useTranslation()
  const action = useAction()
  const editing = props.person
  const [status, setStatus] = useState<string>(editing?.employment_status ?? 'unknown')
  const [occupation, setOccupation] = useState(editing?.occupation ?? '')
  const label = (key: string) => t(`economic.people.${key}`)

  return (
    <RegistryPersonForm
      person={editing?.person}
      lookup={(dni) => get<Lookup>('/people/lookup', { dni })}
      existingPath={(id) => `${BASE_PATH}/people/${id}`}
      save={(person) => {
        const body = { person, employment_status: status, occupation }
        return editing
          ? send('PATCH', `/people/${editing.id}`, body)
          : send('POST', '/people', body)
      }}
      action={action}
      onDone={props.onDone}
    >
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <NativeSelect
          label={label('employmentStatus')}
          value={status}
          onChange={(event) => setStatus(event.currentTarget.value)}
          data={EMPLOYMENT_STATUSES.map((value) => ({
            value,
            label: t(`economic.employmentStatuses.${value}`),
          }))}
        />
        <TextInput
          label={label('occupation')}
          maxLength={200}
          value={occupation}
          onChange={(event) => setOccupation(event.currentTarget.value)}
        />
      </SimpleGrid>
    </RegistryPersonForm>
  )
}
