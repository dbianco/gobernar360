import {
  Alert,
  Anchor,
  Container,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { IconLayoutDashboard } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { api, ApiError, downloadUrl } from '../api/client'
import { dashboards as installed } from '../dashboards/registry'
import { errorMessage } from '../platform/errorMessage'
import { formatTimestampDate } from '../platform/format'
import { StatusCard } from '../platform/status/StatusCard'
import { PublicIndicatorCard } from './PublicIndicatorCard'
import type { PublicSite } from './types'

/**
 * A municipality's public transparency page, for anyone and without signing in: the lights
 * and indicators it published and its published monthly reports.
 */
export function PublicPage() {
  const { t } = useTranslation()
  const { slug = '' } = useParams()
  const site = useQuery({
    queryKey: ['public', slug],
    queryFn: () => api<PublicSite>(`/public/${encodeURIComponent(slug)}`),
    retry: false,
  })
  const notFound = site.error instanceof ApiError && site.error.status === 404
  const data = site.data
  const monthName = (year: number, month: number) =>
    t('status.monthYear', { month: t(`status.months.${month}`), year }).toLowerCase()

  return (
    <Container size="lg" py="xl">
      {site.isLoading && <Loader aria-label={t('app.loading')} />}
      {notFound && (
        <Stack gap="xs">
          <Title order={1}>{t('public.notFoundTitle')}</Title>
          <Text c="dimmed">{t('public.notFoundBody')}</Text>
        </Stack>
      )}
      {site.isError && !notFound && <Alert color="red">{errorMessage(site.error)}</Alert>}
      {data && (
        <Stack gap="xl">
          <Stack gap={2} component="header">
            <Text size="sm" c="dimmed" tt="uppercase">
              {t(`public.${data.kind}`)}
            </Text>
            <Title order={1}>{data.name}</Title>
            <Text size="lg">{t('public.subtitle')}</Text>
          </Stack>

          {data.dashboards.length > 0 && (
            <Stack gap="sm" component="section" aria-label={t('public.lights')}>
              <Title order={2}>{t('public.lights')}</Title>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
                {data.dashboards.map((dashboard) => {
                  const entry = installed.find((item) => item.key === dashboard.key)
                  return (
                    <StatusCard
                      key={dashboard.key}
                      name={entry ? t(entry.labelKey) : dashboard.name}
                      icon={entry?.icon ?? IconLayoutDashboard}
                      status={[...dashboard.lights].reverse().slice(0, 6)}
                    />
                  )
                })}
              </SimpleGrid>
            </Stack>
          )}

          {data.indicators.length > 0 && (
            <Stack gap="sm" component="section" aria-label={t('public.indicators')}>
              <Title order={2}>{t('public.indicators')}</Title>
              <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
                {data.indicators.map((indicator) => (
                  <PublicIndicatorCard key={indicator.key} indicator={indicator} />
                ))}
              </SimpleGrid>
            </Stack>
          )}

          <Stack gap="sm" component="section" aria-label={t('public.reports')}>
            <Title order={2}>{t('public.reports')}</Title>
            {data.reports.length === 0 && <Text c="dimmed">{t('public.noReports')}</Text>}
            {data.reports.map((report) => (
              <Group key={`${report.year}-${report.month}`} gap="sm">
                <Text fw={500}>
                  {t('public.report', { month: monthName(report.year, report.month) })}
                </Text>
                <Text size="sm" c="dimmed">
                  {t('public.reportVersion', {
                    version: report.version,
                    date: formatTimestampDate(report.closed_at),
                  })}
                </Text>
                <Anchor
                  href={downloadUrl(
                    `/public/${encodeURIComponent(data.slug)}` +
                      `/reports/${report.year}/${report.month}`,
                  )}
                  target="_blank"
                >
                  {t('public.download')}
                </Anchor>
              </Group>
            ))}
          </Stack>

          <Stack gap={2} component="footer">
            {data.small_count_threshold > 1 && (
              <Text size="xs" c="dimmed">
                {t('public.note', {
                  count: data.small_count_threshold,
                  last: data.small_count_threshold - 1,
                })}
              </Text>
            )}
            <Text size="xs" c="dimmed">
              {t('public.poweredBy')}
            </Text>
          </Stack>
        </Stack>
      )}
    </Container>
  )
}
