import { Alert, Button, Group, Paper, Stack, Text, Textarea, TextInput, Title } from '@mantine/core'
import { lazy, Suspense, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { createZone, updateZone, useRefreshEverything } from './api'
import { editableCorners, formatPositions, parsePositions, polygonOf } from './geometry'
import { MapLoader } from './MapLoader'
import type { Position, Zone, ZoneSaved } from './types'

const ZoneDrawingMap = lazy(() => import('./ZoneDrawingMap'))

const MIN_CORNERS = 3

/** Draws a new zone, or renames one and moves its boundary. */
export function ZoneEditor(props: {
  /** The zone being changed; without it, a new one. */
  zone?: Zone
  zones: Zone[]
  onSaved: (saved: ZoneSaved) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const { zone } = props
  const label = (key: string) => t(`geo.zones.${key}`)
  const refresh = useRefreshEverything()
  // Null: a boundary with parts or holes, which only a file can change.
  const [original] = useState(() => (zone ? editableCorners(zone.boundary) : []))
  const [name, setName] = useState(zone?.name ?? '')
  const [corners, setCorners] = useState<Position[]>(original ?? [])
  const [past, setPast] = useState<Position[][]>([])
  const [text, setText] = useState(() => formatPositions(corners))
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [others] = useState(() => props.zones.filter((other) => other.id !== zone?.id))
  const typed = parsePositions(text)
  const drawn = corners.length >= MIN_CORNERS && typed !== null
  const moved = formatPositions(corners) !== formatPositions(original ?? [])
  const ready = name.trim() !== '' && (original === null || drawn)

  function change(next: Position[]) {
    setPast([...past, corners])
    setCorners(next)
    setText(formatPositions(next))
  }

  function undo() {
    const before = past[past.length - 1]
    setPast(past.slice(0, -1))
    setCorners(before)
    setText(formatPositions(before))
  }

  function type(value: string) {
    setText(value)
    const read = parsePositions(value)
    if (read) {
      setPast([...past, corners])
      setCorners(read)
    }
  }

  async function save() {
    setPending(true)
    setError(null)
    try {
      const boundary = polygonOf(corners)
      const saved = zone
        ? await updateZone(zone.id, {
            name: name.trim(),
            base_version: zone.version,
            ...(original !== null && moved ? { boundary } : {}),
          })
        : await createZone(name.trim(), boundary)
      await refresh()
      props.onSaved(saved)
    } catch (caught) {
      setError(errorMessage(caught))
      // Somebody else's boundary is now the zone's: show it in the list.
      if (caught instanceof ApiError && caught.code === 'zone_changed') await refresh()
    } finally {
      setPending(false)
    }
  }

  return (
    <Paper withBorder p="md" component="section" aria-label={label(zone ? 'editTitle' : 'newTitle')}>
      <Stack gap="sm">
        <Title order={4}>{label(zone ? 'editTitle' : 'newTitle')}</Title>
        {error && <Alert color="red">{error}</Alert>}
        <TextInput
          label={label('name')}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          maxLength={200}
          maw={420}
          required
        />
        {original === null ? (
          <Alert color="blue">{label('notEditable')}</Alert>
        ) : (
          <>
            <Text size="sm">{label('drawHint')}</Text>
            <Suspense fallback={<MapLoader height={520} />}>
              <ZoneDrawingMap others={others} corners={corners} onChange={change} />
            </Suspense>
            <Textarea
              label={label('corners')}
              description={label('cornersHint')}
              value={text}
              onChange={(event) => type(event.currentTarget.value)}
              error={typed ? undefined : t('geo.location.invalidCoordinates')}
              autosize
              minRows={3}
              maxRows={10}
              maw={420}
            />
            {zone && moved && <Text size="sm">{label('versionNote')}</Text>}
          </>
        )}
        <Group gap="xs">
          <Button loading={pending} disabled={!ready} onClick={() => void save()}>
            {t('app.save')}
          </Button>
          <Button variant="default" onClick={props.onCancel}>
            {t('app.cancel')}
          </Button>
          {original !== null && (
            <>
              <Button variant="subtle" disabled={past.length === 0} onClick={undo}>
                {label('undo')}
              </Button>
              <Button
                variant="subtle"
                color="red"
                disabled={corners.length === 0}
                onClick={() => change([])}
              >
                {label('clear')}
              </Button>
            </>
          )}
        </Group>
      </Stack>
    </Paper>
  )
}
