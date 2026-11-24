import { Alert, Group, Stack, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../errorMessage'
import { useEvolution } from './api'
import { IndicatorGrid } from './IndicatorCard'

/**
 * A dashboard's headline indicators with their evolution and targets. Every summary page
 * shows it after its status strip; it needs nothing from the dashboard but its key.
 */
export function HeadlineIndicators(props: { dashboardKey: string }) {
  const { t } = useTranslation()
  const evolution = useEvolution(props.dashboardKey)
  if (evolution.isError) return <Alert color="red">{errorMessage(evolution.error)}</Alert>
  const indicators = evolution.data ?? []
  const hasData = indicators.some(
    (indicator) =>
      indicator.value !== null || indicator.series.some((point) => point.value !== null),
  )
  // Nothing while loading or before the dashboard has any data: its own page says so.
  if (!hasData) return null

  return (
    <Stack gap="xs" component="section" aria-label={t('indicators.title')}>
      <Group gap="sm" align="baseline">
        <Title order={4}>{t('indicators.title')}</Title>
        <Text size="xs" c="dimmed">
          {t('indicators.hint')}
        </Text>
      </Group>
      <IndicatorGrid indicators={indicators} />
    </Stack>
  )
}
