import { Alert, Button, Group, Stack, Text, TextInput } from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { usePeople } from './api'
import type { PersonRef, SocialPerson } from './types'

const MATCHES_SHOWN = 8

/** Find people already in the dashboard by name or document. */
export function PersonSearch(props: {
  /** What to offer next to each match, e.g. a button to pick them. */
  children: (person: SocialPerson) => ReactNode
  /** Matches that make no sense here, e.g. those already chosen. */
  hide?: (person: SocialPerson) => boolean
  /** Controls shown beside the search box. */
  extra?: ReactNode
}) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const ready = search.trim().length >= 2
  const people = usePeople({ q: search.trim(), limit: MATCHES_SHOWN }, ready)
  const label = (key: string) => t(`social.people.${key}`)
  const found = people.data?.items ?? []
  const matches = props.hide ? found.filter((person) => !props.hide?.(person)) : found

  return (
    <Stack gap="xs">
      <Group align="flex-end">
        <TextInput
          label={label('find')}
          description={label('findHint')}
          maxLength={100}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
        />
        {props.extra}
      </Group>
      {people.isError && <Alert color="red">{errorMessage(people.error)}</Alert>}
      {ready && people.data && matches.length === 0 && <Text c="dimmed">{label('noMatches')}</Text>}
      {ready &&
        matches.map((person) => (
          <Group key={person.id} justify="space-between" wrap="nowrap">
            <Text>{person.person.full_name}</Text>
            {props.children(person)}
          </Group>
        ))}
      {ready && people.data && people.data.total > found.length && (
        <Text size="sm" c="dimmed">
          {label('moreMatches')}
        </Text>
      )}
    </Stack>
  )
}

/** Choose the person a new record is about. */
export function PersonPicker(props: {
  value: PersonRef | null
  onChange: (person: PersonRef | null) => void
}) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`social.people.${key}`, options)

  if (props.value) {
    return (
      <Group justify="space-between" wrap="nowrap">
        <div>
          <Text size="sm" fw={500}>
            {label('choose')}
          </Text>
          <Text>{props.value.full_name}</Text>
        </div>
        <Button size="compact-sm" variant="default" onClick={() => props.onChange(null)}>
          {label('change')}
        </Button>
      </Group>
    )
  }
  return (
    <PersonSearch>
      {(person) => (
        <Button
          size="compact-sm"
          variant="default"
          aria-label={label('chooseNamed', { name: person.person.full_name })}
          onClick={() => props.onChange({ id: person.id, full_name: person.person.full_name })}
        >
          {label('pick')}
        </Button>
      )}
    </PersonSearch>
  )
}
