import { ActionIcon, Group } from '@mantine/core'
import { IconArrowDown, IconArrowUp } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

/** Moves a row of the agenda up or down. */
export function MoveButtons(props: {
  name: string
  first: boolean
  last: boolean
  onMove: (by: -1 | 1) => void
}) {
  const { t } = useTranslation()
  return (
    <Group gap={2} wrap="nowrap">
      <ActionIcon
        variant="subtle"
        disabled={props.first}
        aria-label={t('cabinet.agenda.moveUp', { name: props.name })}
        onClick={() => props.onMove(-1)}
      >
        <IconArrowUp size={16} aria-hidden />
      </ActionIcon>
      <ActionIcon
        variant="subtle"
        disabled={props.last}
        aria-label={t('cabinet.agenda.moveDown', { name: props.name })}
        onClick={() => props.onMove(1)}
      >
        <IconArrowDown size={16} aria-hidden />
      </ActionIcon>
    </Group>
  )
}
