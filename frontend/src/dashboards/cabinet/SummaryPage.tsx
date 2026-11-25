import { Alert, Anchor, Group, Loader, Paper, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { STATES } from '../../platform/commitments/types'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate, formatNumber, formatRatio } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { Pager } from '../../platform/Pager'
import { SearchInput } from '../../platform/SearchInput'
import { StatCard } from '../../platform/StatCard'
import { StatusStrip } from '../../platform/status/StatusStrip'
import { hasLevel } from '../../platform/access'
import { useLocalTable } from '../../platform/paging'
import { currentYear } from '../../platform/years'
import { BASE, BASE_PATH, KEY, useSummary } from './api'
import { CommitmentsTable } from './CommitmentsTable'
import type { OwnerRow } from './types'

function OwnersTable({ rows }: { rows: OwnerRow[] }) {
  const { t } = useTranslation()
  const table = useLocalTable('cabinet.owners', rows, (row) => row.owner.full_name)
  const label = (key: string) => t(`cabinet.summary.${key}`)
  const help = (key: string) => t(`cabinet.help.summaryPage.${key}`)

  return (
    <Paper withBorder p="md" component="section">
      <Stack gap="xs">
        <Title order={4}>{label('byOwner')}</Title>
        <SearchInput
          value={table.query}
          onChange={table.setQuery}
          placeholder={label('searchOwner')}
        />
        {table.total === 0 ? (
          <Text c="dimmed">{t('app.noMatches')}</Text>
        ) : (
          <Table.ScrollContainer minWidth={560}>
            <Table aria-label={label('byOwner')}>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={help('owner')}>{label('owner')}</HelpTh>
                  {STATES.map((state) => (
                    <HelpTh key={state} help={help(state)} ta="right">
                      {label(`columns.${state}`)}
                    </HelpTh>
                  ))}
                  <HelpTh help={help('onTime')} ta="right">
                    {label('onTime')}
                  </HelpTh>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {table.rows.map((row) => (
                  <Table.Tr key={row.owner.id}>
                    <Table.Td>{row.owner.full_name}</Table.Td>
                    {STATES.map((state) => (
                      <Table.Td key={state} ta="right">
                        {row.by_state[state]}
                      </Table.Td>
                    ))}
                    <Table.Td ta="right">{formatRatio(row.on_time_share)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        <Pager {...table.pager} />
      </Stack>
    </Paper>
  )
}

/** Whether what the cabinet agrees gets done: by state, by owner, and what drags on. */
export function SummaryPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [statusYear, setStatusYear] = useState(currentYear)
  const summary = useSummary()
  const data = summary.data
  const label = (key: string, options = {}) => t(`cabinet.summary.${key}`, options)

  return (
    <Stack>
      {/* Commitments have no year of their own, so the strip chooses one. */}
      <StatusStrip dashboardKey={KEY} year={statusYear} onYearChange={setStatusYear} />
      <Group gap="lg">
        <Anchor href={downloadUrl(`${BASE}/export/commitments.csv`)}>{label('download')}</Anchor>
        {data?.last_meeting && (
          <Text c="dimmed" size="sm">
            {label('lastMeeting', {
              count: data.closed_meetings,
              date: formatDate(data.last_meeting),
            })}
          </Text>
        )}
      </Group>
      {summary.isLoading && <Loader aria-label={t('app.loading')} />}
      {summary.isError && <Alert color="red">{errorMessage(summary.error)}</Alert>}
      {data?.total === 0 && (
        <Stack gap="xs" mt="lg">
          <Title order={4}>{label('emptyTitle')}</Title>
          {hasLevel(me, KEY, 'editor') ? (
            <Anchor component={Link} to={`${BASE_PATH}/meetings`}>
              {label('goToMeetings')}
            </Anchor>
          ) : (
            <Text c="dimmed">{label('emptyViewerBody')}</Text>
          )}
        </Stack>
      )}
      {data && data.total > 0 && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 2, md: 5 }}>
            {STATES.map((state) => (
              <StatCard
                key={state}
                label={label(`columns.${state}`)}
                value={formatNumber(data.by_state[state])}
              />
            ))}
            <StatCard
              label={label('onTime')}
              value={formatRatio(data.on_time_share)}
              hint={label('onTimeHint')}
            />
          </SimpleGrid>
          <OwnersTable rows={data.by_owner} />
          <Paper withBorder p="md" component="section">
            <Title order={4} mb="xs">
              {label('mostPostponed')}
            </Title>
            {data.most_postponed.length === 0 ? (
              <Text c="dimmed">{label('noPostponed')}</Text>
            ) : (
              <CommitmentsTable commitments={data.most_postponed} label={label('mostPostponed')} />
            )}
          </Paper>
        </>
      )}
    </Stack>
  )
}
