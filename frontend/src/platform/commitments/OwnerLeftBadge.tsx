import { Badge } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import type { State } from './types'

/** Marks what is still open and whose owner is no longer a member; nothing otherwise. */
export function OwnerLeftBadge(props: { commitment: { owner_left: boolean; state: State } }) {
  const { t } = useTranslation()
  const { owner_left: ownerLeft, state } = props.commitment
  if (!ownerLeft || state === 'done' || state === 'dropped') return null
  return (
    <Badge variant="light" color="grape" tt="none" miw="max-content">
      {t('commitments.ownerLeft')}
    </Badge>
  )
}
