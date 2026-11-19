import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDni } from '../../platform/format'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, PAGE_SIZE, usePeople } from './api'
import { PersonForm } from './PersonForm'

/** Searchable list of the people incorporated into the dashboard. */
export function PeoplePage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [filters, setFilters] = useState({ q: '', neighborhood: '' })
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const people = usePeople({ ...filters, limit: PAGE_SIZE, offset })
  const label = (key: string) => t(`social.people.${key}`)
  const filter = (field: keyof typeof filters) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setFilters((current) => ({ ...current, [field]: value }))
    setOffset(0)
  }

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <TextInput
            label={t('app.search')}
            placeholder={label('searchHint')}
            maxLength={100}
            value={filters.q}
            onChange={filter('q')}
          />
          <TextInput
            label={label('neighborhoodFilter')}
            maxLength={100}
            value={filters.neighborhood}
            onChange={filter('neighborhood')}
          />
        </Group>
        {hasLevel(me, 'social', 'editor') && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {people.isLoading && <Loader aria-label={t('app.loading')} />}
      {people.isError && <Alert color="red">{errorMessage(people.error)}</Alert>}
      {people.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {people.data && people.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('people.fullName')}</Table.Th>
                <Table.Th>{t('people.dni')}</Table.Th>
                <Table.Th>{t('people.neighborhood')}</Table.Th>
                <Table.Th>{label('household')}</Table.Th>
                <Table.Th>{label('relationship')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {people.data.items.map((item) => (
                <Table.Tr key={item.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${BASE_PATH}/people/${item.id}`}>
                      {item.person.full_name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{formatDni(item.person.dni)}</Table.Td>
                  <Table.Td>{item.person.neighborhood || t('app.none')}</Table.Td>
                  <Table.Td>
                    {item.household ? (
                      <Anchor component={Link} to={`${BASE_PATH}/households/${item.household.id}`}>
                        {item.household.name}
                      </Anchor>
                    ) : (
                      <Text span c="dimmed">
                        {label('noHousehold')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {item.relationship
                      ? t(`social.relationships.${item.relationship}`)
                      : t('app.none')}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {people.data && (
        <Pager total={people.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
      )}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={label('createTitle')}
        size="lg"
      >
        {creating && <PersonForm onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
