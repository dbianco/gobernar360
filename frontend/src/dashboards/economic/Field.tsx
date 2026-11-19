import { Text } from '@mantine/core'
import type { ReactNode } from 'react'

/** A labelled value in a record's detail view. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text style={{ whiteSpace: 'pre-wrap' }}>{children || '—'}</Text>
    </div>
  )
}
