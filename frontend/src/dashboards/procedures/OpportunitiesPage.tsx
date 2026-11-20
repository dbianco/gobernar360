import { Alert, Anchor, Group, Loader, Stack, Table, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { BASE, useOpportunities } from './api'
import type { Reach } from './types'

function ReachCells({ reach }: { reach: Reach }) {
  return (
    <>
      <Table.Td ta="right">{formatNumber(reach.requirements)}</Table.Td>
      <Table.Td ta="right">{formatNumber(reach.procedures)}</Table.Td>
      <Table.Td ta="right">{formatNumber(reach.annual_volume)}</Table.Td>
    </>
  )
}

/**
 * Which sources already hold what people are asked for, ranked by how much
 * connecting to each would save. The API sends them in that order.
 */
export function OpportunitiesPage() {
  const { t } = useTranslation()
  const opportunities = useOpportunities()
  const data = opportunities.data
  const label = (key: string) => t(`procedures.opportunities.${key}`)
  const help = (key: string) => t(`procedures.help.opportunitiesPage.${key}`)
  const isEmpty = data && data.sources.length === 0 && data.without_source.requirements === 0

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Text c="dimmed" maw={640}>
          {label('intro')}
        </Text>
        <Anchor href={downloadUrl(`${BASE}/export/opportunities.csv`)}>{label('download')}</Anchor>
      </Group>
      {opportunities.isLoading && <Loader aria-label={t('app.loading')} />}
      {opportunities.isError && <Alert color="red">{errorMessage(opportunities.error)}</Alert>}
      {isEmpty && <Text c="dimmed">{label('empty')}</Text>}
      {data && !isEmpty && (
        <Table.ScrollContainer minWidth={720}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('source')}>{label('source')}</HelpTh>
                <HelpTh help={help('level')}>{label('level')}</HelpTh>
                <HelpTh help={help('area')}>{label('area')}</HelpTh>
                <HelpTh help={help('requirements')} ta="right">
                  {label('requirements')}
                </HelpTh>
                <HelpTh help={help('procedures')} ta="right">
                  {label('procedures')}
                </HelpTh>
                <HelpTh help={help('volume')} ta="right">
                  {label('volume')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.sources.map((row) => (
                <Table.Tr key={row.source.id}>
                  <Table.Td>{row.source.name}</Table.Td>
                  <Table.Td>{t(`procedures.levels.${row.source.level}`)}</Table.Td>
                  <Table.Td>{row.source.area?.name ?? t('app.none')}</Table.Td>
                  <ReachCells reach={row} />
                </Table.Tr>
              ))}
              {data.without_source.requirements > 0 && (
                <Table.Tr>
                  <Table.Td c="dimmed">{label('withoutSource')}</Table.Td>
                  <Table.Td c="dimmed">{t('app.none')}</Table.Td>
                  <Table.Td c="dimmed">{t('app.none')}</Table.Td>
                  <ReachCells reach={data.without_source} />
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
