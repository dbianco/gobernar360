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
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { hasLevel } from '../../platform/access'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, BASE_PATH, useSummary } from './api'
import type { ToolCount } from './types'

function ToolTable({ title, rows }: { title: string; rows: ToolCount[] }) {
  const { t } = useTranslation()
  const label = (key: string) => t(`economic.summary.${key}`)

  return (
    <Paper withBorder p="md" component="section">
      <Title order={4} mb="xs">
        {title}
      </Title>
      {rows.length === 0 ? (
        <Text c="dimmed">{label('noAssignments')}</Text>
      ) : (
        <Table aria-label={title}>
          <Table.Thead>
            <Table.Tr>
              <HelpTh help={t('economic.help.summaryPage.tool')}>{label('tool')}</HelpTh>
              <HelpTh help={t('economic.help.summaryPage.category')}>{label('category')}</HelpTh>
              <HelpTh help={t('economic.help.summaryPage.count')} ta="right">
                {label('count')}
              </HelpTh>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row) => (
              <Table.Tr key={`${row.category}/${row.tool}`}>
                <Table.Td>{row.tool}</Table.Td>
                <Table.Td>{row.category}</Table.Td>
                <Table.Td ta="right">{formatNumber(row.count)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Paper>
  )
}

/** Who is registered, what the municipality offers and what was assigned in a year. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [year, setYear] = useState(currentYear)
  const summary = useSummary(year)
  const data = summary.data
  const label = (key: string, options = {}) => t(`economic.summary.${key}`, options)
  const isEmpty = data && data.actors.total + data.people.total + data.tools === 0

  return (
    <Stack>
      <StatusStrip dashboardKey="economic" year={year} />
      <Group align="flex-end" gap="lg">
        <YearSelect value={year} onChange={setYear} />
        <Anchor href={downloadUrl(`${BASE}/export/actors.csv`)}>{label('downloadActors')}</Anchor>
        <Anchor href={downloadUrl(`${BASE}/export/people.csv`)}>{label('downloadPeople')}</Anchor>
        <Anchor href={downloadUrl(`${BASE}/export/assignments.csv`, { year })}>
          {label('downloadAssignments')}
        </Anchor>
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && isEmpty && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, 'economic', 'editor') ? (
            <Group>
              <Anchor component={Link} to={`${BASE_PATH}/actors`}>
                {t('economic.actors.create')}
              </Anchor>
              <Anchor component={Link} to={`${BASE_PATH}/people`}>
                {t('economic.people.create')}
              </Anchor>
            </Group>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && !isEmpty && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <StatCard
              label={label('actors')}
              value={formatNumber(data.actors.total)}
              hint={label('withAssignments', { count: data.actors.with_assignments })}
            />
            <StatCard
              label={label('people')}
              value={formatNumber(data.people.total)}
              hint={label('withAssignments', { count: data.people.with_assignments })}
            />
            <StatCard label={label('tools')} value={formatNumber(data.tools)} />
            <StatCard label={label('assignments')} value={formatNumber(data.assignments)} />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <ToolTable title={label('actorTools')} rows={data.actor_tools} />
            <ToolTable title={label('personTools')} rows={data.person_tools} />
          </SimpleGrid>
        </>
      )}
    </Stack>
  )
}
