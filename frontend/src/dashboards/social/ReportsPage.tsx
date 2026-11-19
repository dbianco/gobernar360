import { Alert, Group, Loader, SimpleGrid, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CountBarChart } from '../../platform/CountBarChart'
import { errorMessage } from '../../platform/errorMessage'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { useReports } from './api'
import type { MonthCount, NameCount } from './types'

/** Breakdowns of what was delivered and done in a year, and of who is assisted. */
export function ReportsPage() {
  const { t } = useTranslation()
  const [year, setYear] = useState(currentYear)
  const reports = useReports(year)
  const data = reports.data
  const label = (key: string) => t(`social.reports.${key}`)
  const monthNames = t('app.monthNames', { returnObjects: true }) as string[]
  const named = (rows: NameCount[], none: string) =>
    rows.map((row) => ({ name: row.name ?? none, count: row.count }))
  // A year without records reads better as "no data" than as twelve empty bars.
  const byMonth = (rows: MonthCount[]) =>
    rows.some((row) => row.count > 0)
      ? rows.map((row) => ({ name: monthNames[row.month - 1], count: row.count }))
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
            title={label('deliveriesByCategory')}
            rows={named(data.deliveries_by_category, t('app.none'))}
            valueLabel={label('deliveriesCount')}
          />
          <CountBarChart
            title={label('deliveriesByMonth')}
            rows={byMonth(data.deliveries_by_month)}
            valueLabel={label('deliveriesCount')}
          />
          <CountBarChart
            title={label('interventionsByType')}
            rows={named(data.interventions_by_type, t('app.none'))}
            valueLabel={label('interventionsCount')}
          />
          <CountBarChart
            title={label('interventionsByMonth')}
            rows={byMonth(data.interventions_by_month)}
            valueLabel={label('interventionsCount')}
          />
          <CountBarChart
            title={label('peopleByNeighborhood')}
            rows={named(data.people_by_neighborhood, label('noNeighborhood'))}
            valueLabel={label('peopleCount')}
          />
          <CountBarChart
            title={label('deliveriesByNeighborhood')}
            rows={named(data.deliveries_by_neighborhood, label('noNeighborhood'))}
            valueLabel={label('deliveriesCount')}
          />
        </SimpleGrid>
      )}
    </Stack>
  )
}
