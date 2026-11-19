import { Button, Group, Paper, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface CountRow {
  name: string
  count: number
}

const ROW_HEIGHT = 34
const MUTED = 'var(--mantine-color-dimmed)'
const INK = 'var(--mantine-color-text)'

/**
 * A count per category as horizontal bars. One series, so one color and no legend;
 * every bar is labelled with its value and the same data is available as a table.
 */
export function CountBarChart({
  title,
  rows,
  valueLabel,
}: {
  title: string
  rows: CountRow[]
  /** What is being counted, e.g. "Proyectos"; shown in the tooltip. */
  valueLabel: string
}) {
  const { t } = useTranslation()
  const [asTable, setAsTable] = useState(false)
  const longestName = Math.max(0, ...rows.map((row) => row.name.length))

  return (
    <Paper withBorder p="md" component="section">
      <Group justify="space-between" mb="xs">
        <Title order={4}>{title}</Title>
        {rows.length > 0 && (
          <Button variant="subtle" size="compact-xs" onClick={() => setAsTable(!asTable)}>
            {t(asTable ? 'app.chart.showChart' : 'app.chart.showTable')}
          </Button>
        )}
      </Group>
      {rows.length === 0 && <Text c="dimmed">{t('app.chart.noData')}</Text>}
      {rows.length > 0 && asTable && (
        <Table>
          <Table.Tbody>
            {rows.map((row) => (
              <Table.Tr key={row.name}>
                <Table.Td>{row.name}</Table.Td>
                <Table.Td ta="right">{row.count}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {rows.length > 0 && !asTable && (
        <ResponsiveContainer width="100%" height={rows.length * ROW_HEIGHT + 8}>
          <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 32, bottom: 0, left: 0 }}>
            <XAxis type="number" hide allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="name"
              width={Math.min(240, Math.max(60, longestName * 8 + 12))}
              tickLine={false}
              axisLine={false}
              tick={{ fill: MUTED, fontSize: 13 }}
            />
            <Tooltip
              cursor={{ fill: 'var(--mantine-color-default-hover)' }}
              formatter={(value) => [value, valueLabel]}
              contentStyle={{
                background: 'var(--mantine-color-body)',
                border: '1px solid var(--mantine-color-default-border)',
                borderRadius: 4,
                color: INK,
              }}
              labelStyle={{ color: INK }}
              itemStyle={{ color: INK }}
            />
            <Bar
              dataKey="count"
              name={valueLabel}
              fill="var(--mantine-primary-color-filled)"
              radius={[0, 4, 4, 0]}
              barSize={18}
              isAnimationActive={false}
            >
              <LabelList dataKey="count" position="right" fill={INK} fontSize={13} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Paper>
  )
}
