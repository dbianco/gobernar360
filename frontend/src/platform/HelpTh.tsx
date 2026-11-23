import { ActionIcon, Group, Table, Tooltip, VisuallyHidden, type TableThProps } from '@mantine/core'
import { IconInfoCircle } from '@tabler/icons-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * A table header that explains its column: the name plus an info icon whose
 * tooltip opens on hover, touch and keyboard focus. The explanation is also the icon's
 * accessible description, so a screen reader reads it without the tooltip.
 * Every named column of a dashboard table uses it (see tableHeaders.test.ts).
 */
export function HelpTh({
  help,
  children,
  ...props
}: Omit<TableThProps, 'children'> & { help: string; children: string }) {
  const { t } = useTranslation()
  const helpId = useId()
  return (
    <Table.Th {...props}>
      <Group gap={2} wrap="nowrap" display="inline-flex" align="center">
        <span>{children}</span>
        <Tooltip
          label={help}
          multiline
          w={260}
          withArrow
          fw={400}
          ta="left"
          events={{ hover: true, focus: true, touch: true }}
        >
          <ActionIcon
            variant="transparent"
            color="gray"
            size="sm"
            aria-label={t('help.about', { column: children })}
            aria-describedby={helpId}
          >
            <IconInfoCircle size={15} stroke={1.5} aria-hidden />
            <VisuallyHidden id={helpId}>{help}</VisuallyHidden>
          </ActionIcon>
        </Tooltip>
      </Group>
    </Table.Th>
  )
}
