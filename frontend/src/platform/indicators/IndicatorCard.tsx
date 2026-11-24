import {
  ActionIcon,
  Badge,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'
import {
  IconArrowDownRight,
  IconArrowUpRight,
  IconChartLine,
  IconMinus,
  type Icon,
} from '@tabler/icons-react'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  formatAmount,
  formatChange,
  formatIndicator,
  indicatorLabelKey,
  trendOf,
  type Trend,
} from './format'
import { ICON_BUTTON, ICON_SIZE, ICON_STROKE, TOOLTIP } from './iconStyle'
import { IndicatorInfo } from './IndicatorInfo'
import { Sparkline } from './Sparkline'
import type { IndicatorEvolution } from './types'

// The chart library is only needed once a card is opened, so it stays out of the bundle
// the general overview loads with.
const IndicatorDetail = lazy(() =>
  import('./IndicatorDetail').then((module) => ({ default: module.IndicatorDetail })),
)

const TREND_COLOR: Record<Trend, string> = {
  better: 'teal.8',
  worse: 'red.8',
  same: 'dimmed',
  neutral: 'dimmed',
}

/** "+2 against last month", colored by whether that is good news; words carry the meaning. */
function Change(props: {
  change: number | null
  indicator: IndicatorEvolution
  textKey: string
  missingKey: string
}) {
  const { t } = useTranslation()
  if (props.change === null) {
    return (
      <Text size="xs" c="dimmed">
        {t(props.missingKey)}
      </Text>
    )
  }
  const trend = trendOf(props.change, props.indicator.higher_is_better)
  const Arrow: Icon =
    props.change > 0 ? IconArrowUpRight : props.change < 0 ? IconArrowDownRight : IconMinus
  return (
    <Group gap={4} wrap="nowrap">
      <Arrow
        size={14}
        aria-hidden
        color={`var(--mantine-color-${TREND_COLOR[trend].replace('.', '-')})`}
      />
      <Text size="xs" c={TREND_COLOR[trend]} data-trend={trend}>
        {t(props.textKey, { change: formatChange(props.change, props.indicator.unit) })}
      </Text>
    </Group>
  )
}

/** Where the value stands against this year's target: met or missed, and by how much. */
function TargetStatus({ indicator }: { indicator: IndicatorEvolution }) {
  const { t } = useTranslation()
  if (indicator.target === null) {
    return (
      <Text size="xs" c="dimmed">
        {t('indicators.noTarget')}
      </Text>
    )
  }
  const target = formatIndicator(indicator.target, indicator.unit)
  let gap = t('indicators.targetOf', { target })
  if (indicator.value !== null) {
    const difference = indicator.value - indicator.target
    const amount = formatAmount(difference, indicator.unit)
    gap =
      amount === formatAmount(0, indicator.unit)
        ? t('indicators.atTarget', { target })
        : t(difference > 0 ? 'indicators.aboveTarget' : 'indicators.belowTarget', {
            amount,
            target,
          })
  }
  return (
    <Group gap={6} wrap="nowrap" align="center">
      {indicator.on_track !== null && (
        <Badge
          size="sm"
          variant="light"
          color={indicator.on_track ? 'teal' : 'red'}
          style={{ flexShrink: 0 }}
        >
          {t(indicator.on_track ? 'indicators.onTrack' : 'indicators.offTrack')}
        </Badge>
      )}
      <Text size="xs">{gap}</Text>
    </Group>
  )
}

/**
 * A headline indicator: today's value, how it changed since last month and since a year
 * ago, its last twelve months and its target. Opens the detail with the whole series.
 */
export function IndicatorCard({
  indicator,
  label,
  withTarget = true,
}: {
  indicator: IndicatorEvolution
  label: string
  /** False for indicators that cannot have a target, such as combined ones. */
  withTarget?: boolean
}) {
  const { t } = useTranslation()
  const [opened, setOpened] = useState(false)

  return (
    <>
      <Paper
        withBorder
        p="md"
        data-indicator={indicator.key}
        onClick={() => setOpened(true)}
        style={{ cursor: 'pointer' }}
      >
        <Stack gap={6}>
          <Stack gap={0}>
            {/* The name on the left and its two icons together on the right of every card. */}
            <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
              <Text size="sm" c="dimmed" miw={0}>
                {label}
              </Text>
              <Group gap={2} wrap="nowrap" style={{ flexShrink: 0 }}>
                <IndicatorInfo indicatorKey={indicator.key} label={label} />
                <Tooltip label={t('indicators.openHint')} {...TOOLTIP}>
                  <ActionIcon
                    {...ICON_BUTTON}
                    aria-label={t('indicators.open', { name: label })}
                    onClick={(event) => {
                      event.stopPropagation()
                      setOpened(true)
                    }}
                  >
                    <IconChartLine size={ICON_SIZE} stroke={ICON_STROKE} aria-hidden />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
            <Text fz={28} fw={700} lh={1.2}>
              {formatIndicator(indicator.value, indicator.unit)}
            </Text>
          </Stack>
          <Stack gap={2}>
            <Change
              change={indicator.change_previous_month}
              indicator={indicator}
              textKey="indicators.vsPreviousMonth"
              missingKey="indicators.noPreviousMonth"
            />
            <Change
              change={indicator.change_last_year}
              indicator={indicator}
              textKey="indicators.vsLastYear"
              missingKey="indicators.noLastYear"
            />
          </Stack>
          <Sparkline points={indicator.series} label={t('indicators.sparkline', { name: label })} />
          {withTarget && indicator.higher_is_better !== null && (
            <TargetStatus indicator={indicator} />
          )}
        </Stack>
      </Paper>
      {opened && (
        <Suspense fallback={<Loader size="xs" aria-label={t('app.loading')} />}>
          <IndicatorDetail
            indicator={indicator}
            label={label}
            opened={opened}
            onClose={() => setOpened(false)}
          />
        </Suspense>
      )}
    </>
  )
}

export function IndicatorGrid({
  indicators,
  withTargets = true,
}: {
  indicators: IndicatorEvolution[]
  withTargets?: boolean
}) {
  const { t } = useTranslation()
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }}>
      {indicators.map((indicator) => (
        <IndicatorCard
          key={indicator.key}
          indicator={indicator}
          label={t(indicatorLabelKey(indicator.key))}
          withTarget={withTargets}
        />
      ))}
    </SimpleGrid>
  )
}
