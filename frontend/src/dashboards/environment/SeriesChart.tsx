import { Button, Group, Paper, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatNumber } from '../../platform/format'

export interface SeriesPoint {
  /** Short label for the axis. */
  label: string
  /** Full label for the table and the tooltip. */
  name: string
  value: number | null
}

const MUTED = 'var(--mantine-color-dimmed)'
const INK = 'var(--mantine-color-text)'
const GRID = 'var(--mantine-color-default-border)'
const SERIES = 'var(--mantine-primary-color-filled)'

/**
 * One variable over time. A single series, so one color and no legend: the title names
 * it. Periods without a value leave a gap, and the same data is available as a table.
 */
export function SeriesChart(props: {
  title: string
  unit: string
  points: SeriesPoint[]
  /** Drawn as a dashed reference line when the points are comparable with it. */
  target: number | null
  periodHeader: string
}) {
  const { t } = useTranslation()
  const [asTable, setAsTable] = useState(false)
  const label = (key: string) => t(`environment.tracking.${key}`)
  const hasValues = props.points.some((point) => point.value !== null)
  const withUnit = (value: number | null) =>
    value === null ? formatNumber(null) : `${formatNumber(value, 2)} ${props.unit}`.trim()

  return (
    <Paper withBorder p="md" component="section">
      <Group justify="space-between" mb="xs">
        <Title order={4}>{props.title}</Title>
        {hasValues && (
          <Button variant="subtle" size="compact-xs" onClick={() => setAsTable(!asTable)}>
            {label(asTable ? 'showChart' : 'showTable')}
          </Button>
        )}
      </Group>
      {!hasValues && <Text c="dimmed">{label('noValues')}</Text>}
      {hasValues && asTable && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{props.periodHeader}</Table.Th>
              <Table.Th ta="right">{label('value')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {props.points.map((point) => (
              <Table.Tr key={point.name}>
                <Table.Td>{point.name}</Table.Td>
                <Table.Td ta="right">{withUnit(point.value)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {hasValues && !asTable && (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={props.points} margin={{ top: 16, right: 48, bottom: 0, left: 8 }}>
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
              width={64}
              tick={{ fill: MUTED, fontSize: 12 }}
              tickFormatter={(value: number) => formatNumber(value)}
            />
            <Tooltip
              cursor={{ stroke: GRID }}
              formatter={(value) => [withUnit(Number(value)), label('value')]}
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
            {props.target !== null && (
              <ReferenceLine
                y={props.target}
                stroke={MUTED}
                strokeDasharray="6 4"
                ifOverflow="extendDomain"
                label={{ value: label('target'), position: 'right', fill: MUTED, fontSize: 12 }}
              />
            )}
            <Line
              dataKey="value"
              name={label('value')}
              type="linear"
              stroke={SERIES}
              strokeWidth={2}
              dot={{ r: 4, fill: SERIES, stroke: 'var(--mantine-color-body)', strokeWidth: 2 }}
              activeDot={{ r: 6 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Paper>
  )
}
