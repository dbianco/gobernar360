import { Badge } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/** How many times a commitment was postponed; nothing when it never was. */
export function PostponedBadge({ times }: { times: number }) {
  const { t } = useTranslation()
  if (times === 0) return null
  return (
    <Badge variant="light" color="orange" tt="none">
      {t('commitments.postponed', { count: times })}
    </Badge>
  )
}
