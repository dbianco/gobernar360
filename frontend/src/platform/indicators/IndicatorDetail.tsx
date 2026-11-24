import { Badge, Button, Group, Modal, SimpleGrid, Stack, Table, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatChange, formatIndicator } from './format'
import { IndicatorInfo } from './IndicatorInfo'
import type { IndicatorEvolution } from './types'

const MUTED = 'var(--mantine-color-dimmed)'
const INK = 'var(--mantine-color-text)'
const GRID = 'var(--mantine-color-default-border)'
const SERIES = 'var(--mantine-primary-color-filled)'

function Fact(props: { label: string; value: string; detail?: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">
        {props.label}
      </Text>
      <Text fw={600}>{props.value}</Text>
      {props.detail && (
        <Text size="xs" c="dimmed">
          {props.detail}
        </Text>
      )}
    </Stack>
  )
}

/** An indicator's last twelve months with its target line, as a chart or as a table. */
export function IndicatorDetail(props: {
  indicator: IndicatorEvolution
  label: string
  opened: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [asTable, setAsTable] = useState(false)
  const { indicator } = props
  const format = (value: number | null) => formatIndicator(value, indicator.unit)
  const label = (key: string, options = {}) => t(`indicators.detail.${key}`, options)
  const monthName = (year: number, month: number) =>
    t('status.monthYear', { month: t(`status.months.${month}`), year })
  const points = indicator.series.map((point) => ({
    ...point,
    label: `${t(`status.monthsShort.${point.month}`)} ${String(point.year).slice(2)}`,
    name: monthName(point.year, point.month),
  }))
  const hasTarget = indicator.series.some((point) => point.target !== null)
  const hasGaps = indicator.series.some((point) => point.value === null)
  const current = indicator.series[indicator.series.length - 1]
  const direction =
    indicator.higher_is_better === null
      ? 'neutral'
      : indicator.higher_is_better
        ? 'higherIsBetter'
        : 'lowerIsBetter'

  return (
    <Modal.Root opened={props.opened} onClose={props.onClose} size="xl">
      <Modal.Overlay />
      <Modal.Content>
        <Modal.Header>
          {/* The icon sits beside the title, so the dialog is still named by the title alone. */}
          <Group gap={4} wrap="nowrap">
            <Modal.Title>{props.label}</Modal.Title>
            <IndicatorInfo indicatorKey={indicator.key} label={props.label} />
          </Group>
          <Modal.CloseButton />
        </Modal.Header>
        <Modal.Body>
          <Stack>
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <Fact label={label('today')} value={format(indicator.value)} />
              <Fact
                label={label('previousMonth')}
                value={format(indicator.previous_value)}
                detail={
                  indicator.change_previous_month === null
                    ? undefined
                    : label('change', {
                        change: formatChange(indicator.change_previous_month, indicator.unit),
                      })
                }
              />
              <Fact
                label={label('lastYear')}
                value={format(indicator.last_year_value)}
                detail={
                  indicator.change_last_year === null
                    ? undefined
                    : label('change', {
                        change: formatChange(indicator.change_last_year, indicator.unit),
                      })
                }
              />
              <Stack gap={0}>
                <Text size="xs" c="dimmed">
                  {label('target', { year: current?.year })}
                </Text>
                <Text fw={600}>{format(indicator.target)}</Text>
                {indicator.on_track !== null && (
                  <Badge
                    size="sm"
                    variant="light"
                    color={indicator.on_track ? 'teal' : 'red'}
                    w="fit-content"
                  >
                    {t(indicator.on_track ? 'indicators.onTrack' : 'indicators.offTrack')}
                  </Badge>
                )}
              </Stack>
            </SimpleGrid>
            <Text size="xs" c="dimmed">
              {label(direction)}
              {hasGaps &&
                ` ${label(indicator.reconstructible ? 'gaps' : 'gapsNotReconstructible')}`}
            </Text>
            <Group justify="space-between">
              <Text fw={600} size="sm">
                {label('lastMonths')}
              </Text>
              <Button variant="subtle" size="compact-xs" onClick={() => setAsTable(!asTable)}>
                {label(asTable ? 'showChart' : 'showTable')}
              </Button>
            </Group>
            {asTable ? (
              <Table aria-label={label('lastMonths')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{label('month')}</Table.Th>
                    <Table.Th ta="right">{label('value')}</Table.Th>
                    <Table.Th ta="right">{label('targetColumn')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {points.map((point) => (
                    <Table.Tr key={point.name}>
                      <Table.Th scope="row" fw={400}>
                        {point.name}
                      </Table.Th>
                      <Table.Td ta="right">{format(point.value)}</Table.Td>
                      <Table.Td ta="right">{format(point.target)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={points} margin={{ top: 16, right: 16, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke={GRID} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={{ stroke: GRID }}
                    tick={{ fill: MUTED, fontSize: 12 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={72}
                    tick={{ fill: MUTED, fontSize: 12 }}
                    tickFormatter={(value: number) => format(value)}
                  />
                  <Tooltip
                    cursor={{ stroke: GRID }}
                    formatter={(value, name) => [format(Number(value)), name]}
                    labelFormatter={(_, items) => items[0]?.payload?.name ?? ''}
                    contentStyle={{
                      background: 'var(--mantine-color-body)',
                      border: '1px solid var(--mantine-color-default-border)',
                      borderRadius: 4,
                      color: INK,
                    }}
                    labelStyle={{ color: INK }}
                    itemStyle={{ color: INK }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    dataKey="value"
                    name={label('value')}
                    type="linear"
                    stroke={SERIES}
                    strokeWidth={2}
                    dot={{
                      r: 3,
                      fill: SERIES,
                      stroke: 'var(--mantine-color-body)',
                      strokeWidth: 2,
                    }}
                    activeDot={{ r: 5 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                  {hasTarget && (
                    <Line
                      dataKey="target"
                      name={label('targetColumn')}
                      type="stepAfter"
                      stroke={MUTED}
                      strokeWidth={1.5}
                      strokeDasharray="6 4"
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            )}
          </Stack>
        </Modal.Body>
      </Modal.Content>
    </Modal.Root>
  )
}
