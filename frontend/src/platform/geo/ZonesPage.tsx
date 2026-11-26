import { Alert, Button, Group, List, Loader, Modal, Stack, Table, Text, Title } from '@mantine/core'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { dashboards } from '../../dashboards/registry'
import { hasLevel } from '../access'
import { useAuth } from '../authContext'
import { useConfirm } from '../confirmContext'
import { errorMessage } from '../errorMessage'
import { formatDate, formatNumber } from '../format'
import { HelpTh } from '../HelpTh'
import { Pager } from '../Pager'
import { useLocalTable } from '../paging'
import { SearchInput } from '../SearchInput'
import { useAction } from '../useAction'
import { retireZone, useOverlaps, useRefreshEverything, useZones, useZoneVersions } from './api'
import { ImportZonesForm } from './ImportZonesForm'
import { MapLoader } from './MapLoader'
import type { Overlap, Zone, ZoneImport, ZoneSaved } from './types'
import { UnzonedPanel } from './UnzonedPanel'
import { ZoneEditor } from './ZoneEditor'

const ZonesMap = lazy(() => import('./ZonesMap'))

/** A moment as the day it falls on where the person is. */
function dayOf(moment: string): string {
  const date = new Date(moment)
  const pad = (value: number) => String(value).padStart(2, '0')
  return formatDate(`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`)
}

function OverlapsAlert({ overlaps }: { overlaps: Overlap[] }) {
  const { t } = useTranslation()
  if (overlaps.length === 0) return null
  return (
    <Alert color="orange" title={t('geo.zones.overlapsTitle')}>
      <Text size="sm">{t('geo.zones.overlapsBody')}</Text>
      <List size="sm" mt="xs">
        {overlaps.map(({ zone, other, area_m2 }) => (
          <List.Item key={`${zone.id} ${other.id}`}>
            {t('geo.zones.overlap', {
              zone: zone.name,
              other: other.name,
              // In hectares from a hundredth of one up.
              area: formatNumber(area_m2 / 10_000, 2),
            })}
          </List.Item>
        ))}
      </List>
    </Alert>
  )
}

function VersionsModal(props: { zone: Zone; onClose: () => void }) {
  const { t } = useTranslation()
  const versions = useZoneVersions(props.zone.id)
  const label = (key: string, options = {}) => t(`geo.zones.${key}`, options)
  const [shown, setShown] = useState<number | null>(null)
  const drawn = useMemo(() => {
    const version = versions.data?.find((candidate) => candidate.version === shown)
    return version ? [{ id: String(version.version), boundary: version.boundary }] : []
  }, [versions.data, shown])

  return (
    <Modal
      opened
      onClose={props.onClose}
      title={label('versionsTitle', { name: props.zone.name })}
      size="lg"
    >
      <Stack gap="sm">
        <Text size="sm">{label('versionsIntro')}</Text>
        {versions.isLoading && <Loader size="sm" aria-label={t('app.loading')} />}
        {versions.isError && <Alert color="red">{errorMessage(versions.error)}</Alert>}
        {versions.data && (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={label('help.version')}>{label('version')}</HelpTh>
                <HelpTh help={label('help.from')}>{label('from')}</HelpTh>
                <HelpTh help={label('help.to')}>{label('to')}</HelpTh>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {versions.data.map((version) => (
                <Table.Tr key={version.version}>
                  <Table.Td>
                    {version.version}
                    {version.source && (
                      <Text size="xs" c="dimmed">
                        {label('official', { source: version.source })}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{dayOf(version.valid_from)}</Table.Td>
                  <Table.Td>
                    {version.valid_to ? dayOf(version.valid_to) : label('current')}
                  </Table.Td>
                  <Table.Td ta="right">
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      aria-label={label('showVersion', { number: version.version })}
                      onClick={() => setShown(version.version)}
                    >
                      {t('app.view')}
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
        {shown !== null && (
          <Suspense fallback={<MapLoader />}>
            <ZonesMap
              // The map opens on the boundary: another one is another map.
              key={shown}
              label={label('versionMapLabel', { name: props.zone.name, number: shown })}
              zones={drawn}
            />
          </Suspense>
        )}
      </Stack>
    </Modal>
  )
}

type Mode = { name: 'list' } | { name: 'new' } | { name: 'edit'; zone: Zone }

/** The municipality's zones: drawing, importing and moving them, and what they miss. */
export function ZonesPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const zones = useZones()
  const overlaps = useOverlaps()
  const action = useAction(['zones'])
  const refresh = useRefreshEverything()
  const confirm = useConfirm()
  const [mode, setMode] = useState<Mode>({ name: 'list' })
  const [importing, setImporting] = useState(false)
  const [history, setHistory] = useState<Zone | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const table = useLocalTable('zones', zones.data, (zone) => zone.name)
  const label = (key: string, options = {}) => t(`geo.zones.${key}`, options)
  const drawn = useMemo(
    () => (zones.data ?? []).map(({ id, name, boundary }) => ({ id, boundary, label: name })),
    [zones.data],
  )
  // Only the dashboards this member can see have anything to review.
  const located = dashboards
    .filter((dashboard) => hasLevel(me, dashboard.key, 'viewer'))
    .flatMap((dashboard) => dashboard.located ?? [])

  function saved({ zone }: ZoneSaved) {
    setNotice(label('saved', { name: zone.name }))
    setMode({ name: 'list' })
  }

  function imported(result: ZoneImport) {
    setNotice(label('import.done', { ...result }))
    setImporting(false)
  }

  async function retire(zone: Zone) {
    const sure = await confirm({
      message: label('retireConfirm', { name: zone.name }),
      confirmLabel: label('retire'),
      danger: true,
    })
    if (!sure) return
    const done = await action.run(async () => {
      await retireZone(zone.id)
      return true
    })
    if (done) {
      setNotice(label('retired', { name: zone.name }))
      await refresh()
    }
  }

  if (mode.name !== 'list' && zones.data) {
    return (
      <ZoneEditor
        zone={mode.name === 'edit' ? mode.zone : undefined}
        zones={zones.data}
        onSaved={saved}
        onCancel={() => setMode({ name: 'list' })}
      />
    )
  }

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>{label('title')}</Title>
          <Text c="dimmed">{label('intro')}</Text>
        </div>
        <Group gap="xs">
          <Button variant="default" onClick={() => setImporting(true)}>
            {label('import.open')}
          </Button>
          <Button disabled={!zones.data} onClick={() => setMode({ name: 'new' })}>
            {label('draw')}
          </Button>
        </Group>
      </Group>
      {notice && (
        <Alert
          color="green"
          withCloseButton
          closeButtonLabel={label('closeNotice')}
          onClose={() => setNotice(null)}
        >
          {notice}
        </Alert>
      )}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {zones.isLoading && <Loader aria-label={t('app.loading')} />}
      {zones.isError && <Alert color="red">{errorMessage(zones.error)}</Alert>}
      {overlaps.isError && <Alert color="red">{errorMessage(overlaps.error)}</Alert>}
      {overlaps.data && <OverlapsAlert overlaps={overlaps.data} />}
      {zones.data?.length === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {zones.data && zones.data.length > 0 && (
        <>
          <Suspense fallback={<MapLoader />}>
            <ZonesMap
              // Opens on all the zones again when one is added, moved or retired.
              key={zones.data.map((zone) => `${zone.id}${zone.version}`).join()}
              label={label('mapLabel')}
              zones={drawn}
            />
          </Suspense>
          <SearchInput
            value={table.query}
            onChange={table.setQuery}
            placeholder={label('searchHint')}
          />
          {table.total === 0 && <Text c="dimmed">{t('app.noMatches')}</Text>}
          {table.rows.length > 0 && (
            <Table.ScrollContainer minWidth={480}>
              <Table highlightOnHover aria-label={label('title')}>
                <Table.Thead>
                  <Table.Tr>
                    <HelpTh help={label('help.name')}>{label('name')}</HelpTh>
                    <HelpTh help={label('help.version')}>{label('version')}</HelpTh>
                    <HelpTh help={label('help.from')}>{label('from')}</HelpTh>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {table.rows.map((zone) => (
                    <Table.Tr key={zone.id}>
                      <Table.Td>
                        {zone.name}
                        {zone.source && (
                          <Text size="xs" c="dimmed">
                            {label('official', { source: zone.source })}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>{zone.version}</Table.Td>
                      <Table.Td>{dayOf(zone.valid_from)}</Table.Td>
                      <Table.Td>
                        <Group gap="xs" justify="flex-end">
                          <Button
                            size="compact-sm"
                            variant="default"
                            aria-label={label('editNamed', { name: zone.name })}
                            onClick={() => setMode({ name: 'edit', zone })}
                          >
                            {t('app.edit')}
                          </Button>
                          <Button
                            size="compact-sm"
                            variant="subtle"
                            aria-label={label('versionsNamed', { name: zone.name })}
                            onClick={() => setHistory(zone)}
                          >
                            {label('versions')}
                          </Button>
                          <Button
                            size="compact-sm"
                            variant="subtle"
                            color="red"
                            aria-label={label('retireNamed', { name: zone.name })}
                            onClick={() => void retire(zone)}
                          >
                            {label('retire')}
                          </Button>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
          <Pager {...table.pager} />
          {located.map((kind) => (
            <UnzonedPanel
              key={`${kind.dashboard}/${kind.record}`}
              kind={kind}
              title={t(`geo.unzoned.titles.${kind.dashboard}.${kind.record}`)}
            />
          ))}
        </>
      )}
      {importing && (
        <ImportZonesForm opened onDone={imported} onClose={() => setImporting(false)} />
      )}
      {history && <VersionsModal zone={history} onClose={() => setHistory(null)} />}
    </Stack>
  )
}
