import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { HelpTh } from '../../platform/HelpTh'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate } from '../../platform/format'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, BASE_PATH, send, useAction, useAssignments, useTools } from './api'
import { AssignmentForm } from './AssignmentForm'
import type { Assignment } from './types'
import { fitPage, usePaging } from '../../platform/paging'
import { SearchInput } from '../../platform/SearchInput'
import { useConfirm } from '../../platform/confirmContext'

const recipientOf = (assignment: Assignment) =>
  assignment.actor
    ? {
        kind: 'actor',
        name: assignment.actor.name,
        to: `${BASE_PATH}/actors/${assignment.actor.id}`,
      }
    : {
        kind: 'person',
        name: assignment.person?.full_name ?? '',
        to: `${BASE_PATH}/people/${assignment.person?.id}`,
      }

/** Every tool assigned in a year. New assignments are loaded from an actor or a person. */
export function AssignmentsPage() {
  const { t } = useTranslation()
  const { me } = useAuth()
  const action = useAction()
  const tools = useTools()
  const [year, setYear] = useState(currentYear)
  const [toolId, setToolId] = useState('')
  const [q, setQ] = useState('')
  const paging = usePaging('economic.assignments')
  const { limit, offset, setOffset } = paging
  const [editing, setEditing] = useState<Assignment | null>(null)
  const assignments = useAssignments({ q, year, tool_id: toolId, limit, offset })
  fitPage(paging, assignments)
  const canEdit = hasLevel(me, 'economic', 'editor')
  const label = (key: string, options = {}) => t(`economic.assignments.${key}`, options)
  const confirm = useConfirm()
  const askDelete = (message: string) =>
    confirm({ message, confirmLabel: t('app.delete'), danger: true })

  async function remove(id: string) {
    if (!(await askDelete(label('deleteConfirm')))) return
    await action.run(() => send('DELETE', `/assignments/${id}`))
  }

  return (
    <Stack>
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
          label={label('tool')}
          value={toolId}
          onChange={(event) => {
            setToolId(event.currentTarget.value)
            setOffset(0)
          }}
          data={[
            { value: '', label: label('allTools') },
            ...(tools.data ?? []).map((tool) => ({ value: tool.id, label: tool.name })),
          ]}
        />
        <Anchor href={downloadUrl(`${BASE}/export/assignments.csv`, { year })}>
          {label('download')}
        </Anchor>
      </Group>
      {action.error && <Alert color="red">{action.error}</Alert>}
      {assignments.isLoading && <Loader aria-label={t('app.loading')} />}
      {assignments.isError && <Alert color="red">{errorMessage(assignments.error)}</Alert>}
      {assignments.data?.total === 0 && <Text c="dimmed">{label('emptyYear')}</Text>}
      {assignments.data && assignments.data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <HelpTh help={t('economic.help.assignmentsPage.date')}>{label('date')}</HelpTh>
                <HelpTh help={t('economic.help.assignmentsPage.tool')}>{label('tool')}</HelpTh>
                <HelpTh help={t('economic.help.assignmentsPage.recipient')}>
                  {label('recipient')}
                </HelpTh>
                <HelpTh help={t('economic.help.assignmentsPage.kind')}>{label('kind')}</HelpTh>
                <HelpTh help={t('economic.help.assignmentsPage.note')}>{label('note')}</HelpTh>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {assignments.data.items.map((assignment) => {
                const recipient = recipientOf(assignment)
                return (
                  <Table.Tr key={assignment.id}>
                    <Table.Td>{formatDate(assignment.date)}</Table.Td>
                    <Table.Td>{assignment.tool.name}</Table.Td>
                    <Table.Td>
                      <Anchor component={Link} to={recipient.to}>
                        {recipient.name}
                      </Anchor>
                    </Table.Td>
                    <Table.Td>{label(recipient.kind)}</Table.Td>
                    <Table.Td>{assignment.note}</Table.Td>
                    <Table.Td ta="right">
                      {canEdit && (
                        <Group gap="xs" justify="flex-end" wrap="nowrap">
                          <Button
                            size="compact-xs"
                            variant="default"
                            aria-label={label('editNamed', { name: recipient.name })}
                            onClick={() => setEditing(assignment)}
                          >
                            {t('app.edit')}
                          </Button>
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            color="red"
                            aria-label={label('deleteNamed', { name: recipient.name })}
                            onClick={() => remove(assignment.id)}
                          >
                            {t('app.delete')}
                          </Button>
                        </Group>
                      )}
                    </Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {assignments.data && (
        <Pager {...paging.pager(assignments.data.total)} />
      )}
      <Modal opened={editing !== null} onClose={() => setEditing(null)} title={label('editTitle')}>
        {editing && (
          <AssignmentForm
            target={
              editing.actor
                ? { actor_id: editing.actor.id }
                : { person_id: editing.person?.id ?? '' }
            }
            assignment={editing}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>
    </Stack>
  )
}
