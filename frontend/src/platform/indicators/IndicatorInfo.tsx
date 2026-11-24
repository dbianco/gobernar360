import { ActionIcon, Tooltip } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

import { indicatorDescriptionKey } from './format'
import { ICON_BUTTON, ICON_SIZE, ICON_STROKE, TOOLTIP } from './iconStyle'

/**
 * An info icon next to an indicator's name whose tooltip says what the indicator measures.
 * Opens on hover, touch and keyboard focus; shows nothing for an indicator without a text.
 */
export function IndicatorInfo(props: { indicatorKey: string; label: string }) {
  const { t, i18n } = useTranslation()
  const key = indicatorDescriptionKey(props.indicatorKey)
  if (!i18n.exists(key)) return null

  return (
    <Tooltip label={t(key)} {...TOOLTIP}>
      <ActionIcon
        {...ICON_BUTTON}
        aria-label={t('help.about', { column: props.label })}
        // Inside a card that opens its detail: asking what it means is not opening it.
        onClick={(event) => event.stopPropagation()}
      >
        <IconInfoCircle size={ICON_SIZE} stroke={ICON_STROKE} aria-hidden />
      </ActionIcon>
    </Tooltip>
  )
}
