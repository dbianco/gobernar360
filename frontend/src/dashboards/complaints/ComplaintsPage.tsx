import {
  Alert,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/access'
import { fitPage, usePaging } from '../../platform/paging'
import { BASE_PATH, KEY, useAreas, useComplaints, useTypes, useZones } from './api'
import { ComplaintForm } from './ComplaintForm'
import { ComplaintsTable } from './ComplaintsTable'
import { CLOCK_STATUSES, STATES } from './types'

const NO_FILTERS = { q: '', state: '', type_id: '', area_id: '', zone_id: '', status: '' }

/** Every complaint, newest first, with filters; editors register new ones here. */
export function ComplaintsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const navigate = useNavigate()
  const [filters, setFilters] = useState(NO_FILTERS)
  const paging = usePaging('complaints.complaints')
  const [creating, setCreating] = useState(false)
  const complaints = useComplaints({ ...filters, limit: paging.limit, offset: paging.offset })
  fitPage(paging, complaints)
  const types = useTypes()
  const zones = useZones()
  const areas = useAreas()
  const label = (key: string) => t(`complaints.list.${key}`)
  const filter = (field: keyof typeof filters) => (event: { currentTarget: { value: string } }) => {
    const value = event.currentTarget.value
    setFilters((current) => ({ ...current, [field]: value }))
    // A different search starts again from its first page.
    paging.restart()
  }
  const options = (items: { id: string; name: string }[] | undefined, all: string) => [
    { value: '', label: label(all) },
    ...(items ?? []).map((item) => ({ value: item.id, label: item.name })),
  ]
  const canCreate =
    (types.data ?? []).some((type) => type.is_active) && (zones.data?.length ?? 0) > 0

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
            label={label('state')}
            value={filters.state}
            onChange={filter('state')}
            data={[
              { value: '', label: label('allStates') },
              { value: 'open', label: label('openOnly') },
              ...STATES.map((state) => ({ value: state, label: t(`complaints.states.${state}`) })),
            ]}
          />
          <NativeSelect
            label={label('type')}
            value={filters.type_id}
            onChange={filter('type_id')}
            data={options(types.data, 'allTypes')}
          />
          <NativeSelect
            label={label('area')}
            value={filters.area_id}
            onChange={filter('area_id')}
            data={options(areas.data, 'allAreas')}
          />
          <NativeSelect
            label={label('zone')}
            value={filters.zone_id}
            onChange={filter('zone_id')}
            data={options(zones.data, 'allZones')}
          />
          <NativeSelect
            label={label('status')}
            value={filters.status}
            onChange={filter('status')}
            data={[
              { value: '', label: label('allStatuses') },
              ...CLOCK_STATUSES.map((status) => ({
                value: status,
                label: t(`complaints.statuses.${status}`),
              })),
            ]}
          />
        </Group>
        {hasLevel(me, KEY, 'editor') && canCreate && (
          <Button onClick={() => setCreating(true)}>{label('create')}</Button>
        )}
      </Group>
      {hasLevel(me, KEY, 'editor') && types.data && zones.data && !canCreate && (
        <Text c="dimmed">{label('needsParameters')}</Text>
      )}
      {complaints.isLoading && <Loader aria-label={t('app.loading')} />}
      {complaints.isError && <Alert color="red">{errorMessage(complaints.error)}</Alert>}
      {complaints.data?.total === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {complaints.data && complaints.data.items.length > 0 && (
        <ComplaintsTable complaints={complaints.data.items} showArea label={label('tableLabel')} />
      )}
      {complaints.data && (
        <Pager {...paging.pager(complaints.data.total)} />
      )}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title={label('createTitle')}
        size="lg"
      >
        {creating && (
          <ComplaintForm
            types={types.data ?? []}
            zones={zones.data ?? []}
            onDone={(created) => {
              setCreating(false)
              if (created) navigate(`${BASE_PATH}/complaints/${created.id}`)
            }}
          />
        )}
      </Modal>
    </Stack>
  )
}
