import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { lazy, Suspense, useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useConfirm } from '../confirmContext'
import { errorMessage } from '../errorMessage'
import { useAction } from '../useAction'
import { saveLocation, useLocationOf, useZones } from './api'
import { formatPosition, formatPositions, parsePosition, parsePositions, positionsOf } from './geometry'
import { MapLoader } from './MapLoader'
import type { LocatedKind, LocationGeometry, LocationKind, Position, RecordLocation, Zone } from './types'

const LocationMap = lazy(() => import('./LocationMap'))

/** The location the marks and the kind make, or null while they are not enough. */
function geometryOf(kind: LocationKind, positions: Position[]): LocationGeometry | null {
  if (kind === 'Point') {
    return positions.length === 1 ? { type: 'Point', coordinates: positions[0] } : null
  }
  return positions.length > 1 ? { type: 'LineString', coordinates: positions } : null
}

function LocationForm(props: {
  current: RecordLocation
  zones: Zone[]
  pending: boolean
  onSave: (location: LocationGeometry) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const { current } = props
  const label = (key: string) => t(`geo.location.${key}`)
  const [kind, setKind] = useState<LocationKind>(current.location?.type ?? current.kinds[0])
  const [positions, setPositions] = useState(() => positionsOf(current.location))
  const write = (next: Position[], as: LocationKind) =>
    as === 'Point' ? next.map(formatPosition).join('') : formatPositions(next)
  // What is typed, which may not be coordinates yet; the map only moves when it is.
  const [text, setText] = useState(() => write(positions, kind))
  const typed = kind === 'Point' ? text.trim() === '' || parsePosition(text) : parsePositions(text)
  const location = typed ? geometryOf(kind, positions) : null

  const mark = useCallback(
    (next: Position[]) => {
      setPositions(next)
      setText(write(next, kind))
    },
    [kind],
  )

  function type(value: string) {
    setText(value)
    const point = parsePosition(value)
    const read = kind === 'Point' ? (point ? [point] : []) : parsePositions(value)
    if (read) setPositions(read)
  }

  function changeKind(next: LocationKind) {
    // A line starts where the point was, and the other way round.
    const kept = next === 'Point' ? positions.slice(0, 1) : positions
    setKind(next)
    setPositions(kept)
    setText(write(kept, next))
  }

  const field = {
    label: label(kind === 'Point' ? 'coordinates' : 'lineCoordinates'),
    description: label(kind === 'Point' ? 'coordinatesHint' : 'lineCoordinatesHint'),
    value: text,
    error: typed ? undefined : label('invalidCoordinates'),
    onChange: (event: { currentTarget: { value: string } }) => type(event.currentTarget.value),
  }

  return (
    <Stack gap="sm">
      {current.kinds.length > 1 && (
        <SegmentedControl
          aria-label={label('kind')}
          value={kind}
          onChange={(value) => changeKind(value as LocationKind)}
          data={current.kinds.map((value) => ({ value, label: label(`kinds.${value}`) }))}
          style={{ alignSelf: 'flex-start' }}
        />
      )}
      <Text size="sm">{label(kind === 'Point' ? 'clickPoint' : 'clickLine')}</Text>
      <Suspense fallback={<MapLoader />}>
        <LocationMap zones={props.zones} kind={kind} positions={positions} onChange={mark} />
      </Suspense>
      {kind === 'Point' ? <TextInput {...field} maw={420} /> : <Textarea {...field} autosize minRows={3} maw={420} />}
      <Group gap="xs">
        <Button
          loading={props.pending}
          disabled={!location}
          onClick={() => location && props.onSave(location)}
        >
          {t('app.save')}
        </Button>
        <Button variant="default" onClick={props.onCancel}>
          {t('app.cancel')}
        </Button>
        {kind === 'LineString' && (
          <Button
            variant="subtle"
            disabled={positions.length === 0}
            onClick={() => mark(positions.slice(0, -1))}
          >
            {label('undo')}
          </Button>
        )}
      </Group>
    </Stack>
  )
}

/** Where a record is and the zones that puts it in, with editing for those who load data. */
export function LocationPanel(props: { kind: LocatedKind; recordId: string; canEdit: boolean }) {
  const { t } = useTranslation()
  const located = useLocationOf(props.kind, props.recordId)
  const zones = useZones()
  const action = useAction([props.kind.dashboard, 'overview'])
  const confirm = useConfirm()
  const [editing, setEditing] = useState(false)
  const label = (key: string) => t(`geo.location.${key}`)
  const data = located.data

  async function save(location: LocationGeometry | null) {
    const saved = await action.run(() => saveLocation(props.kind, props.recordId, location))
    if (saved) setEditing(false)
  }

  async function remove() {
    const sure = await confirm({
      message: label('removeConfirm'),
      confirmLabel: label('remove'),
      danger: true,
    })
    if (sure) await save(null)
  }

  return (
    <Paper withBorder p="md" component="section" aria-label={label('title')}>
      <Stack gap="sm">
        <Group justify="space-between">
          <Title order={4}>{label('title')}</Title>
          {props.canEdit && data && !editing && (
            <Group gap="xs">
              <Button size="xs" variant="default" onClick={() => setEditing(true)}>
                {label(data.location ? 'change' : 'set')}
              </Button>
              {data.location && (
                <Button size="xs" variant="subtle" color="red" onClick={() => void remove()}>
                  {label('remove')}
                </Button>
              )}
            </Group>
          )}
        </Group>
        {(located.isLoading || zones.isLoading) && (
          <Loader size="sm" aria-label={t('app.loading')} />
        )}
        {located.isError && <Alert color="red">{errorMessage(located.error)}</Alert>}
        {zones.isError && <Alert color="red">{errorMessage(zones.error)}</Alert>}
        {action.error && <Alert color="red">{action.error}</Alert>}
        {data && zones.data && editing && (
          <LocationForm
            current={data}
            zones={zones.data}
            pending={action.pending}
            onSave={(location) => void save(location)}
            onCancel={() => setEditing(false)}
          />
        )}
        {data && zones.data && !editing && (
          <>
            {!data.location && <Text c="dimmed">{label('none')}</Text>}
            {data.location && (
              <>
                <Group gap="xs">
                  {data.zones.map((zone) => (
                    <Badge key={zone.id} variant="light" tt="none" size="lg">
                      {zone.name}
                    </Badge>
                  ))}
                  {data.zones.length === 0 && (
                    <Badge variant="light" color="orange" tt="none" size="lg">
                      {label('outside')}
                    </Badge>
                  )}
                  {data.location.type === 'Point' && (
                    <Text size="sm" c="dimmed">
                      {formatPosition(data.location.coordinates)}
                    </Text>
                  )}
                </Group>
                <Suspense fallback={<MapLoader height={260} />}>
                  <LocationMap
                    // The map opens on the location: another one is another map.
                    key={JSON.stringify(data.location)}
                    zones={zones.data}
                    kind={data.location.type}
                    positions={positionsOf(data.location)}
                  />
                </Suspense>
              </>
            )}
          </>
        )}
      </Stack>
    </Paper>
  )
}
