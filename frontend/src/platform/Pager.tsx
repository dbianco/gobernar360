import { Button, Group, NativeSelect, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

/**
 * "1–50 de 132" with previous and next buttons, and optionally a choice of page size.
 * Hidden while everything fits in one page (the smallest one, when sizes are offered).
 */
export function Pager(props: {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
  /** Page sizes to choose from; the list restarts at its first page on a change. */
  pageSizes?: number[]
  onLimitChange?: (limit: number) => void
}) {
  const { t } = useTranslation()
  const { total, limit, offset, pageSizes } = props
  const smallest = pageSizes ? Math.min(...pageSizes) : limit
  if (total <= smallest && offset === 0) return null

  return (
    <Group justify="flex-end" gap="sm">
      {pageSizes && props.onLimitChange && (
        <NativeSelect
          size="xs"
          aria-label={t('app.pager.pageSize')}
          value={String(limit)}
          data={pageSizes.map((size) => ({
            value: String(size),
            label: t('app.pager.perPage', { count: size }),
          }))}
          onChange={(event) => props.onLimitChange?.(Number(event.currentTarget.value))}
        />
      )}
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
