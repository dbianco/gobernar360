import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
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
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { ActorForm } from './ActorForm'
import { BASE_PATH, PAGE_SIZE, useActors, useActorTypes, useSectors } from './api'
import { formatCuit } from './format'

/** Searchable list of the municipality's economic actors. */
export function ActorsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [filters, setFilters] = useState({ q: '', actor_type_id: '', sector_id: '' })
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const actors = useActors({ ...filters, limit: PAGE_SIZE, offset })
  const actorTypes = useActorTypes()
  const sectors = useSectors()
  const label = (key: string) => t(`economic.actors.${key}`)
  const filter = (field: keyof typeof filters) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    setOffset(0)
  }
  const options = (items: { id: string; name: string }[] | undefined, all: string) => [
    { value: '', label: all },
    ...(items ?? []).map((item) => ({ value: item.id, label: item.name })),
  ]

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
          <NativeSelect
            label={label('type')}
            value={filters.actor_type_id}
            onChange={filter('actor_type_id')}
            data={options(actorTypes.data, label('allTypes'))}
          />
          <NativeSelect
            label={label('sector')}
            value={filters.sector_id}
            onChange={filter('sector_id')}
            data={options(sectors.data, label('allSectors'))}
          />
        </Group>
        {hasLevel(me, 'economic', 'editor') && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {actors.isLoading && <Loader aria-label={t('app.loading')} />}
      {actors.isError && <Alert color="red">{errorMessage(actors.error)}</Alert>}
      {actors.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {actors.data && actors.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{label('name')}</Table.Th>
                <Table.Th>{label('type')}</Table.Th>
                <Table.Th>{label('sector')}</Table.Th>
                <Table.Th>{label('cuit')}</Table.Th>
                <Table.Th ta="right">{label('employees')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {actors.data.items.map((actor) => (
                <Table.Tr key={actor.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`${BASE_PATH}/actors/${actor.id}`}>
                      {actor.name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{actor.actor_type?.name ?? t('app.none')}</Table.Td>
                  <Table.Td>{actor.sector?.name ?? t('app.none')}</Table.Td>
                  <Table.Td>{actor.cuit ? formatCuit(actor.cuit) : t('app.none')}</Table.Td>
                  <Table.Td ta="right">{actor.employee_count ?? t('app.none')}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {actors.data && (
        <Pager total={actors.data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
      )}
      <Modal opened={creating} onClose={() => setCreating(false)} title={label('createTitle')} size="lg">
        {creating && <ActorForm onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
