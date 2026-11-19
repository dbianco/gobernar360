import { Button, Group, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/** "1–50 de 132" with previous and next buttons; hidden while everything fits in one page. */
export function Pager(props: {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}) {
  const { t } = useTranslation()
  const { total, limit, offset } = props
  if (total <= limit && offset === 0) return null

  return (
    <Group justify="flex-end" gap="sm">
      <Text size="sm" c="dimmed">
        {t('app.pager.range', {
          from: Math.min(offset + 1, total),
          to: Math.min(offset + limit, total),
          total,
        })}
      </Text>
      <Button
        size="compact-sm"
        variant="default"
        disabled={offset === 0}
        onClick={() => props.onChange(Math.max(0, offset - limit))}
      >
        {t('app.pager.previous')}
      </Button>
      <Button
        size="compact-sm"
        variant="default"
        disabled={offset + limit >= total}
        onClick={() => props.onChange(offset + limit)}
      >
        {t('app.pager.next')}
      </Button>
    </Group>
  )
}
