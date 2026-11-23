import { Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from './authContext'
import { hasLevel } from './access'
import { type AccessLevel } from './types'

/** Renders its children only when the user has the required access to the dashboard. */
export function RequireDashboard(props: {
  dashboardKey: string
  min?: AccessLevel
  children: ReactNode
}) {
  const { t } = useTranslation()
  const { me } = useAuth()

  if (!hasLevel(me, props.dashboardKey, props.min ?? 'viewer')) {
    return (
      <Stack align="center" mt="xl" gap="xs">
        <Title order={3}>{t('dashboards.forbiddenTitle')}</Title>
        <Text c="dimmed">{t('dashboards.forbiddenBody')}</Text>
      </Stack>
    )
  }
  return <>{props.children}</>
}
