import { Alert, Button, Group, Loader, Modal, Stack, Text, Title } from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { errorMessage } from '../../platform/errorMessage'
import { useDeliveries, useInterventions } from './api'
import { DeliveryForm } from './DeliveryForm'
import { InterventionForm } from './InterventionForm'
import { DeliveriesTable, InterventionsTable } from './RecordTables'
import type { Page, RecordScope } from './types'

const MOST_RECENT = 200

function Section<T>(props: {
  title: string
  empty: string
  addLabel?: string
  onAdd?: () => void
  query: { data?: Page<T>; isLoading: boolean; isError: boolean; error: unknown }
  children: (items: T[]) => ReactNode
}) {
  const { t } = useTranslation()
  const { data } = props.query
  return (
    <Stack gap="xs" component="section">
      <Group justify="space-between">
        <Title order={4}>{props.title}</Title>
        {props.onAdd && <Button onClick={props.onAdd}>{props.addLabel}</Button>}
      </Group>
      {props.query.isLoading && <Loader aria-label={t('app.loading')} />}
      {props.query.isError && <Alert color="red">{errorMessage(props.query.error)}</Alert>}
      {data?.items.length === 0 && <Text c="dimmed">{props.empty}</Text>}
      {data && data.items.length > 0 && props.children(data.items)}
      {data && data.total > data.items.length && (
        <Text size="sm" c="dimmed">
          {t('social.mostRecent', { count: data.items.length })}
        </Text>
      )}
    </Stack>
  )
}

/**
 * The history of one person or of a whole household: benefits received and
 * interventions, newest first. New records are loaded for a person, so adding
 * is offered only in a person's history.
 */
export function RecordsPanel(props: { scope: RecordScope; canEdit: boolean }) {
  const { t } = useTranslation()
  const personId = 'person_id' in props.scope ? props.scope.person_id : undefined
  const deliveries = useDeliveries({ ...props.scope, limit: MOST_RECENT })
  const interventions = useInterventions({ ...props.scope, limit: MOST_RECENT })
  const [adding, setAdding] = useState<'delivery' | 'intervention' | null>(null)
  const canAdd = props.canEdit && personId !== undefined
  const title = personId ? 'title' : 'householdTitle'

  return (
    <>
      <Section
        title={t(`social.deliveries.${title}`)}
        empty={t('social.deliveries.empty')}
        addLabel={t('social.deliveries.add')}
        onAdd={canAdd ? () => setAdding('delivery') : undefined}
        query={deliveries}
      >
        {(items) => (
          <DeliveriesTable items={items} showPerson={!personId} canEdit={props.canEdit} />
        )}
      </Section>
      <Section
        title={t(`social.interventions.${title}`)}
        empty={t('social.interventions.empty')}
        addLabel={t('social.interventions.add')}
        onAdd={canAdd ? () => setAdding('intervention') : undefined}
        query={interventions}
      >
        {(items) => (
          <InterventionsTable items={items} showPerson={!personId} canEdit={props.canEdit} />
        )}
      </Section>
      <Modal
        opened={adding === 'delivery'}
        onClose={() => setAdding(null)}
        title={t('social.deliveries.add')}
      >
        {adding === 'delivery' && (
          <DeliveryForm personId={personId} onDone={() => setAdding(null)} />
        )}
      </Modal>
      <Modal
        opened={adding === 'intervention'}
        onClose={() => setAdding(null)}
        title={t('social.interventions.add')}
        size="lg"
      >
        {adding === 'intervention' && (
          <InterventionForm personId={personId} onDone={() => setAdding(null)} />
        )}
      </Modal>
    </>
  )
}
