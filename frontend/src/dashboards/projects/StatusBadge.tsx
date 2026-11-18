import { Badge } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import type { EffectiveStatus } from './types'

const COLORS: Record<EffectiveStatus, string> = {
  not_started: 'gray',
  in_progress: 'blue',
  delayed: 'red',
  finished: 'green',
}

/** Project status. The label always accompanies the color. */
export function StatusBadge({ status }: { status: EffectiveStatus }) {
  const { t } = useTranslation()
  return (
    <Badge color={COLORS[status]} variant="light">
      {t(`projects.status.${status}`)}
    </Badge>
  )
}
