import {
  Alert,
  Anchor,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { hasLevel } from '../../platform/access'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, BASE_PATH, useSummary } from './api'

function CountTable(props: {
  title: string
  empty: string
  /** Column headers with their explanation; those after the first `textColumns` hold numbers. */
  columns: { label: string; help: string }[]
  textColumns: number
  rows: (string | number)[][]
}) {
  const align = (index: number) => (index >= props.textColumns ? 'right' : undefined)
  const cell = (value: string | number): ReactNode =>
    typeof value === 'number' ? formatNumber(value) : value

  return (
    <Paper withBorder p="md" component="section">
      <Title order={4} mb="xs">
        {props.title}
      </Title>
      {props.rows.length === 0 ? (
        <Text c="dimmed">{props.empty}</Text>
      ) : (
        <Table aria-label={props.title}>
          <Table.Thead>
            <Table.Tr>
              {props.columns.map((column, index) => (
                <HelpTh key={column.label} help={column.help} ta={align(index)}>
                  {column.label}
                </HelpTh>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {props.rows.map((row) => (
              <Table.Tr key={row.slice(0, props.textColumns).join('/')}>
                {row.map((value, index) => (
                  <Table.Td key={props.columns[index].label} ta={align(index)}>
                    {cell(value)}
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Paper>
  )
}

/** Who is assisted, and what was delivered and done in a year. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [year, setYear] = useState(currentYear)
  const summary = useSummary(year)
  const data = summary.data
  const label = (key: string, options = {}) => t(`social.summary.${key}`, options)
  const column = (key: string) => ({
    label: label(key),
    help: t(`social.help.summaryPage.${key}`),
  })
  const isEmpty =
    data && data.people + data.households + data.deliveries + data.interventions === 0
  const download = (name: string, key: string, query?: { year: number }) => (
    <Anchor href={downloadUrl(`${BASE}/export/${name}.csv`, query)}>{label(key)}</Anchor>
  )

  return (
    <Stack>
      <StatusStrip dashboardKey="social" year={year} />
      <Group align="flex-end" gap="lg">
        <YearSelect value={year} onChange={setYear} />
        {download('people', 'downloadPeople')}
        {download('households', 'downloadHouseholds')}
        {download('deliveries', 'downloadDeliveries', { year })}
        {download('interventions', 'downloadInterventions', { year })}
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && isEmpty && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, 'social', 'admin') ? (
            <>
              <Text c="dimmed">{label('emptyAdminBody')}</Text>
              <Group>
                <Anchor component={Link} to={`${BASE_PATH}/parameters`}>
                  {label('goToParameters')}
                </Anchor>
                <Anchor component={Link} to={`${BASE_PATH}/people`}>
                  {label('goToPeople')}
                </Anchor>
              </Group>
            </>
          ) : hasLevel(me, 'social', 'editor') ? (
            <>
              <Text c="dimmed">{label('emptyEditorBody')}</Text>
              <Anchor component={Link} to={`${BASE_PATH}/people`}>
                {label('goToPeople')}
              </Anchor>
            </>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && !isEmpty && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <StatCard
              label={label('people')}
              value={formatNumber(data.people)}
              hint={label('peopleWithDeliveries', { count: data.people_with_deliveries })}
            />
            <StatCard label={label('households')} value={formatNumber(data.households)} />
            <StatCard
              label={label('deliveries')}
              value={formatNumber(data.deliveries)}
              hint={label('units', { count: data.units })}
            />
            <StatCard
              label={label('interventions')}
              value={formatNumber(data.interventions)}
              hint={label('peopleWithInterventions', { count: data.people_with_interventions })}
            />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <CountTable
              title={label('benefits')}
              empty={label('noDeliveries')}
              columns={['benefit', 'category', 'deliveriesCount', 'unitsCount'].map(column)}
              textColumns={2}
              rows={data.benefits.map((row) => [
                row.benefit,
                row.category,
                row.deliveries,
                row.units,
              ])}
            />
            <CountTable
              title={label('interventionTypes')}
              empty={label('noInterventions')}
              columns={['type', 'count'].map(column)}
              textColumns={1}
              rows={data.intervention_types.map((row) => [row.name ?? t('app.none'), row.count])}
            />
          </SimpleGrid>
        </>
      )}
    </Stack>
  )
}
