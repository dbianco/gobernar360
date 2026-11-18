import { Alert, Anchor, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber, formatPercent, formatRatio } from '../../platform/format'
import { StatCard } from '../../platform/StatCard'
import { dashboards } from '../registry'

interface OverviewIndicator {
  key: string
  value: number | null
  unit: string | null
}

interface DashboardOverview {
  dashboard_key: string
  indicators: OverviewIndicator[]
}

function formatIndicator(indicator: OverviewIndicator): string {
  if (indicator.unit === 'percent') return formatPercent(indicator.value)
  if (indicator.unit === 'ratio') return formatRatio(indicator.value)
  return formatNumber(indicator.value)
}

/** Home page: headline indicators of every dashboard the user can see. */
export function OverviewPage() {
  const { t } = useTranslation()
  const overview = useQuery({
    queryKey: ['overview'],
    queryFn: () => api<DashboardOverview[]>('/overview'),
  })

  return (
    <Stack>
      <Title order={2}>{t('overview.title')}</Title>
      {overview.isLoading && <Loader aria-label={t('app.loading')} />}
      {overview.isError && <Alert color="red">{errorMessage(overview.error)}</Alert>}
      {overview.data?.length === 0 && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{t('overview.emptyTitle')}</Title>
          <Text c="dimmed">{t('overview.emptyBody')}</Text>
        </Stack>
      )}
      {overview.data?.map((section) => {
        const entry = dashboards.find((dashboard) => dashboard.key === section.dashboard_key)
        if (!entry) return null
        return (
          <Stack key={section.dashboard_key} gap="sm">
            <Group justify="space-between" align="baseline">
              <Title order={3}>{t(entry.labelKey)}</Title>
              <Anchor component={Link} to={entry.basePath}>
                {t('overview.open')}
              </Anchor>
            </Group>
            {section.indicators.length === 0 ? (
              <Text c="dimmed">{t('overview.noData')}</Text>
            ) : (
              <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
                {section.indicators.map((indicator) => (
                  <StatCard
                    key={indicator.key}
                    label={t(`overview.indicators.${indicator.key}`)}
                    value={formatIndicator(indicator)}
                  />
                ))}
              </SimpleGrid>
            )}
          </Stack>
        )
      })}
    </Stack>
  )
}
