import { Center, Paper } from '@mantine/core'
import type { ReactNode } from 'react'

/** The centred card of the pages people see before signing in. */
export function PublicCard({ children }: { children: ReactNode }) {
  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={400}>
        {children}
      </Paper>
    </Center>
  )
}
