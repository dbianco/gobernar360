import { Group, Stack } from '@mantine/core'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MapLoader } from '../../platform/geo/MapLoader'
import { UnzonedPanel } from '../../platform/geo/UnzonedPanel'
import { SearchInput } from '../../platform/SearchInput'
import { FilterBar } from './FilterBar'
import { PROJECTS } from './located'
import { useTerm } from './termContext'
import type { ProjectFilters } from './types'

const RecordsMap = lazy(() => import('../../platform/geo/RecordsMap'))

/** The term's projects on the map, with the filters of their list. */
export function MapPage() {
  const { t } = useTranslation()
  const { term } = useTerm()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<ProjectFilters>({})

  return (
    <Stack>
      <Group align="flex-end">
        <SearchInput value={q} onChange={setQ} placeholder={t('projects.list.searchHint')} />
        <FilterBar filters={filters} onChange={setFilters} withStatus />
      </Group>
      <Suspense fallback={<MapLoader />}>
        <RecordsMap
          kind={PROJECTS}
          label={t('geo.map.labels.projects.projects')}
          filters={{ term_id: term.id, q, ...filters }}
        />
      </Suspense>
      <UnzonedPanel kind={PROJECTS} title={t('geo.unzoned.titles.projects.projects')} />
    </Stack>
  )
}
