import { Badge } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/** Marks a procedure that can be done entirely from home; pointing at it says why. */
export function DigitalBadge() {
  const { t } = useTranslation()
  return (
    <Badge variant="light" color="teal" tt="none" miw="max-content" title={t('procedures.digitalRule')}>
      {t('procedures.digital')}
    </Badge>
  )
}
