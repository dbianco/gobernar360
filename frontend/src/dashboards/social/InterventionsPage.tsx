import { Alert, Anchor, Button, Group, Loader, Modal, NativeSelect, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, useInterventions, useInterventionTypes } from './api'
import { InterventionForm } from './InterventionForm'
import { InterventionsTable } from './RecordTables'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Every intervention of a year, with anyone. */
export function InterventionsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const types = useInterventionTypes()
  const [year, setYear] = useState(currentYear)
  const [typeId, setTypeId] = useState('')
  const [q, setQ] = useState('')
  const paging = usePaging('social.interventions')
  const { limit, offset, setOffset } = paging
  const [adding, setAdding] = useState(false)
  const interventions = useInterventions({ q,
    year,
    intervention_type_id: typeId,
    limit,
    offset,
  })
  fitPage(paging, interventions)
  const canEdit = hasLevel(me, 'social', 'editor')
  const label = (key: string) => t(`social.interventions.${key}`)

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end" gap="lg">
          <SearchInput
            value={q}
            onChange={(value) => {
              setQ(value)
              setOffset(0)
            }}
            placeholder={label('searchHint')}
          />
          <YearSelect
            value={year}
            onChange={(value) => {
              setYear(value)
              setOffset(0)
            }}
          />
          <NativeSelect
            label={label('type')}
            value={typeId}
            onChange={(event) => {
              setTypeId(event.currentTarget.value)
              setOffset(0)
            }}
            data={[
              { value: '', label: label('allTypes') },
              ...(types.data ?? []).map((type) => ({ value: type.id, label: type.name })),
            ]}
          />
          <Anchor href={downloadUrl(`${BASE}/export/interventions.csv`, { year })}>
            {label('download')}
          </Anchor>
        </Group>
        {canEdit && <Button onClick={() => setAdding(true)}>{label('add')}</Button>}
      </Group>
      {interventions.isLoading && <Loader aria-label={t('app.loading')} />}
      {interventions.isError && <Alert color="red">{errorMessage(interventions.error)}</Alert>}
      {interventions.data?.total === 0 && <Text c="dimmed">{label('emptyYear')}</Text>}
      {interventions.data && interventions.data.items.length > 0 && (
        <InterventionsTable items={interventions.data.items} showPerson canEdit={canEdit} />
      )}
      {interventions.data && (
        <Pager {...paging.pager(interventions.data.total)} />
      )}
      <Modal opened={adding} onClose={() => setAdding(false)} title={label('add')} size="lg">
        {adding && <InterventionForm onDone={() => setAdding(false)} />}
      </Modal>
    </Stack>
  )
}
