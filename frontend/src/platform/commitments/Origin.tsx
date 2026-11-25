import { Anchor, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { dashboardLabelKey } from '../../dashboards/registry'
import type { Commitment } from './types'

/** Where a commitment comes from: its meeting for whoever may open it, or that it is informal. */
export function Origin({ commitment }: { commitment: Commitment }) {
  const { t } = useTranslation()
  const { origin, source } = commitment
  if (origin) {
    return (
      <Anchor component={Link} to={origin.path} size="sm">
        {origin.label}
      </Anchor>
    )
  }
  const labelKey = source ? dashboardLabelKey(source) : undefined
  return (
    <Text size="sm">
      {source ? (labelKey ? t(labelKey) : source) : t('commitments.informal')}
    </Text>
  )
}
