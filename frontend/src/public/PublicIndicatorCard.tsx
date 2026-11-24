import { Badge, Group, Paper, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import {
  formatChange,
  formatIndicator,
  indicatorLabelKey,
  trendOf,
} from '../platform/indicators/format'
import { IndicatorInfo } from '../platform/indicators/IndicatorInfo'
import { Sparkline } from '../platform/indicators/Sparkline'
import type { PublicIndicator } from './types'

const TREND_COLOR = { better: 'teal.8', worse: 'red.8', same: 'dimmed', neutral: 'dimmed' }

/** A published indicator: small counts read "fewer than N", never the number. */
export function PublicIndicatorCard({ indicator }: { indicator: PublicIndicator }) {
  const { t } = useTranslation()
  const label = t(indicatorLabelKey(indicator.key), indicator.name)
  const shown = (value: number | null, below: number | null) =>
    below !== null ? t('public.below', { count: below }) : formatIndicator(value, indicator.unit)
  const change = indicator.change_previous_month
  const trend = trendOf(change, indicator.higher_is_better)

  return (
    <Paper withBorder p="md" data-indicator={indicator.key}>
      <Stack gap={6}>
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
          <Text size="sm" c="dimmed">
            {label}
          </Text>
          <IndicatorInfo indicatorKey={indicator.key} label={label} />
        </Group>
        <Text fz={28} fw={700} lh={1.2}>
          {shown(indicator.value, indicator.value_below)}
        </Text>
        {change !== null && (
          <Text size="xs" c={TREND_COLOR[trend]}>
            {t('indicators.vsPreviousMonth', { change: formatChange(change, indicator.unit) })}
          </Text>
        )}
        <Sparkline
          points={indicator.series}
          label={t('indicators.sparkline', { name: label })}
        />
        {indicator.target !== null && (
          <Group gap={6}>
            {indicator.on_track !== null && (
              <Badge size="sm" variant="light" color={indicator.on_track ? 'teal' : 'red'}>
                {t(indicator.on_track ? 'indicators.onTrack' : 'indicators.offTrack')}
              </Badge>
            )}
            <Text size="xs">
              {t('indicators.targetOf', {
                target: formatIndicator(indicator.target, indicator.unit),
              })}
            </Text>
          </Group>
        )}
      </Stack>
    </Paper>
  )
}
