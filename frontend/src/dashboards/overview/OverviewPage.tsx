import {
  Alert,
  Anchor,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber, formatPercent, formatRatio } from '../../platform/format'
import { StatCard } from '../../platform/StatCard'
import { StatusCard } from '../../platform/status/StatusCard'
import type { DatedStatus } from '../../platform/status/types'
import { dashboards } from '../registry'

interface OverviewIndicator {
  key: string
  value: number | null
  unit: string | null
}

interface DashboardOverview {
  dashboard_key: string
  indicators: OverviewIndicator[]
  /** Recent status lights, newest first. */
  status: DatedStatus[]
}

function formatIndicator(indicator: OverviewIndicator): string {
  if (indicator.unit === 'percent') return formatPercent(indicator.value)
  if (indicator.unit === 'ratio') return formatRatio(indicator.value)
  return formatNumber(indicator.value)
}

const COLLAPSED_STORAGE_KEY = 'overview.collapsed'

/** Keys of the sections this browser left collapsed. Storage may be blocked, hence the guards. */
function readCollapsed(): string[] {
  try {
    const stored: unknown = JSON.parse(window.localStorage.getItem(COLLAPSED_STORAGE_KEY) ?? '[]')
    return Array.isArray(stored) ? stored.filter((key) => typeof key === 'string') : []
  } catch {
    return []
  }
}

function storeCollapsed(keys: string[]) {
  try {
    window.localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify(keys))
  } catch {
    // The choice simply lasts until the page is left.
  }
}

/** Home page: the status light and headline indicators of every dashboard the user can see. */
export function OverviewPage() {
  const { t } = useTranslation()
  const overview = useQuery({
    queryKey: ['overview'],
    queryFn: () => api<DashboardOverview[]>('/overview'),
  })

  const [collapsed, setCollapsed] = useState(readCollapsed)
  const toggle = (key: string) => {
    const next = collapsed.includes(key)
      ? collapsed.filter((other) => other !== key)
      : [...collapsed, key]
    setCollapsed(next)
    storeCollapsed(next)
  }
  const sections = (overview.data ?? []).flatMap((section) => {
    const entry = dashboards.find((dashboard) => dashboard.key === section.dashboard_key)
    return entry ? [{ ...section, entry }] : []
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
      {sections.length > 0 && (
        <SimpleGrid
          cols={{ base: 1, sm: 2, lg: 4 }}
          component="section"
          aria-label={t('overview.lights')}
        >
          {sections.map(({ entry, status }) => (
            <StatusCard
              key={entry.key}
              name={t(entry.labelKey)}
              icon={entry.icon}
              status={status}
            />
          ))}
        </SimpleGrid>
      )}
      {sections.map(({ entry, indicators }) => {
        const open = !collapsed.includes(entry.key)
        const Chevron = open ? IconChevronDown : IconChevronRight
        return (
          <Stack key={entry.key} gap="sm" component="section">
            <Group justify="space-between" align="baseline">
              <Title order={3}>
                <UnstyledButton
                  fz="inherit"
                  fw="inherit"
                  aria-expanded={open}
                  onClick={() => toggle(entry.key)}
                >
                  <Group gap={6} wrap="nowrap">
                    <Chevron size={20} aria-hidden />
                    {t(entry.labelKey)}
                  </Group>
                </UnstyledButton>
              </Title>
              <Anchor component={Link} to={entry.basePath}>
                {t('overview.open')}
              </Anchor>
            </Group>
            {open &&
              (indicators.length === 0 ? (
                <Text c="dimmed">{t('overview.noData')}</Text>
              ) : (
                <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
                  {indicators.map((indicator) => (
                    <StatCard
                      key={indicator.key}
                      label={t(`overview.indicators.${indicator.key}`)}
                      value={formatIndicator(indicator)}
                    />
                  ))}
                </SimpleGrid>
              ))}
          </Stack>
        )
      })}
    </Stack>
  )
}
