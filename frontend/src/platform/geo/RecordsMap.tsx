import { Alert, Anchor, CloseButton, Group, Paper, Stack, Text } from '@mantine/core'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Query } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { useFeatures, useZones, type View } from './api'
import { GeoMap } from './GeoMap'
import { type Bounds, boundsOfZones, positionsOf } from './geometry'
import { type DrawnMarker, GoTo, LinesLayer, MarkersLayer, ViewWatcher, ZonesLayer } from './layers'
import type { LocatedKind, MapFeature, Position } from './types'

/** Where a record is clicked: the point itself, or the middle corner of its line. */
function anchorOf(feature: MapFeature): Position {
  const positions = positionsOf(feature.geometry)
  return positions[Math.floor((positions.length - 1) / 2)]
}

/** Records at exactly the same place share a mark, or only the top one could be reached. */
function byPlace(features: MapFeature[]): Map<string, MapFeature[]> {
  const places = new Map<string, MapFeature[]>()
  for (const feature of features) {
    const key = anchorOf(feature).join(',')
    places.set(key, [...(places.get(key) ?? []), feature])
  }
  return places
}

/**
 * A dashboard's records on the map. Only what is inside the visible area is asked for, and
 * close records come grouped until the map is near enough to tell them apart.
 */
export default function RecordsMap(props: { kind: LocatedKind; label: string; filters: Query }) {
  const { t } = useTranslation()
  const zones = useZones()
  const [view, setView] = useState<View | null>(null)
  const [goTo, setGoTo] = useState<Bounds | null>(null)
  const [selected, setSelected] = useState<MapFeature[]>([])
  const found = useFeatures(props.kind, view, props.filters)
  const data = found.data

  const drawnZones = useMemo(
    () => (zones.data ?? []).map(({ id, name, boundary }) => ({ id, boundary, label: name })),
    [zones.data],
  )
  const markers = useMemo((): DrawnMarker[] => {
    if (!data) return []
    const places = [...byPlace(data.features).entries()].map(([key, here]): DrawnMarker => ({
      key,
      position: anchorOf(here[0]),
      name: here.map((feature) => feature.title).join(', '),
      kind: 'pin',
      text: here.length > 1 ? String(here.length) : undefined,
      onClick: () => setSelected(here),
    }))
    const clusters = data.clusters.map((cluster): DrawnMarker => ({
      key: `cluster ${cluster.center.join(',')}`,
      position: cluster.center,
      name: t('geo.map.cluster', { count: cluster.count }),
      kind: 'cluster',
      text: String(cluster.count),
      onClick: () => setGoTo([...cluster.bounds]),
    }))
    return [...clusters, ...places]
  }, [data, t])
  const lines = useMemo(
    () =>
      (data?.features ?? []).map((feature) => ({
        key: feature.id,
        geometry: feature.geometry,
        onClick: () => setSelected([feature]),
      })),
    [data],
  )

  // The map opens on the zones, so it waits to know them.
  if (zones.isLoading) return null
  if (zones.isError) return <Alert color="red">{errorMessage(zones.error)}</Alert>

  const card = selected.length > 0 && (
    <Paper withBorder shadow="md" p="sm">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={4}>
          {selected.map((feature) => (
            <Anchor key={feature.id} component={Link} to={props.kind.path(feature.id)}>
              {feature.title}
            </Anchor>
          ))}
        </Stack>
        <CloseButton
          size="sm"
          aria-label={t('geo.map.closeSelection')}
          onClick={() => setSelected([])}
        />
      </Group>
    </Paper>
  )

  return (
    <Stack gap="xs">
      {found.isError && <Alert color="red">{errorMessage(found.error)}</Alert>}
      <GeoMap
        label={props.label}
        bounds={boundsOfZones(zones.data ?? [])}
        height={520}
        card={card}
      >
        <ZonesLayer zones={drawnZones} />
        <LinesLayer lines={lines} />
        <MarkersLayer markers={markers} />
        <ViewWatcher onChange={setView} />
        <GoTo bounds={goTo} />
      </GeoMap>
      {data && (
        <Text size="sm" c="dimmed" role="status">
          {t('geo.map.inView', { count: data.total })}
          {data.truncated && ` ${t('geo.map.truncated', { count: data.features.length })}`}
        </Text>
      )}
    </Stack>
  )
}
