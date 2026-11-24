import { Button, Group, Paper, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { HelpTh } from '../../platform/HelpTh'
import { formatMonth } from './format'

const MUTED = 'var(--mantine-color-dimmed)'
const INK = 'var(--mantine-color-text)'

/** Complaints received against complaints resolved, month by month; also as a table. */
export function FlowChart(props: {
  rows: { month: string; received: number; resolved: number }[]
}) {
  const { t } = useTranslation()
  const [asTable, setAsTable] = useState(false)
  const label = (key: string) => t(`complaints.summary.${key}`)
  const help = (key: string) => t(`complaints.help.flow.${key}`)
  const rows = props.rows.map((row) => ({ ...row, name: formatMonth(row.month, t) }))

  return (
    <Paper withBorder p="md" component="section" aria-label={label('flow')}>
      <Group justify="space-between" mb="xs">
        <Title order={4}>{label('flow')}</Title>
        {rows.length > 0 && (
          <Button variant="subtle" size="compact-xs" onClick={() => setAsTable(!asTable)}>
            {t(asTable ? 'app.chart.showChart' : 'app.chart.showTable')}
          </Button>
        )}
      </Group>
      {rows.length === 0 && <Text c="dimmed">{t('app.chart.noData')}</Text>}
      {rows.length > 0 && asTable && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <HelpTh help={help('month')}>{label('month')}</HelpTh>
              <HelpTh help={help('received')} ta="right">
                {label('flowReceived')}
              </HelpTh>
              <HelpTh help={help('resolved')} ta="right">
                {label('flowResolved')}
              </HelpTh>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row) => (
              <Table.Tr key={row.month}>
                <Table.Td>{row.name}</Table.Td>
                <Table.Td ta="right">{row.received}</Table.Td>
                <Table.Td ta="right">{row.resolved}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {rows.length > 0 && !asTable && (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--mantine-color-default-border)" />
            <XAxis dataKey="name" tick={{ fill: MUTED, fontSize: 12 }} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fill: MUTED, fontSize: 12 }} axisLine={false} />
            <Tooltip
              cursor={{ fill: 'var(--mantine-color-default-hover)' }}
              contentStyle={{
                background: 'var(--mantine-color-body)',
                border: '1px solid var(--mantine-color-default-border)',
                borderRadius: 4,
                color: INK,
              }}
              labelStyle={{ color: INK }}
            />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            <Bar
              dataKey="received"
              name={label('flowReceived')}
              fill="var(--mantine-color-blue-5)"
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
            <Bar
              dataKey="resolved"
              name={label('flowResolved')}
              fill="var(--mantine-color-teal-7)"
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Paper>
  )
}
