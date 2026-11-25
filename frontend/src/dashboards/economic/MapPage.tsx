import { Group, NativeSelect, Stack } from '@mantine/core'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MapLoader } from '../../platform/geo/MapLoader'
import { UnzonedPanel } from '../../platform/geo/UnzonedPanel'
import { SearchInput } from '../../platform/SearchInput'
import { useActorTypes, useSectors } from './api'
import { ACTORS } from './located'

const RecordsMap = lazy(() => import('../../platform/geo/RecordsMap'))

/** The economic actors on the map, with the filters of their list. */
export function MapPage() {
  const { t } = useTranslation()
  const [filters, setFilters] = useState({ q: '', actor_type_id: '', sector_id: '' })
  const actorTypes = useActorTypes()
  const sectors = useSectors()
  const label = (key: string) => t(`economic.actors.${key}`)
  const change = (field: keyof typeof filters, value: string) =>
    setFilters((current) => ({ ...current, [field]: value }))
  const options = (items: { id: string; name: string }[] | undefined, all: string) => [
    { value: '', label: all },
    ...(items ?? []).map((item) => ({ value: item.id, label: item.name })),
  ]

  return (
    <Stack>
      <Group align="flex-end">
        <SearchInput
          value={filters.q}
          onChange={(value) => change('q', value)}
          placeholder={label('searchHint')}
        />
        <NativeSelect
          label={label('type')}
          value={filters.actor_type_id}
          onChange={(event) => change('actor_type_id', event.currentTarget.value)}
          data={options(actorTypes.data, label('allTypes'))}
        />
        <NativeSelect
          label={label('sector')}
          value={filters.sector_id}
          onChange={(event) => change('sector_id', event.currentTarget.value)}
          data={options(sectors.data, label('allSectors'))}
        />
      </Group>
      <Suspense fallback={<MapLoader />}>
        <RecordsMap
          kind={ACTORS}
          label={t('geo.map.labels.economic.actors')}
          filters={filters}
        />
      </Suspense>
      <UnzonedPanel kind={ACTORS} title={t('geo.unzoned.titles.economic.actors')} />
    </Stack>
  )
}
