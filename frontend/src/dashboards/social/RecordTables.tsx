import { Alert, Anchor, Badge, Button, Group, Modal, Stack, Table, Text } from '@mantine/core'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { HelpTh } from '../../platform/HelpTh'
import { formatDate } from '../../platform/format'
import { BASE_PATH, send, useAction } from './api'
import { DeliveryForm } from './DeliveryForm'
import { InterventionForm } from './InterventionForm'
import type { Delivery, Intervention, PersonRef } from './types'

function PersonLink({ person }: { person: PersonRef }) {
  return (
    <Anchor component={Link} to={`${BASE_PATH}/people/${person.id}`}>
      {person.full_name}
    </Anchor>
  )
}

function RowActions(props: {
  editLabel: string
  deleteLabel: string
  onEdit: () => void
  onDelete: () => void
}) {
  const { t } = useTranslation()
  return (
    <Group gap="xs" justify="flex-end" wrap="nowrap">
      <Button size="compact-xs" variant="default" aria-label={props.editLabel} onClick={props.onEdit}>
        {t('app.edit')}
      </Button>
      <Button
        size="compact-xs"
        variant="subtle"
        color="red"
        aria-label={props.deleteLabel}
        onClick={props.onDelete}
      >
        {t('app.delete')}
      </Button>
    </Group>
  )
}

function RecordTable(props: { minWidth: number; head: ReactNode; children: ReactNode }) {
  return (
    <Table.ScrollContainer minWidth={props.minWidth}>
      <Table>
        <Table.Thead>
          <Table.Tr>{props.head}</Table.Tr>
        </Table.Thead>
        <Table.Tbody>{props.children}</Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}

/** Benefits delivered, with the controls to correct or delete each one. */
export function DeliveriesTable(props: {
  items: Delivery[]
  /** Whether the rows belong to several people, so each one names its person. */
  showPerson: boolean
  canEdit: boolean
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [editing, setEditing] = useState<Delivery | null>(null)
  const label = (key: string, options = {}) => t(`social.deliveries.${key}`, options)

  function remove(id: string) {
    if (!window.confirm(label('deleteConfirm'))) return
    void action.run(() => send('DELETE', `/deliveries/${id}`))
  }

  return (
    <Stack gap="xs">
      {action.error && <Alert color="red">{action.error}</Alert>}
      <RecordTable
        minWidth={props.showPerson ? 720 : 560}
        head={
          <>
            <HelpTh help={t('social.help.deliveries.date')}>{label('date')}</HelpTh>
            {props.showPerson && (
              <HelpTh help={t('social.help.deliveries.person')}>{label('person')}</HelpTh>
            )}
            <HelpTh help={t('social.help.deliveries.benefit')}>{label('benefit')}</HelpTh>
            <HelpTh help={t('social.help.deliveries.category')}>{label('category')}</HelpTh>
            <HelpTh help={t('social.help.deliveries.quantity')} ta="right">
              {label('quantity')}
            </HelpTh>
            <HelpTh help={t('social.help.deliveries.note')}>{label('note')}</HelpTh>
            <Table.Th />
          </>
        }
      >
        {props.items.map((delivery) => (
          <Table.Tr key={delivery.id}>
            <Table.Td>{formatDate(delivery.date)}</Table.Td>
            {props.showPerson && (
              <Table.Td>
                <PersonLink person={delivery.person} />
              </Table.Td>
            )}
            <Table.Td>{delivery.benefit.name}</Table.Td>
            <Table.Td>{delivery.benefit.category.name}</Table.Td>
            <Table.Td ta="right">{delivery.quantity}</Table.Td>
            <Table.Td style={{ whiteSpace: 'pre-wrap' }}>{delivery.note}</Table.Td>
            <Table.Td>
              {props.canEdit && (
                <RowActions
                  editLabel={label('editNamed', { name: delivery.benefit.name })}
                  deleteLabel={label('deleteNamed', { name: delivery.benefit.name })}
                  onEdit={() => setEditing(delivery)}
                  onDelete={() => remove(delivery.id)}
                />
              )}
            </Table.Td>
          </Table.Tr>
        ))}
      </RecordTable>
      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={label('editTitle')}>
        {editing && <DeliveryForm delivery={editing} onDone={() => setEditing(null)} />}
      </Modal>
    </Stack>
  )
}

/**
 * Interventions, with the controls to correct or delete each one. A description
 * the server withheld (null) is shown as reserved rather than as empty.
 */
export function InterventionsTable(props: {
  items: Intervention[]
  showPerson: boolean
  canEdit: boolean
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [editing, setEditing] = useState<Intervention | null>(null)
  const label = (key: string, options = {}) => t(`social.interventions.${key}`, options)
  const withheld = props.items.some((intervention) => intervention.description === null)

  function remove(id: string) {
    if (!window.confirm(label('deleteConfirm'))) return
    void action.run(() => send('DELETE', `/interventions/${id}`))
  }

  return (
    <Stack gap="xs">
      {action.error && <Alert color="red">{action.error}</Alert>}
      {withheld && (
        <Text size="sm" c="dimmed">
          {t('social.reservedHint')}
        </Text>
      )}
      <RecordTable
        minWidth={props.showPerson ? 760 : 600}
        head={
          <>
            <HelpTh help={t('social.help.interventions.date')}>{label('date')}</HelpTh>
            {props.showPerson && (
              <HelpTh help={t('social.help.interventions.person')}>{label('person')}</HelpTh>
            )}
            <HelpTh help={t('social.help.interventions.type')}>{label('type')}</HelpTh>
            <HelpTh help={t('social.help.interventions.performedBy')}>
              {label('performedBy')}
            </HelpTh>
            <HelpTh help={t('social.help.interventions.description')}>
              {label('description')}
            </HelpTh>
            <Table.Th />
          </>
        }
      >
        {props.items.map((intervention) => (
          <Table.Tr key={intervention.id}>
            <Table.Td>{formatDate(intervention.date)}</Table.Td>
            {props.showPerson && (
              <Table.Td>
                <PersonLink person={intervention.person} />
              </Table.Td>
            )}
            <Table.Td>{intervention.intervention_type.name}</Table.Td>
            <Table.Td>{intervention.performed_by || t('app.none')}</Table.Td>
            <Table.Td style={{ whiteSpace: 'pre-wrap' }}>
              {intervention.description === null ? (
                <Badge variant="light" color="gray">
                  {t('social.reserved')}
                </Badge>
              ) : (
                intervention.description
              )}
            </Table.Td>
            <Table.Td>
              {props.canEdit && (
                <RowActions
                  editLabel={label('editNamed', { name: intervention.intervention_type.name })}
                  deleteLabel={label('deleteNamed', { name: intervention.intervention_type.name })}
                  onEdit={() => setEditing(intervention)}
                  onDelete={() => remove(intervention.id)}
                />
              )}
            </Table.Td>
          </Table.Tr>
        ))}
      </RecordTable>
      <Modal
        opened={editing !== null}
        onClose={() => setEditing(null)}
        title={label('editTitle')}
        size="lg"
      >
        {editing && <InterventionForm intervention={editing} onDone={() => setEditing(null)} />}
      </Modal>
    </Stack>
  )
}
