import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatNumber } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { BASE_PATH, KEY, PAGE_SIZE, useAreas, useProcedures } from './api'
import { costText } from './format'
import { ProcedureForm } from './ProcedureForm'
import { CHANNELS } from './types'

/** Searchable inventory of the municipality's procedures. */
export function ProceduresPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const [filters, setFilters] = useState({ q: '', area_id: '', channel: '', active: '' })
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)
  const procedures = useProcedures({ ...filters, limit: PAGE_SIZE, offset })
  const areas = useAreas()
  const label = (key: string, options = {}) => t(`procedures.list.${key}`, options)
  const help = (key: string) => t(`procedures.help.proceduresPage.${key}`)
  const filter = (field: keyof typeof filters) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    setOffset(0)
  }
  const hasAreas = (areas.data?.length ?? 0) > 0

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <TextInput
            label={t('app.search')}
            placeholder={label('searchHint')}
            maxLength={100}
            value={filters.q}
            onChange={filter('q')}
          />
          <NativeSelect
            label={label('area')}
            value={filters.area_id}
            onChange={filter('area_id')}
            data={[
              { value: '', label: label('allAreas') },
              ...(areas.data ?? []).map((area) => ({ value: area.id, label: area.name })),
            ]}
          />
          <NativeSelect
            label={label('channel')}
            value={filters.channel}
            onChange={filter('channel')}
            data={[
              { value: '', label: label('allChannels') },
              ...CHANNELS.map((value) => ({ value, label: t(`procedures.channels.${value}`) })),
            ]}
          />
          <NativeSelect
            label={label('state')}
            value={filters.active}
            onChange={filter('active')}
            data={[
              { value: '', label: label('allStates') },
              { value: 'true', label: label('onlyActive') },
              { value: 'false', label: label('onlyInactive') },
            ]}
          />
        </Group>
        {hasLevel(me, KEY, 'editor') && hasAreas && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {areas.data && !hasAreas && <Text c="dimmed">{label('needsArea')}</Text>}
      {procedures.isLoading && <Loader aria-label={t('app.loading')} />}
      {procedures.isError && <Alert color="red">{errorMessage(procedures.error)}</Alert>}
      {procedures.data?.total === 0 && hasAreas && <Text c="dimmed">{label('empty')}</Text>}
      {procedures.data && procedures.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={help('name')}>{label('name')}</HelpTh>
                <HelpTh help={help('area')}>{label('area')}</HelpTh>
                <HelpTh help={help('channel')}>{label('channel')}</HelpTh>
                <HelpTh help={help('cost')}>{label('cost')}</HelpTh>
                <HelpTh help={help('days')}>{label('days')}</HelpTh>
                <HelpTh help={help('volume')} ta="right">
                  {label('volume')}
                </HelpTh>
                <HelpTh help={help('requirements')} ta="right">
                  {label('requirements')}
                </HelpTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {procedures.data.items.map((procedure) => (
                <Table.Tr key={procedure.id}>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      <Anchor component={Link} to={`${BASE_PATH}/procedures/${procedure.id}`}>
                        {procedure.name}
                      </Anchor>
                      {!procedure.is_active && (
                        <Badge variant="light" color="gray">
                          {label('inactive')}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>{procedure.area.name}</Table.Td>
                  <Table.Td>{t(`procedures.channels.${procedure.channel}`)}</Table.Td>
                  <Table.Td>{costText(procedure, label('free'))}</Table.Td>
                  <Table.Td>
                    {procedure.duration_days === null
                      ? t('app.none')
                      : label('daysValue', { count: procedure.duration_days })}
                  </Table.Td>
                  <Table.Td ta="right">{formatNumber(procedure.annual_volume)}</Table.Td>
                  <Table.Td ta="right">{procedure.requirement_count}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {procedures.data && (
        <Pager
          total={procedures.data.total}
          limit={PAGE_SIZE}
          offset={offset}
          onChange={setOffset}
        />
      )}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={label('createTitle')}
        size="lg"
      >
        {creating && <ProcedureForm areas={areas.data ?? []} onDone={() => setCreating(false)} />}
      </Modal>
    </Stack>
  )
}
