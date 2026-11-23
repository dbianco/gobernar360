import { Alert, Button, Group, Loader, Modal, Stack, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { HelpTh } from '../../platform/HelpTh'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate } from '../../platform/format'
import { send, useAction, useAssignments } from './api'
import { AssignmentForm, type AssignmentTarget } from './AssignmentForm'
import type { Assignment } from './types'
import { useConfirm } from '../../platform/confirmContext'

const MOST_RECENT = 200

/** The tools one actor or one person received, newest first. */
export function AssignmentsPanel(props: { target: AssignmentTarget; canEdit: boolean }) {
  const { t } = useTranslation()
  const action = useAction()
  const assignments = useAssignments({ ...props.target, limit: MOST_RECENT })
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<Assignment | null>(null)
  const label = (key: string, options = {}) => t(`economic.assignments.${key}`, options)
  const confirm = useConfirm()
  const askDelete = (message: string) =>
    confirm({ message, confirmLabel: t('app.delete'), danger: true })

  async function remove(id: string) {
    if (!(await askDelete(label('deleteConfirm')))) return
    await action.run(() => send('DELETE', `/assignments/${id}`))
  }

  return (
    <Stack gap="xs" component="section">
      <Group justify="space-between">
        <Title order={4}>{label('title')}</Title>
        {props.canEdit && <Button onClick={() => setAdding(true)}>{label('add')}</Button>}
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {assignments.isLoading && <Loader aria-label={t('app.loading')} />}
      {assignments.isError && <Alert color="red">{errorMessage(assignments.error)}</Alert>}
      {assignments.data?.items.length === 0 && <Text c="dimmed">{label('empty')}</Text>}
      {assignments.data && assignments.data.items.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <HelpTh help={t('economic.help.assignmentsPanel.date')}>{label('date')}</HelpTh>
              <HelpTh help={t('economic.help.assignmentsPanel.tool')}>{label('tool')}</HelpTh>
              <HelpTh help={t('economic.help.assignmentsPanel.note')}>{label('note')}</HelpTh>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {assignments.data.items.map((assignment) => (
              <Table.Tr key={assignment.id}>
                <Table.Td>{formatDate(assignment.date)}</Table.Td>
                <Table.Td>{assignment.tool.name}</Table.Td>
                <Table.Td>{assignment.note}</Table.Td>
                <Table.Td ta="right">
                  {props.canEdit && (
                    <Group gap="xs" justify="flex-end" wrap="nowrap">
                      <Button
                        size="compact-xs"
                        variant="default"
                        aria-label={label('editNamed', { name: assignment.tool.name })}
                        onClick={() => setEditing(assignment)}
                      >
                        {t('app.edit')}
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        aria-label={label('deleteNamed', { name: assignment.tool.name })}
                        onClick={() => remove(assignment.id)}
                      >
                        {t('app.delete')}
                      </Button>
                    </Group>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <Modal opened={adding} onClose={() => setAdding(false)} title={label('add')}>
        {adding && <AssignmentForm target={props.target} onDone={() => setAdding(false)} />}
      </Modal>
      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={label('editTitle')}>
        {editing && (
          <AssignmentForm
            target={props.target}
            assignment={editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
