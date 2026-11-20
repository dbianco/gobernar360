import { Group, Paper, Stack, Text } from '@mantine/core'
import type { Icon } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

import { StatusLight } from './StatusLight'
import type { DatedStatus } from './types'

/**
 * A dashboard's light on the general overview: its icon on the color of the latest
 * month that has one, and the months set shortly before it.
 * `status` comes newest first.
 */
export function StatusCard(props: { name: string; icon: Icon; status: DatedStatus[] }) {
  const { t } = useTranslation()
  const [latest, ...earlier] = props.status
  const monthName = (month: number) => t(`status.months.${month}`)

  return (
    <Paper withBorder p="md" role="group" aria-label={props.name}>
      <Group wrap="nowrap" align="center">
        <StatusLight color={latest?.color ?? null} size={72} icon={props.icon} />
        <Stack gap={4} miw={0}>
          <Text fw={600} lh={1.2}>
            {props.name}
          </Text>
          <Text size="sm">{t(`status.states.${latest?.color ?? 'none'}`)}</Text>
          {latest && (
            <Text size="xs" c="dimmed">
              {t('status.monthYear', {
                month: monthName(latest.month),
                year: latest.year,
              })}
            </Text>
          )}
          {earlier.length > 0 && (
            <Group gap={6} mt={4}>
              {earlier.toReversed().map((light) => {
                const label = t('status.monthLabel', {
                  month: monthName(light.month),
                  state: t(`status.states.${light.color}`),
                })
                return (
                  <Stack
                    key={`${light.year}-${light.month}`}
                    gap={0}
                    align="center"
                    role="img"
                    aria-label={label}
                    title={label}
                  >
                    <StatusLight color={light.color} size={20} />
                    <Text fz={10} c="dimmed" aria-hidden>
                      {t(`status.monthsShort.${light.month}`)}
                    </Text>
                  </Stack>
                )
              })}
            </Group>
          )}
        </Stack>
      </Group>
    </Paper>
  )
}
