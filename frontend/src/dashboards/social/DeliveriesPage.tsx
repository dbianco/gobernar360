import { Alert, Anchor, Button, Group, Loader, Modal, NativeSelect, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/access'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, useBenefits, useDeliveries } from './api'
import { DeliveryForm } from './DeliveryForm'
import { DeliveriesTable } from './RecordTables'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'

/** Every benefit delivered in a year, to anyone. */
export function DeliveriesPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const benefits = useBenefits()
  const [year, setYear] = useState(currentYear)
  const [benefitId, setBenefitId] = useState('')
  const [q, setQ] = useState('')
  const paging = usePaging('social.deliveries')
  const { limit, offset, setOffset } = paging
  const [adding, setAdding] = useState(false)
  const deliveries = useDeliveries({ q, year, benefit_id: benefitId, limit, offset })
  fitPage(paging, deliveries)
  const canEdit = hasLevel(me, 'social', 'editor')
  const label = (key: string) => t(`social.deliveries.${key}`)

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
            label={label('benefit')}
            value={benefitId}
            onChange={(event) => {
              setBenefitId(event.currentTarget.value)
              setOffset(0)
            }}
            data={[
              { value: '', label: label('allBenefits') },
              ...(benefits.data ?? []).map((benefit) => ({
                value: benefit.id,
                label: benefit.name,
              })),
            ]}
          />
          <Anchor href={downloadUrl(`${BASE}/export/deliveries.csv`, { year })}>
            {label('download')}
          </Anchor>
        </Group>
        {canEdit && <Button onClick={() => setAdding(true)}>{label('add')}</Button>}
      </Group>
      {deliveries.isLoading && <Loader aria-label={t('app.loading')} />}
      {deliveries.isError && <Alert color="red">{errorMessage(deliveries.error)}</Alert>}
      {deliveries.data?.total === 0 && <Text c="dimmed">{label('emptyYear')}</Text>}
      {deliveries.data && deliveries.data.items.length > 0 && (
        <DeliveriesTable items={deliveries.data.items} showPerson canEdit={canEdit} />
      )}
      {deliveries.data && (
        <Pager {...paging.pager(deliveries.data.total)} />
      )}
      <Modal opened={adding} onClose={() => setAdding(false)} title={label('add')}>
        {adding && <DeliveryForm onDone={() => setAdding(false)} />}
      </Modal>
    </Stack>
  )
}
