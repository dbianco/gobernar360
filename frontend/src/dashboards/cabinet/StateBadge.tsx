import { Badge } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import type { State } from './types'

const COLORS: Record<State, string> = {
  overdue: 'red',
  open: 'blue',
  done: 'green',
  dropped: 'gray',
}

export function StateBadge({ state }: { state: State }) {
  const { t } = useTranslation()
  return (
    <Badge color={COLORS[state]} variant="light" tt="none">
      {t(`cabinet.states.${state}`)}
    </Badge>
  )
}
