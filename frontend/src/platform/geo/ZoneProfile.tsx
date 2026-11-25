import { Alert, Group, Loader, NativeSelect, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { dashboards } from '../../dashboards/registry'
import { errorMessage } from '../errorMessage'
import { StatCard } from '../StatCard'
import { useZoneProfile, useZones } from './api'
import { formatFigure } from './figures'
import { MapLoader } from './MapLoader'
import type { ProfileSection } from './types'

const ZonesMap = lazy(() => import('./ZonesMap'))

function Section({ section }: { section: ProfileSection }) {
  const { t } = useTranslation()
  const entry = dashboards.find((dashboard) => dashboard.key === section.dashboard_key)
  if (!entry) return null
  return (
    <Stack gap="xs" component="section" aria-label={t(entry.labelKey)}>
      <Title order={4}>{t(entry.labelKey)}</Title>
      <SimpleGrid cols={{ base: 1, xs: 2 }}>
        {section.metrics.map((metric) => (
          <StatCard
            key={metric.key}
            label={t(
              `geo.metrics.${section.dashboard_key}.${section.record_key}.${metric.key}.label`,
            )}
            value={formatFigure(section.values[metric.key], metric, t('geo.breakdown.hidden'))}
          />
        ))}
      </SimpleGrid>
      {section.groups.length > 0 && (
        <Text size="sm">
          {t(`geo.groupings.${section.grouping}.label`)}:{' '}
          {section.groups
            .map(
              (group) =>
                `${group.name ?? t(`geo.groupings.${section.grouping}.none`)} ${group.count}`,
            )
            .join(' · ')}
        </Text>
      )}
      {section.threshold !== null && section.suppressed && (
        <Text size="xs" c="dimmed">
          {t('geo.breakdown.hiddenNote', { count: section.threshold })}
        </Text>
      )}
    </Stack>
  )
}

/** What every dashboard the member can see has in one zone. Nothing until there are zones. */
export function ZoneProfile() {
  const { t } = useTranslation()
  const zones = useZones()
  const [zoneId, setZoneId] = useState<string | null>(null)
  const profile = useZoneProfile(zoneId)
  const drawn = useMemo(
    () =>
      (zones.data ?? []).map(({ id, name, boundary }) => ({
        id,
        boundary,
        label: name,
        selected: id === zoneId,
      })),
    [zones.data, zoneId],
  )

  if (zones.isError) return <Alert color="red">{errorMessage(zones.error)}</Alert>
  if (!zones.data || zones.data.length === 0) return null

  return (
    <Stack gap="sm" component="section" aria-label={t('geo.profile.title')}>
      <Title order={3}>{t('geo.profile.title')}</Title>
      <Group>
        <NativeSelect
          label={t('geo.zone')}
          value={zoneId ?? ''}
          onChange={(event) => setZoneId(event.currentTarget.value || null)}
          data={[
            { value: '', label: t('geo.profile.choose') },
            ...zones.data.map((zone) => ({ value: zone.id, label: zone.name })),
          ]}
        />
      </Group>
      {zoneId && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <Suspense fallback={<MapLoader />}>
            <ZonesMap label={t('geo.profile.mapLabel')} zones={drawn} onSelect={setZoneId} />
          </Suspense>
          <Stack>
            {profile.isLoading && <Loader aria-label={t('app.loading')} />}
            {profile.isError && <Alert color="red">{errorMessage(profile.error)}</Alert>}
            {profile.data?.sections.length === 0 && (
              <Text c="dimmed">{t('geo.profile.empty')}</Text>
            )}
            {profile.data?.sections.map((section) => (
              <Section key={`${section.dashboard_key}/${section.record_key}`} section={section} />
            ))}
          </Stack>
        </SimpleGrid>
      )}
    </Stack>
  )
}
