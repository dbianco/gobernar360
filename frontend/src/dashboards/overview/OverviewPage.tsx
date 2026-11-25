import {
  ActionIcon,
  Alert,
  Anchor,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { api } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { ZoneProfile } from '../../platform/geo/ZoneProfile'
import { useCombinedIndicators } from '../../platform/indicators/api'
import { IndicatorGrid } from '../../platform/indicators/IndicatorCard'
import type { IndicatorEvolution } from '../../platform/indicators/types'
import { StatusCard } from '../../platform/status/StatusCard'
import type { DatedStatus } from '../../platform/status/types'
import { type DashboardEntry, dashboards } from '../registry'

interface DashboardOverview {
  dashboard_key: string
  /** The indicators the dashboard reports today, with their evolution. */
  indicators: IndicatorEvolution[]
  /** Recent status lights, newest first. */
  status: DatedStatus[]
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

/** Indicators that relate two dashboards; only those the member can see both sides of. */
/**
 * One icon per dashboard, next to the page title, that shows or hides everything of that
 * dashboard on the page. The choice lasts while the page is open.
 */
function DashboardToggles(props: {
  entries: DashboardEntry[]
  hidden: string[]
  onToggle: (key: string) => void
}) {
  const { t } = useTranslation()
  return (
    <Group gap={6} role="group" aria-label={t('overview.toggles')}>
      {/* One tooltip at a time: the clicked icon keeps focus, and with it its tooltip. */}
      <Tooltip.Group>
        {props.entries.map((entry) => {
          const shown = !props.hidden.includes(entry.key)
          const label = t(shown ? 'overview.hide' : 'overview.show', { name: t(entry.labelKey) })
          return (
            <Tooltip
              key={entry.key}
              label={label}
              withArrow
              events={{ hover: true, focus: true, touch: true }}
            >
              <ActionIcon
                size={34}
                // Light while it is shown, dark once hidden.
                variant={shown ? 'light' : 'filled'}
                color={shown ? undefined : 'dark'}
                aria-label={label}
                aria-pressed={shown}
                onClick={() => props.onToggle(entry.key)}
              >
                <entry.icon size={22} stroke={1.5} aria-hidden />
              </ActionIcon>
            </Tooltip>
          )
        })}
      </Tooltip.Group>
    </Group>
  )
}

/** Indicators relating two dashboards; only those whose dashboards are all shown. */
function CombinedSection({ hidden }: { hidden: string[] }) {
  const { t } = useTranslation()
  const combined = useCombinedIndicators()
  const shown = (combined.data ?? []).filter((item) =>
    item.dashboard_keys.every((key) => !hidden.includes(key)),
  )
  if (!shown.length) return null
  return (
    <Stack gap="sm" component="section" aria-label={t('overview.combined.title')}>
      <Group gap="sm" align="baseline">
        <Title order={3}>{t('overview.combined.title')}</Title>
        <Text size="sm" c="dimmed">
          {t('overview.combined.hint')}
        </Text>
      </Group>
      {/* They have no targets of their own. */}
      <IndicatorGrid indicators={shown} withTargets={false} />
    </Stack>
  )
}

/**
 * Home page: the status light and headline indicators of every dashboard the user can see,
 * with their evolution, and the indicators that combine dashboards.
 */
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
  // Dashboards hidden from this page; not remembered, so every visit starts with all of them.
  const [hidden, setHidden] = useState<string[]>([])
  const toggleShown = (key: string) =>
    setHidden((current) =>
      current.includes(key) ? current.filter((other) => other !== key) : [...current, key],
    )
  const sections = (overview.data ?? []).flatMap((section) => {
    const entry = dashboards.find((dashboard) => dashboard.key === section.dashboard_key)
    return entry ? [{ ...section, entry }] : []
  })
  const shownSections = sections.filter(({ entry }) => !hidden.includes(entry.key))

  return (
    <Stack>
      <Group gap="lg" align="center">
        <Title order={2}>{t('overview.title')}</Title>
        {sections.length > 0 && (
          <DashboardToggles
            entries={sections.map(({ entry }) => entry)}
            hidden={hidden}
            onToggle={toggleShown}
          />
        )}
      </Group>
      {overview.isLoading && <Loader aria-label={t('app.loading')} />}
      {overview.isError && <Alert color="red">{errorMessage(overview.error)}</Alert>}
      {overview.data?.length === 0 && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{t('overview.emptyTitle')}</Title>
          <Text c="dimmed">{t('overview.emptyBody')}</Text>
        </Stack>
      )}
      {sections.length > 0 && shownSections.length === 0 && (
        <Text c="dimmed">{t('overview.noneShown')}</Text>
      )}
      {shownSections.length > 0 && (
        <SimpleGrid
          cols={{ base: 1, sm: 2, lg: 4 }}
          component="section"
          aria-label={t('overview.lights')}
        >
          {shownSections.map(({ entry, status }) => (
            <StatusCard
              key={entry.key}
              name={t(entry.labelKey)}
              icon={entry.icon}
              status={status}
            />
          ))}
        </SimpleGrid>
      )}
      {shownSections.length > 0 && <CombinedSection hidden={hidden} />}
      {shownSections.map(({ entry, indicators }) => {
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
                <IndicatorGrid indicators={indicators} />
              ))}
          </Stack>
        )
      })}
      {sections.length > 0 && <ZoneProfile />}
    </Stack>
  )
}
