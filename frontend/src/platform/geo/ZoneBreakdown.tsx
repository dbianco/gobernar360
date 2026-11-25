import { Alert, Anchor, Group, Loader, NativeSelect, Paper, Stack, Table, Text, Title } from '@mantine/core'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Query } from '../../api/client'
import { activeMembership } from '../access'
import { useAuth } from '../authContext'
import { errorMessage } from '../errorMessage'
import { formatDate } from '../format'
import { HelpTh } from '../HelpTh'
import { breakdownCsv, useBreakdown, useZones } from './api'
import { formatFigure } from './figures'
import { MapLoader } from './MapLoader'
import type { Breakdown, Figures, LocatedKind, Metric } from './types'

const ShadedMap = lazy(() => import('./ShadedMap'))

function FiguresTable(props: { title: string; kind: LocatedKind; data: Breakdown }) {
  const { t } = useTranslation()
  const { data } = props
  const metricText = (metric: Metric, what: 'label' | 'help') =>
    t(`geo.metrics.${props.kind.dashboard}.${props.kind.record}.${metric.key}.${what}`)
  const row = (key: string, name: string, figures: Figures, strong = false) => (
    <Table.Tr key={key} fw={strong ? 700 : undefined}>
      <Table.Td>{name}</Table.Td>
      {data.metrics.map((metric) => (
        <Table.Td key={metric.key} ta="right">
          {formatFigure(figures.values[metric.key], metric, t('geo.breakdown.hidden'))}
        </Table.Td>
      ))}
      {data.grouping && (
        <Table.Td>
          {figures.groups
            .map((group) => `${group.name ?? t(`geo.groupings.${data.grouping}.none`)} ${group.count}`)
            .join(' · ')}
        </Table.Td>
      )}
    </Table.Tr>
  )

  return (
    <Table.ScrollContainer minWidth={360}>
      <Table aria-label={props.title}>
        <Table.Thead>
          <Table.Tr>
            <HelpTh help={t('geo.breakdown.zoneHelp')}>{t('geo.zone')}</HelpTh>
            {data.metrics.map((metric) => (
              <HelpTh key={metric.key} help={metricText(metric, 'help')} ta="right">
                {metricText(metric, 'label')}
              </HelpTh>
            ))}
            {data.grouping && (
              <HelpTh help={t(`geo.groupings.${data.grouping}.help`)}>
                {t(`geo.groupings.${data.grouping}.label`)}
              </HelpTh>
            )}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.zones.map(({ zone, ...figures }) => row(zone.id, zone.name, figures))}
          {row('outside', t('geo.breakdown.outside'), data.outside)}
          {row('unlocated', t('geo.breakdown.unlocated'), data.unlocated)}
          {row('total', t('geo.breakdown.total'), data.total, true)}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}

/**
 * A dashboard's figures by zone, shaded on a map and in a table. Shows nothing until the
 * municipality has zones, except to whoever can draw them.
 */
export function ZoneBreakdown(props: {
  kind: LocatedKind
  filters: Query
  /** Use the boundaries in force at the end of this day; default: today's. */
  asOf?: string
}) {
  const { t } = useTranslation()
  const { me } = useAuth()
  const zones = useZones(props.asOf)
  const breakdown = useBreakdown(props.kind, props.filters, props.asOf)
  const [metricKey, setMetricKey] = useState<string | null>(null)
  const data = breakdown.data
  const title = t(`geo.breakdown.titles.${props.kind.dashboard}.${props.kind.record}`)

  if (zones.isError || breakdown.isError) {
    return <Alert color="red">{errorMessage(zones.error ?? breakdown.error)}</Alert>
  }
  if (!zones.data || !data) return <Loader size="sm" aria-label={t('app.loading')} />
  if (data.zones.length === 0) {
    if (!activeMembership(me)?.is_admin) return null
    return (
      <Text size="sm" c="dimmed">
        {t('geo.breakdown.noZones')}{' '}
        <Anchor component={Link} to="/admin/zones" size="sm">
          {t('geo.breakdown.goToZones')}
        </Anchor>
      </Text>
    )
  }

  const metric = data.metrics.find(({ key }) => key === metricKey) ?? data.metrics[0]
  const metricLabel = (key: string) =>
    t(`geo.metrics.${props.kind.dashboard}.${props.kind.record}.${key}.label`)

  return (
    <Paper withBorder p="md" component="section" aria-label={title}>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-end">
          <div>
            <Title order={4}>{title}</Title>
            <Text size="sm" c="dimmed">
              {data.boundaries_as_of
                ? t('geo.breakdown.boundariesAsOf', { date: formatDate(data.boundaries_as_of) })
                : t('geo.breakdown.boundariesToday')}
            </Text>
          </div>
          <Group align="flex-end">
            {data.metrics.length > 1 && (
              <NativeSelect
                label={t('geo.breakdown.shadeBy')}
                value={metric.key}
                onChange={(event) => setMetricKey(event.currentTarget.value)}
                data={data.metrics.map(({ key }) => ({ value: key, label: metricLabel(key) }))}
              />
            )}
            <Anchor href={breakdownCsv(props.kind, props.filters, props.asOf)}>
              {t('geo.breakdown.download')}
            </Anchor>
          </Group>
        </Group>
        <Suspense fallback={<MapLoader />}>
          <ShadedMap
            label={t('geo.breakdown.mapLabel', { metric: metricLabel(metric.key) })}
            zones={zones.data}
            rows={data.zones}
            metric={metric}
          />
        </Suspense>
        <FiguresTable title={title} kind={props.kind} data={data} />
        {data.threshold !== null && (
          <Text size="sm" c="dimmed">
            {t('geo.breakdown.hiddenNote', { count: data.threshold })}
          </Text>
        )}
      </Stack>
    </Paper>
  )
}
