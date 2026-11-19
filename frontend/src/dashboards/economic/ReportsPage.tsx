import { Alert, Group, Loader, SimpleGrid, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CountBarChart } from '../../platform/CountBarChart'
import { errorMessage } from '../../platform/errorMessage'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { useReports } from './api'

/** Breakdowns of who is registered and of what was assigned in a year. */
export function ReportsPage() {
  const { t } = useTranslation()
  const [year, setYear] = useState(currentYear)
  const reports = useReports(year)
  const data = reports.data
  const label = (key: string) => t(`economic.reports.${key}`)
  const months = t('app.monthNames', { returnObjects: true }) as string[]
  const named = (rows: { name: string | null; count: number }[], none: string) =>
    rows.map((row) => ({ name: row.name ?? none, count: row.count }))
  // A year without assignments reads better as "no data" than as twelve empty bars.
  const byMonth = data?.assignments_by_month.some((row) => row.count > 0)
    ? data.assignments_by_month.map((row) => ({ name: months[row.month - 1], count: row.count }))
    : []

  return (
    <Stack>
      <Group align="flex-end" gap="lg">
        <YearSelect value={year} onChange={setYear} />
        <Text size="sm" c="dimmed" pb={6}>
          {label('yearHint')}
        </Text>
      </Group>
      {reports.isLoading && <Loader aria-label={t('app.loading')} />}
      {reports.isError && <Alert color="red">{errorMessage(reports.error)}</Alert>}
      {data && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <CountBarChart
            title={label('actorsByType')}
            rows={named(data.actors_by_type, t('economic.actors.noType'))}
            valueLabel={label('actorsCount')}
          />
          <CountBarChart
            title={label('actorsBySector')}
            rows={named(data.actors_by_sector, t('economic.actors.noSector'))}
            valueLabel={label('actorsCount')}
          />
          <CountBarChart
            title={label('peopleByStatus')}
            rows={data.people_by_employment_status.map((row) => ({
              name: t(`economic.employmentStatuses.${row.status}`),
              count: row.count,
            }))}
            valueLabel={label('peopleCount')}
          />
          <CountBarChart
            title={label('assignmentsByCategory')}
            rows={named(data.assignments_by_category, t('app.none'))}
            valueLabel={label('assignmentsCount')}
          />
          <CountBarChart
            title={label('assignmentsByMonth')}
            rows={byMonth}
            valueLabel={label('assignmentsCount')}
          />
        </SimpleGrid>
      )}
    </Stack>
  )
}
