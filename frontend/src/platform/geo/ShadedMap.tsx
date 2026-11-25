import { Group, Stack, Text } from '@mantine/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { formatFigure } from './figures'
import { GeoMap } from './GeoMap'
import classes from './GeoMap.module.css'
import { boundsOfZones } from './geometry'
import { ZonesLayer } from './layers'
import { shadeOf, shadeSteps } from './shading'
import type { Figures, Metric, Zone, ZoneRef } from './types'

/** Zones shaded by one figure, which is also written on each: colour is never alone. */
export default function ShadedMap(props: {
  label: string
  zones: Zone[]
  rows: (Figures & { zone: ZoneRef })[]
  metric: Metric
  height?: number
}) {
  const { t } = useTranslation()
  const { zones, rows, metric } = props
  const hidden = t('geo.breakdown.hidden')
  const steps = useMemo(
    () => shadeSteps(rows.map((row) => row.values[metric.key])),
    [rows, metric],
  )
  const drawn = useMemo(() => {
    const values = new Map(rows.map((row) => [row.zone.id, row.values[metric.key]]))
    return zones
      .filter((zone) => values.has(zone.id))
      .map((zone) => {
        const value = values.get(zone.id) ?? null
        return {
          id: zone.id,
          boundary: zone.boundary,
          label: `${zone.name}\n${formatFigure(value, metric, hidden)}`,
          fill: shadeOf(value, steps),
          dashed: value === null,
        }
      })
  }, [zones, rows, metric, steps, hidden])

  return (
    <Stack gap="xs">
      <GeoMap label={props.label} bounds={boundsOfZones(zones)} height={props.height}>
        <ZonesLayer zones={drawn} />
      </GeoMap>
      {steps.length > 0 && (
        <Group gap="md" component="ul" aria-label={t('geo.breakdown.legend')} p={0} m={0}>
          {steps.map((step) => (
            <Group key={step.color} gap={6} component="li" style={{ listStyle: 'none' }}>
              <span className={classes.swatch} style={{ background: step.color }} aria-hidden />
              <Text size="sm">
                {step.from === step.to
                  ? formatFigure(step.from, metric, hidden)
                  : t('geo.breakdown.range', {
                      from: formatFigure(step.from, metric, hidden),
                      to: formatFigure(step.to, metric, hidden),
                    })}
              </Text>
            </Group>
          ))}
        </Group>
      )}
    </Stack>
  )
}
