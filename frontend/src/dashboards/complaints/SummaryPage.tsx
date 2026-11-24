import {
  Alert,
  Anchor,
  Group,
  Loader,
  NativeSelect,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl, type Query } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { CountBarChart } from '../../platform/CountBarChart'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate, formatNumber, formatRatio, todayIso } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { HeadlineIndicators } from '../../platform/indicators/HeadlineIndicators'
import { hasLevel } from '../../platform/access'
import { currentYear } from '../../platform/years'
import { BASE, BASE_PATH, KEY, useSummary } from './api'
import { FlowChart } from './FlowChart'
import type { GroupResolution, Summary } from './types'

const PERIODS = ['last12', 'thisYear', 'lastYear'] as const
type PeriodKey = (typeof PERIODS)[number]
const REPEAT_DAYS = [7, 15, 30, 60, 90]

/** The dates a period choice stands for; the API's default is the last twelve months. */
function periodQuery(period: PeriodKey): Query {
  const year = currentYear()
  if (period === 'thisYear') return { from: `${year}-01-01`, to: todayIso() }
  if (period === 'lastYear') return { from: `${year - 1}-01-01`, to: `${year - 1}-12-31` }
  return {}
}

function ResolutionTable(props: { title: string; nameLabel: string; rows: GroupResolution[] }) {
  const { t } = useTranslation()
  const label = (key: string) => t(`complaints.summary.${key}`)
  const help = (key: string) => t(`complaints.help.resolution.${key}`)
  return (
    <Paper withBorder p="md" component="section">
      <Title order={4} mb="xs">
        {props.title}
      </Title>
      {props.rows.length === 0 ? (
        <Text c="dimmed">{t('app.chart.noData')}</Text>
      ) : (
        <Table.ScrollContainer minWidth={560}>
          <Table aria-label={props.title}>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('name')}>{props.nameLabel}</HelpTh>
                <HelpTh help={help('received')} ta="right">
                  {label('received')}
                </HelpTh>
                <HelpTh help={help('resolved')} ta="right">
                  {label('resolved')}
                </HelpTh>
                <HelpTh help={help('onTime')} ta="right">
                  {label('onTimeColumn')}
                </HelpTh>
                <HelpTh help={help('median')} ta="right">
                  {label('medianColumn')}
                </HelpTh>
                <HelpTh help={help('p90')} ta="right">
                  {label('p90Column')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {props.rows.map((row) => (
                <Table.Tr key={row.id}>
                  <Table.Td>{row.name}</Table.Td>
                  <Table.Td ta="right">{row.received}</Table.Td>
                  <Table.Td ta="right">{row.resolved}</Table.Td>
                  <Table.Td ta="right">{formatRatio(row.on_time_ratio)}</Table.Td>
                  <Table.Td ta="right">{formatNumber(row.median_days)}</Table.Td>
                  <Table.Td ta="right">{formatNumber(row.p90_days)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  )
}

function RepeatedTable({ data }: { data: Summary }) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`complaints.summary.${key}`, options)
  const help = (key: string) => t(`complaints.help.repeated.${key}`)
  return (
    <Paper withBorder p="md" component="section" aria-label={label('repeated')}>
      <Title order={4}>{label('repeated')}</Title>
      <Text size="sm" c="dimmed" mb="xs">
        {label('repeatedHint', { count: data.repeat_days })}
      </Text>
      {data.repeated.length === 0 ? (
        <Text c="dimmed">{label('noRepeated')}</Text>
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table aria-label={label('repeated')}>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('type')}>{label('type')}</HelpTh>
                <HelpTh help={help('address')}>{label('address')}</HelpTh>
                <HelpTh help={help('zone')}>{label('zone')}</HelpTh>
                <HelpTh help={help('count')} ta="right">
                  {label('count')}
                </HelpTh>
                <HelpTh help={help('first')}>{label('first')}</HelpTh>
                <HelpTh help={help('last')}>{label('last')}</HelpTh>
                <HelpTh help={help('numbers')}>{label('numbers')}</HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.repeated.map((row) => (
                <Table.Tr key={row.numbers.join()}>
                  <Table.Td>{row.type}</Table.Td>
                  <Table.Td>{row.address}</Table.Td>
                  <Table.Td>{row.zone}</Table.Td>
                  <Table.Td ta="right">{row.count}</Table.Td>
                  <Table.Td>{formatDate(row.first_received)}</Table.Td>
                  <Table.Td>{formatDate(row.last_received)}</Table.Td>
                  <Table.Td>{row.numbers.join(', ')}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  )
}

/** How the municipality answers its residents: the backlog today and the period's record. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [statusYear, setStatusYear] = useState(currentYear)
  const [period, setPeriod] = useState<PeriodKey>('last12')
  const [repeatDays, setRepeatDays] = useState('30')
  const query = periodQuery(period)
  const summary = useSummary({ ...query, repeat_days: repeatDays })
  const data = summary.data
  const label = (key: string, options = {}) => t(`complaints.summary.${key}`, options)
  const isEmpty = data && data.totals.received === 0 && data.backlog.open === 0
  const countLabel = label('countLabel')

  return (
    <Stack>
      <StatusStrip dashboardKey={KEY} year={statusYear} onYearChange={setStatusYear} />
      <HeadlineIndicators dashboardKey={KEY} />
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <NativeSelect
            label={label('period')}
            value={period}
            onChange={(event) => setPeriod(event.currentTarget.value as PeriodKey)}
            data={PERIODS.map((value) => ({ value, label: label(`periods.${value}`) }))}
          />
          <NativeSelect
            label={label('repeatDays')}
            value={repeatDays}
            onChange={(event) => setRepeatDays(event.currentTarget.value)}
            data={REPEAT_DAYS.map((days) => ({
              value: String(days),
              label: label('repeatDaysValue', { count: days }),
            }))}
          />
        </Group>
        <Group gap="lg">
          <Anchor href={downloadUrl(`${BASE}/export/complaints.csv`, query)}>
            {label('downloadComplaints')}
          </Anchor>
          <Anchor href={downloadUrl(`${BASE}/export/areas.csv`, query)}>
            {label('downloadAreas')}
          </Anchor>
        </Group>
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && isEmpty && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, KEY, 'editor') ? (
            <Anchor component={Link} to={`${BASE_PATH}/complaints`}>
              {label('goToComplaints')}
            </Anchor>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && !isEmpty && (
        <>
          <Title order={3}>{label('backlogTitle')}</Title>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <StatCard label={label('open')} value={formatNumber(data.backlog.open)} />
            <StatCard
              label={label('overdue')}
              value={formatNumber(data.backlog.overdue)}
              hint={label('overdueHint')}
            />
            <StatCard
              label={label('atRisk')}
              value={formatNumber(data.backlog.at_risk)}
              hint={label('atRiskHint')}
            />
            <StatCard
              label={label('paused')}
              value={formatNumber(data.backlog.paused)}
              hint={label('pausedHint')}
            />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, md: 3 }}>
            <CountBarChart
              title={label('byState')}
              valueLabel={countLabel}
              rows={data.backlog.by_state.map((row) => ({
                name: t(`complaints.states.${row.state}`),
                count: row.count,
              }))}
            />
            <CountBarChart
              title={label('byStatus')}
              valueLabel={countLabel}
              rows={data.backlog.by_status.map((row) => ({
                name: t(`complaints.statuses.${row.status}`),
                count: row.count,
              }))}
            />
            <CountBarChart
              title={label('ageing')}
              valueLabel={countLabel}
              rows={data.backlog.ageing.map((row) => ({
                name:
                  row.max_days === null
                    ? label('ageOver', { count: row.min_days - 1 })
                    : label('ageRange', { min: row.min_days, max: row.max_days }),
                count: row.count,
              }))}
            />
          </SimpleGrid>

          <Title order={3}>
            {label('periodTitle', {
              from: formatDate(data.period.from),
              to: formatDate(data.period.to),
            })}
          </Title>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <StatCard label={label('received')} value={formatNumber(data.totals.received)} />
            <StatCard label={label('resolved')} value={formatNumber(data.totals.resolved)} />
            <StatCard
              label={label('onTime')}
              value={formatRatio(data.totals.on_time_ratio)}
              hint={label('onTimeHint', {
                count: data.totals.on_time,
                total: data.totals.resolved,
              })}
            />
            <StatCard
              label={label('median')}
              value={formatNumber(data.totals.median_days)}
              hint={label('medianHint', { p90: formatNumber(data.totals.p90_days) })}
            />
          </SimpleGrid>
          <FlowChart rows={data.monthly} />
          <ResolutionTable title={label('byType')} nameLabel={label('type')} rows={data.by_type} />
          <ResolutionTable title={label('byArea')} nameLabel={label('area')} rows={data.by_area} />
          <RepeatedTable data={data} />
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <CountBarChart
              title={label('topZones')}
              valueLabel={countLabel}
              rows={data.top_zones}
            />
            <CountBarChart
              title={label('topTypes')}
              valueLabel={countLabel}
              rows={data.top_types}
            />
          </SimpleGrid>
        </>
      )}
    </Stack>
  )
}
