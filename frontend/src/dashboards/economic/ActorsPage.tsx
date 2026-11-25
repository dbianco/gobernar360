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
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { zoneNames } from '../../platform/geo/zoneNames'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/access'
import { ActorForm } from './ActorForm'
import { BASE_PATH, useActors, useActorTypes, useSectors } from './api'
import { formatCuit } from './format'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Searchable list of the municipality's economic actors. */
export function ActorsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [filters, setFilters] = useState({ q: '', actor_type_id: '', sector_id: '' })
  const paging = usePaging('economic.actors')
  const { limit, offset, setOffset } = paging
  const [creating, setCreating] = useState(false)
  const actors = useActors({ ...filters, limit, offset })
  fitPage(paging, actors)
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
          <SearchInput
            value={filters.q}
            onChange={(value) => filter('q')({ currentTarget: { value } })}
            placeholder={label('searchHint')}
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
                <HelpTh help={t('economic.help.actorsPage.name')}>{label('name')}</HelpTh>
                <HelpTh help={t('economic.help.actorsPage.type')}>{label('type')}</HelpTh>
                <HelpTh help={t('economic.help.actorsPage.sector')}>{label('sector')}</HelpTh>
                <HelpTh help={t('economic.help.actorsPage.zones')}>{t('geo.zone')}</HelpTh>
                <HelpTh help={t('economic.help.actorsPage.cuit')}>{label('cuit')}</HelpTh>
                <HelpTh help={t('economic.help.actorsPage.employees')} ta="right">
                  {label('employees')}
                </HelpTh>
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
                  <Table.Td>{zoneNames(actor.zones, t('app.none'))}</Table.Td>
                  <Table.Td>{actor.cuit ? formatCuit(actor.cuit) : t('app.none')}</Table.Td>
                  <Table.Td ta="right">{actor.employee_count ?? t('app.none')}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {actors.data && (
        <Pager {...paging.pager(actors.data.total)} />
      )}
      <Modal opened={creating} onClose={() => setCreating(false)} title={label('createTitle')} size="lg">
        {creating && <ActorForm onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
