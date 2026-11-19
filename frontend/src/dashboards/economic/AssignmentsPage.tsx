import {
  Alert,
  Anchor,
  Button,
  Group,
  Loader,
  NativeSelect,
  Stack,
  Table,
  Text,
} from '@mantine/core'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { downloadUrl } from '../../api/client'
import { useAuth } from '../../platform/authContext'
import { errorMessage } from '../../platform/errorMessage'
import { formatDate } from '../../platform/format'
import { Pager } from '../../platform/Pager'
import { hasLevel } from '../../platform/types'
import { currentYear } from '../../platform/years'
import { YearSelect } from '../../platform/YearSelect'
import { BASE, BASE_PATH, PAGE_SIZE, send, useAction, useAssignments, useTools } from './api'
import type { Assignment } from './types'

const recipientOf = (assignment: Assignment) =>
  assignment.actor
    ? { kind: 'actor', name: assignment.actor.name, to: `${BASE_PATH}/actors/${assignment.actor.id}` }
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
  const [offset, setOffset] = useState(0)
  const assignments = useAssignments({ year, tool_id: toolId, limit: PAGE_SIZE, offset })
  const canEdit = hasLevel(me, 'economic', 'editor')
  const label = (key: string, options = {}) => t(`economic.assignments.${key}`, options)

  function remove(id: string) {
    if (!window.confirm(label('deleteConfirm'))) return
    void action.run(() => send('DELETE', `/assignments/${id}`))
  }

  return (
    <Stack>
      <Group align="flex-end" gap="lg">
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
                <Table.Th>{label('date')}</Table.Th>
                <Table.Th>{label('tool')}</Table.Th>
                <Table.Th>{label('recipient')}</Table.Th>
                <Table.Th>{label('kind')}</Table.Th>
                <Table.Th>{label('note')}</Table.Th>
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
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          aria-label={label('deleteNamed', { name: recipient.name })}
                          onClick={() => remove(assignment.id)}
                        >
                          {t('app.delete')}
                        </Button>
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
        <Pager
          total={assignments.data.total}
          limit={PAGE_SIZE}
          offset={offset}
          onChange={setOffset}
        />
      )}
    </Stack>
  )
}
