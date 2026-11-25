import { Group, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { StatusLight } from '../status/StatusLight'
import type { StatusColor } from '../status/types'
import { CommitmentLines } from './CommitmentLines'
import type { SubjectCommitment } from './types'

/** What was agreed about each month of a status strip, next to the month's light. */
export function MonthCommitments(props: {
  byMonth: Map<number, SubjectCommitment[]>
  colors: Map<number, StatusColor>
}) {
  const { t } = useTranslation()
  const months = [...props.byMonth].sort(([a], [b]) => a - b)

  return (
    <Stack gap="xs" component="section" aria-label={t('commitments.title')}>
      <Text fw={600} size="sm">
        {t('commitments.title')}
      </Text>
      {months.map(([month, commitments]) => {
        const color = props.colors.get(month) ?? null
        const name = t('status.monthLabel', {
          month: t(`status.months.${month}`),
          state: t(`status.states.${color ?? 'none'}`),
        })
        return (
          <Group key={month} role="group" aria-label={name} gap="sm" align="flex-start" wrap="nowrap">
            <StatusLight color={color} size={20} />
            <Stack gap={2} miw={0}>
              <Text size="sm" fw={500} aria-hidden>
                {name}
              </Text>
              <CommitmentLines commitments={commitments} />
            </Stack>
          </Group>
        )
      })}
    </Stack>
  )
}
