import { Paper, Text } from '@mantine/core'
import type { ReactNode } from 'react'

/** One headline number with its label. */
export function StatCard(props: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Paper withBorder p="md" data-indicator>
      <Text size="sm" c="dimmed">
        {props.label}
      </Text>
      <Text fz={28} fw={700} lh={1.2}>
        {props.value}
      </Text>
      {props.hint && (
        <Text size="xs" c="dimmed">
          {props.hint}
        </Text>
      )}
    </Paper>
  )
}
