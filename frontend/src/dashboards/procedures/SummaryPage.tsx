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
import { useAuth } from '../../platform/authContext'
import { CountBarChart } from '../../platform/CountBarChart'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber, formatRatio } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { hasLevel } from '../../platform/access'
import { currentYear } from '../../platform/years'
import { BASE, BASE_PATH, KEY, useSummary } from './api'

/** Where the inventory stands: how many procedures, how they are done and what they ask for. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [statusYear, setStatusYear] = useState(currentYear)
  const summary = useSummary()
  const data = summary.data
  const label = (key: string, options = {}) => t(`procedures.summary.${key}`, options)
  const help = (key: string) => t(`procedures.help.summaryPage.${key}`)
  const isEmpty = data && data.procedures + data.requirements + data.sources === 0

  return (
    <Stack>
      {/* The inventory has no year of its own, so the strip chooses one. */}
      <StatusStrip dashboardKey={KEY} year={statusYear} onYearChange={setStatusYear} />
      <Group gap="lg">
        <Anchor href={downloadUrl(`${BASE}/export/procedures.csv`)}>
          {label('downloadProcedures')}
        </Anchor>
        <Anchor href={downloadUrl(`${BASE}/export/procedure-requirements.csv`)}>
          {label('downloadRequirements')}
        </Anchor>
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data && isEmpty && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, KEY, 'editor') ? (
            <Anchor component={Link} to={`${BASE_PATH}/procedures`}>
              {label('goToProcedures')}
            </Anchor>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && !isEmpty && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 5 }}>
            <StatCard label={label('procedures')} value={formatNumber(data.procedures)} />
            <StatCard
              label={label('online')}
              value={formatNumber(data.online)}
              hint={
                data.procedures > 0 &&
                label('onlineHint', { percent: formatRatio(data.online / data.procedures) })
              }
            />
            <StatCard
              label={label('averageRequirements')}
              value={formatNumber(data.average_requirements)}
              hint={label('averageHint')}
            />
            <StatCard label={label('requirements')} value={formatNumber(data.requirements)} />
            <StatCard label={label('sources')} value={formatNumber(data.sources)} />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <CountBarChart
              title={label('byArea')}
              rows={data.by_area}
              valueLabel={label('countLabel')}
            />
            <CountBarChart
              title={label('byChannel')}
              rows={data.by_channel.map((row) => ({
                name: t(`procedures.channels.${row.channel}`),
                count: row.count,
              }))}
              valueLabel={label('countLabel')}
            />
          </SimpleGrid>
          <Paper withBorder p="md" component="section">
            <Title order={4} mb="xs">
              {label('topRequirements')}
            </Title>
            {data.top_requirements.length === 0 ? (
              <Text c="dimmed">{label('noTopRequirements')}</Text>
            ) : (
              <Table aria-label={label('topRequirements')}>
                <Table.Thead>
                  <Table.Tr>
                    <HelpTh help={help('requirement')}>{label('requirement')}</HelpTh>
                    <HelpTh help={help('source')}>{label('source')}</HelpTh>
                    <HelpTh help={help('count')} ta="right">
                      {label('count')}
                    </HelpTh>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.top_requirements.map((row) => (
                    <Table.Tr key={`${row.name}/${row.source}`}>
                      <Table.Td>{row.name}</Table.Td>
                      <Table.Td>{row.source ?? label('noSource')}</Table.Td>
                      <Table.Td ta="right">{row.count}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Paper>
        </>
      )}
    </Stack>
  )
}
