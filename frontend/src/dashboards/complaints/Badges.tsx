import { Badge, Group } from '@mantine/core'
import { IconPlayerPause } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

import type { Clock, ClockStatus, State } from './types'

const STATE_COLORS: Record<State, string> = {
  received: 'blue',
  assigned: 'indigo',
  in_progress: 'cyan',
  waiting: 'grape',
  resolved: 'teal',
  closed: 'gray',
  rejected: 'dark',
  reopened: 'orange',
}

const STATUS_COLORS: Record<ClockStatus, string> = {
  on_time: 'green',
  at_risk: 'yellow',
  overdue: 'red',
}

export function StateBadge({ state }: { state: State }) {
  const { t } = useTranslation()
  return (
    <Badge variant="light" color={STATE_COLORS[state]} style={{ textTransform: 'none' }}>
      {t(`complaints.states.${state}`)}
    </Badge>
  )
}

const SOLVED: State[] = ['resolved', 'closed']

/**
 * On time, at risk or overdue, always with its name, plus a mark while the clock is paused.
 * A solved complaint shows its outcome instead: solved in time or late.
 */
export function ClockBadge({ clock, state }: { clock: Clock; state: State }) {
  const { t } = useTranslation()
  if (!clock.status) return null
  const group = SOLVED.includes(state) ? 'outcomes' : 'statuses'
  return (
    <Group gap={4} wrap="nowrap">
      <Badge
        variant={clock.status === 'overdue' ? 'filled' : 'light'}
        color={STATUS_COLORS[clock.status]}
        style={{ textTransform: 'none' }}
      >
        {t(`complaints.${group}.${clock.status}`)}
      </Badge>
      {clock.paused && (
        <Badge
          variant="outline"
          color="grape"
          leftSection={<IconPlayerPause size={12} aria-hidden />}
          style={{ textTransform: 'none' }}
        >
          {t('complaints.paused')}
        </Badge>
      )}
    </Group>
  )
}
