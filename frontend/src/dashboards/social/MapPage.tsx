import { Stack, Text } from '@mantine/core'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { hasLevel } from '../../platform/access'
import { useAuth } from '../../platform/authContext'
import { MapLoader } from '../../platform/geo/MapLoader'
import { UnzonedPanel } from '../../platform/geo/UnzonedPanel'
import { ZoneBreakdown } from '../../platform/geo/ZoneBreakdown'
import { SearchInput } from '../../platform/SearchInput'
import { currentYear } from '../../platform/years'
import { HOUSEHOLDS } from './located'

const RecordsMap = lazy(() => import('../../platform/geo/RecordsMap'))

/** Households on the map for those who load data; for viewers, counts by zone only. */
export function MapPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [q, setQ] = useState('')

  if (!hasLevel(me, HOUSEHOLDS.dashboard, HOUSEHOLDS.individualLevel)) {
    return (
      <Stack>
        <Text c="dimmed">{t('geo.map.restricted')}</Text>
        <ZoneBreakdown kind={HOUSEHOLDS} filters={{ year: currentYear() }} />
      </Stack>
    )
  }
  return (
    <Stack>
      <SearchInput value={q} onChange={setQ} placeholder={t('social.households.searchHint')} />
      <Suspense fallback={<MapLoader />}>
        <RecordsMap
          kind={HOUSEHOLDS}
          label={t('geo.map.labels.social.households')}
          filters={{ q }}
        />
      </Suspense>
      <UnzonedPanel kind={HOUSEHOLDS} title={t('geo.unzoned.titles.social.households')} />
    </Stack>
  )
}
