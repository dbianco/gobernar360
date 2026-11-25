import { Alert, Anchor, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { ZoneBreakdown } from '../../platform/geo/ZoneBreakdown'
import { boundariesOf } from '../../platform/geo/asOf'
import { formatMoney, formatPercent, formatRatio } from '../../platform/format'
import { HeadlineIndicators } from '../../platform/indicators/HeadlineIndicators'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { currentYear } from '../../platform/years'
import { BASE, useSummary } from './api'
import { CountBarChart } from './CountBarChart'
import { FilterBar } from './FilterBar'
import { PROJECTS } from './located'
import { useTerm } from './termContext'
import { EFFECTIVE_STATUSES, type ProjectFilters } from './types'

/**
 * The headline indicators of the latest term with their evolution and targets, then the
 * chosen term's projects in detail, with filters and CSV downloads.
 */
export function SummaryPage() {
  const { t } = useTranslation()
  const { term } = useTerm()
  const [filters, setFilters] = useState<ProjectFilters>({})
  const [statusYear, setStatusYear] = useState(currentYear)
  const summary = useSummary(term.id, filters)
  const data = summary.data

  return (
    <Stack>
      {/* Projects are looked at by term, not by year, so the strip chooses its own year. */}
      <StatusStrip dashboardKey="projects" year={statusYear} onYearChange={setStatusYear} />
      <HeadlineIndicators dashboardKey="projects" />
      <Group gap="sm" align="baseline" mt="sm">
        <Title order={4}>{t('projects.summary.detail')}</Title>
        <Text size="xs" c="dimmed">
          {t('projects.summary.detailHint')}
        </Text>
      </Group>
      <FilterBar filters={filters} onChange={setFilters} />
      <Group gap="lg">
        <Anchor href={downloadUrl(`${BASE}/export/projects.csv`, { term_id: term.id, ...filters })}>
          {t('projects.summary.downloadProjects')}
        </Anchor>
        <Anchor href={downloadUrl(`${BASE}/export/indicators.csv`, { term_id: term.id })}>
          {t('projects.summary.downloadIndicators')}
        </Anchor>
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && (
        <>
          <Title order={5}>{t('projects.summary.byStatus')}</Title>
          <SimpleGrid cols={{ base: 2, md: 4 }}>
            {EFFECTIVE_STATUSES.map((status) => (
              <StatCard
                key={status}
                label={t(`projects.status.${status}`)}
                value={data.status_counts[status]}
              />
            ))}
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
            <StatCard
              label={t('projects.summary.averageProgress')}
              value={formatPercent(data.average_progress)}
            />
            <StatCard
              label={t('projects.summary.budgetTotal')}
              value={formatMoney(data.budget.total)}
            />
            <StatCard
              label={t('projects.summary.budgetPlanned')}
              value={formatRatio(data.budget.planned_ratio)}
              hint={t('projects.summary.budgetPlannedHint', {
                amount: formatMoney(data.budget.planned),
              })}
            />
            <StatCard
              label={t('projects.summary.budgetExecuted')}
              value={formatRatio(data.budget.executed_ratio)}
              hint={t('projects.summary.budgetExecutedHint', {
                amount: formatMoney(data.budget.executed),
              })}
            />
            <StatCard
              label={t('projects.summary.milestonesCompleted')}
              value={`${data.milestones.completed} / ${data.milestones.total}`}
            />
            <StatCard
              label={t('projects.summary.milestonesInAlert')}
              value={data.milestones.in_alert}
            />
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <CountBarChart title={t('projects.summary.byDepartment')} rows={data.by_department} />
            <CountBarChart title={t('projects.summary.byOwner')} rows={data.by_owner} />
            <CountBarChart title={t('projects.summary.byProgram')} rows={data.by_program} />
            <CountBarChart
              title={t('projects.summary.bySdg')}
              rows={data.by_sdg.map((row) => ({
                name: t('projects.sdgLabel', {
                  number: row.sdg,
                  title: t(`projects.sdg.${row.sdg}`),
                }),
                count: row.count,
              }))}
            />
          </SimpleGrid>

          <ZoneBreakdown
            kind={PROJECTS}
            filters={{ term_id: term.id, ...filters }}
            asOf={boundariesOf(filters.year)}
          />
        </>
      )}
    </Stack>
  )
}
