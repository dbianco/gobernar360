import { Button, Group } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/** Edit and delete buttons at the end of a table row. */
export function RowActions(props: {
  editLabel: string
  deleteLabel: string
  /** Text of the delete button; defaults to the generic delete text. */
  deleteText?: string
  onEdit: () => void
  onDelete: () => void
}) {
  const { t } = useTranslation()
  return (
    <Group gap="xs" justify="flex-end" wrap="nowrap">
      <Button size="compact-xs" variant="default" aria-label={props.editLabel} onClick={props.onEdit}>
        {t('app.edit')}
      </Button>
      <Button
        size="compact-xs"
        variant="subtle"
        color="red"
        aria-label={props.deleteLabel}
        onClick={props.onDelete}
      >
        {props.deleteText ?? t('app.delete')}
      </Button>
    </Group>
  )
}
